"""
Professional Logging Configuration
===================================
Centralized logging setup with file and console handlers.
"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

# Log file path
LOG_FILE = os.path.join(LOGS_DIR, 'shopguard.log')


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Configured logger with file and console handlers
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        # File handler with rotation (10MB max, keep 5 backups)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)

        # Console handler (INFO and above)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatters
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%H:%M:%S'
        )

        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


class APILogger:
    """Specialized logger for API operations with structured output"""

    def __init__(self, name: str = "api"):
        self.logger = get_logger(name)

    def request(self, method: str, path: str, status: int = None, duration_ms: float = None):
        """Log API request"""
        msg = f"[REQUEST] {method} {path}"
        if status:
            msg += f" -> {status}"
        if duration_ms:
            msg += f" ({duration_ms:.1f}ms)"
        self.logger.info(msg)

    def websocket_connect(self, client_count: int, assets: list = None):
        """Log WebSocket connection"""
        assets_str = ", ".join(assets) if assets else "default"
        self.logger.info(f"[WS] Client connected | Total: {client_count} | Assets: {assets_str}")

    def websocket_disconnect(self, client_count: int):
        """Log WebSocket disconnection"""
        self.logger.info(f"[WS] Client disconnected | Total: {client_count}")

    def signal_update(self, asset: str, action: str, checks: int):
        """Log signal update"""
        self.logger.info(f"[SIGNAL] {asset}: {action} | Checks: {checks}/3")

    def error(self, component: str, error: Exception, context: str = ""):
        """Log error with context"""
        self.logger.error(f"[ERROR] {component}: {str(error)} | Context: {context}")

    def circuit_breaker(self, component: str, state: str, reason: str = ""):
        """Log circuit breaker state change"""
        self.logger.warning(f"[CIRCUIT] {component}: {state} | {reason}")


# Global instances
api_logger = APILogger("shopguard.api")
agent_logger = get_logger("shopguard.agents")
