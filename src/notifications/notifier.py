"""
Notification System Implementation

Provides flexible notification delivery across multiple channels:
- Email (via SendGrid)
- SMS (via Twilio)
- Telegram
- Webhooks
- Slack (future)
"""

import os
import json
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import asyncio
from loguru import logger


class NotificationChannel(Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    TELEGRAM = "telegram"
    WEBHOOK = "webhook"
    SLACK = "slack"


class NotificationPriority(Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Notification:
    """Notification message"""
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    channels: List[NotificationChannel] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'message': self.message,
            'priority': self.priority.value,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata
        }


class Notifier(ABC):
    """Abstract base class for notifiers"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send notification"""
        pass

    def is_enabled(self) -> bool:
        return self.enabled

    def format_message(self, notification: Notification) -> str:
        """Format notification message"""
        emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.NORMAL: "📢",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.CRITICAL: "🚨"
        }

        return f"{emoji.get(notification.priority, '📢')} **{notification.title}**\n\n{notification.message}"


# =============================================================================
# Email Notifier (SendGrid)
# =============================================================================

class EmailNotifier(Notifier):
    """Email notifications via SendGrid"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        from_email: str = "noreply@shopguard.trading",
        to_emails: Optional[List[str]] = None,
        enabled: bool = True
    ):
        super().__init__(enabled)
        self.api_key = api_key or os.getenv('SENDGRID_API_KEY')
        self.from_email = from_email
        self.to_emails = to_emails or []

        if not self.api_key:
            logger.warning("SendGrid API key not configured - email notifications disabled")
            self.enabled = False

    def send(self, notification: Notification) -> bool:
        """Send email notification"""
        if not self.enabled or not self.to_emails:
            return False

        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            # Create email
            message = Mail(
                from_email=Email(self.from_email),
                to_emails=[To(email) for email in self.to_emails],
                subject=f"[{notification.priority.value.upper()}] {notification.title}",
                html_content=Content("text/html", self._format_html(notification))
            )

            # Send via SendGrid
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {len(self.to_emails)} recipients")
                return True
            else:
                logger.error(f"Failed to send email: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Email notification error: {e}")
            return False

    def _format_html(self, notification: Notification) -> str:
        """Format notification as HTML email"""
        color = {
            NotificationPriority.LOW: "#17a2b8",
            NotificationPriority.NORMAL: "#6c757d",
            NotificationPriority.HIGH: "#ffc107",
            NotificationPriority.CRITICAL: "#dc3545"
        }

        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; padding: 20px;">
            <div style="background-color: {color.get(notification.priority, '#6c757d')}; color: white; padding: 15px; border-radius: 5px;">
                <h2>{notification.title}</h2>
            </div>
            <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid {color.get(notification.priority, '#6c757d')};">
                <p style="white-space: pre-wrap;">{notification.message}</p>
            </div>
            <div style="margin-top: 20px; font-size: 12px; color: #6c757d;">
                <p>Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Priority: {notification.priority.value.upper()}</p>
            </div>
        </body>
        </html>
        """


# =============================================================================
# SMS Notifier (Twilio)
# =============================================================================

class SMSNotifier(Notifier):
    """SMS notifications via Twilio"""

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        to_numbers: Optional[List[str]] = None,
        enabled: bool = True
    ):
        super().__init__(enabled)
        self.account_sid = account_sid or os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = auth_token or os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = from_number or os.getenv('TWILIO_FROM_NUMBER')
        self.to_numbers = to_numbers or []

        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.warning("Twilio credentials not configured - SMS notifications disabled")
            self.enabled = False

    def send(self, notification: Notification) -> bool:
        """Send SMS notification"""
        if not self.enabled or not self.to_numbers:
            return False

        try:
            from twilio.rest import Client

            client = Client(self.account_sid, self.auth_token)

            # Format message (SMS has 160 char limit)
            message = self._format_sms(notification)

            # Send to all recipients
            success_count = 0
            for to_number in self.to_numbers:
                try:
                    msg = client.messages.create(
                        body=message,
                        from_=self.from_number,
                        to=to_number
                    )
                    if msg.status in ['queued', 'sent', 'delivered']:
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send SMS to {to_number}: {e}")

            if success_count > 0:
                logger.info(f"SMS sent to {success_count}/{len(self.to_numbers)} recipients")
                return True
            return False

        except Exception as e:
            logger.error(f"SMS notification error: {e}")
            return False

    def _format_sms(self, notification: Notification) -> str:
        """Format notification for SMS (160 char limit)"""
        prefix = {
            NotificationPriority.LOW: "[INFO]",
            NotificationPriority.NORMAL: "[ALERT]",
            NotificationPriority.HIGH: "[WARNING]",
            NotificationPriority.CRITICAL: "[CRITICAL]"
        }

        # Truncate message to fit SMS limit
        header = f"{prefix.get(notification.priority, '[ALERT]')} {notification.title}"
        max_msg_len = 160 - len(header) - 3  # Reserve space for header and "..."

        if len(notification.message) > max_msg_len:
            message = notification.message[:max_msg_len] + "..."
        else:
            message = notification.message

        return f"{header}\n{message}"


# =============================================================================
# Telegram Notifier
# =============================================================================

class TelegramNotifier(Notifier):
    """Telegram notifications via Bot API"""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_ids: Optional[List[str]] = None,
        enabled: bool = True
    ):
        super().__init__(enabled)
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_ids = chat_ids or (os.getenv('TELEGRAM_CHAT_IDS', '').split(',') if os.getenv('TELEGRAM_CHAT_IDS') else [])

        if not self.bot_token or not self.chat_ids:
            logger.warning("Telegram credentials not configured - Telegram notifications disabled")
            self.enabled = False

    def send(self, notification: Notification) -> bool:
        """Send Telegram notification"""
        if not self.enabled or not self.chat_ids:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            message = self._format_telegram(notification)

            success_count = 0
            for chat_id in self.chat_ids:
                payload = {
                    'chat_id': chat_id,
                    'text': message,
                    'parse_mode': 'Markdown'
                }

                response = requests.post(url, json=payload, timeout=10)

                if response.status_code == 200:
                    success_count += 1
                else:
                    logger.error(f"Failed to send Telegram message to {chat_id}: {response.text}")

            if success_count > 0:
                logger.info(f"Telegram message sent to {success_count}/{len(self.chat_ids)} chats")
                return True
            return False

        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return False

    def _format_telegram(self, notification: Notification) -> str:
        """Format notification for Telegram (Markdown)"""
        emoji = {
            NotificationPriority.LOW: "ℹ️",
            NotificationPriority.NORMAL: "📢",
            NotificationPriority.HIGH: "⚠️",
            NotificationPriority.CRITICAL: "🚨"
        }

        message = f"{emoji.get(notification.priority, '📢')} *{notification.title}*\n\n"
        message += f"{notification.message}\n\n"
        message += f"_Time: {notification.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_"

        return message


# =============================================================================
# Webhook Notifier
# =============================================================================

class WebhookNotifier(Notifier):
    """Generic webhook notifications"""

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        enabled: bool = True
    ):
        super().__init__(enabled)
        self.webhook_url = webhook_url or os.getenv('WEBHOOK_URL')
        self.headers = headers or {}

        if not self.webhook_url:
            logger.warning("Webhook URL not configured - webhook notifications disabled")
            self.enabled = False

    def send(self, notification: Notification) -> bool:
        """Send webhook notification"""
        if not self.enabled:
            return False

        try:
            payload = notification.to_dict()

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code in [200, 201, 202, 204]:
                logger.info(f"Webhook notification sent successfully")
                return True
            else:
                logger.error(f"Webhook failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Webhook notification error: {e}")
            return False


# =============================================================================
# Multi-Channel Notifier
# =============================================================================

class MultiChannelNotifier:
    """Send notifications across multiple channels"""

    def __init__(self):
        self.notifiers: Dict[NotificationChannel, Notifier] = {}

    def add_notifier(self, channel: NotificationChannel, notifier: Notifier):
        """Add a notifier for a specific channel"""
        self.notifiers[channel] = notifier
        logger.info(f"Added {channel.value} notifier")

    def send(self, notification: Notification) -> Dict[NotificationChannel, bool]:
        """Send notification to all configured channels"""
        results = {}

        # If no specific channels specified, use all
        channels = notification.channels if notification.channels else list(self.notifiers.keys())

        for channel in channels:
            if channel in self.notifiers:
                notifier = self.notifiers[channel]
                if notifier.is_enabled():
                    results[channel] = notifier.send(notification)
                else:
                    results[channel] = False
            else:
                logger.warning(f"No notifier configured for {channel.value}")
                results[channel] = False

        return results

    def send_async(self, notification: Notification):
        """Send notification asynchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_in_executor(None, self.send, notification)


# =============================================================================
# Helper Functions
# =============================================================================

def create_default_notifier() -> MultiChannelNotifier:
    """Create a multi-channel notifier with all available channels"""
    notifier = MultiChannelNotifier()

    # Add email
    email = EmailNotifier(
        to_emails=os.getenv('NOTIFICATION_EMAILS', '').split(',') if os.getenv('NOTIFICATION_EMAILS') else []
    )
    notifier.add_notifier(NotificationChannel.EMAIL, email)

    # Add SMS
    sms = SMSNotifier(
        to_numbers=os.getenv('NOTIFICATION_PHONES', '').split(',') if os.getenv('NOTIFICATION_PHONES') else []
    )
    notifier.add_notifier(NotificationChannel.SMS, sms)

    # Add Telegram
    telegram = TelegramNotifier()
    notifier.add_notifier(NotificationChannel.TELEGRAM, telegram)

    # Add Webhook
    webhook = WebhookNotifier()
    notifier.add_notifier(NotificationChannel.WEBHOOK, webhook)

    return notifier


# =============================================================================
# Convenience Functions
# =============================================================================

def send_trade_notification(symbol: str, side: str, quantity: float, price: float, pnl: Optional[float] = None):
    """Send trade execution notification"""
    notifier = create_default_notifier()

    pnl_text = f"\nP&L: ${pnl:,.2f}" if pnl is not None else ""

    notification = Notification(
        title=f"Trade Executed: {side.upper()} {symbol}",
        message=f"Quantity: {quantity}\nPrice: ${price:.2f}{pnl_text}",
        priority=NotificationPriority.NORMAL,
        metadata={'symbol': symbol, 'side': side, 'quantity': quantity, 'price': price}
    )

    return notifier.send(notification)


def send_risk_alert(title: str, message: str, severity: str = "high"):
    """Send risk management alert"""
    notifier = create_default_notifier()

    priority = {
        'low': NotificationPriority.LOW,
        'medium': NotificationPriority.NORMAL,
        'high': NotificationPriority.HIGH,
        'critical': NotificationPriority.CRITICAL
    }.get(severity.lower(), NotificationPriority.HIGH)

    notification = Notification(
        title=title,
        message=message,
        priority=priority
    )

    return notifier.send(notification)


def send_system_alert(title: str, message: str):
    """Send system status alert"""
    notifier = create_default_notifier()

    notification = Notification(
        title=title,
        message=message,
        priority=NotificationPriority.CRITICAL
    )

    return notifier.send(notification)
