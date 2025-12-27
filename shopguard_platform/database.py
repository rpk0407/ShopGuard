"""
Database Layer - SQLite persistence for the trading platform
"""
import sqlite3
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path


DB_PATH = Path(__file__).parent.parent / "shopguard_data.db"


@dataclass
class Trade:
    id: int
    symbol: str
    side: str  # BUY or SELL
    quantity: float
    price: float
    total: float
    pnl: float
    strategy: str
    confidence: float
    timestamp: str
    notes: str = ""


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    entry_time: str
    strategy: str


@dataclass
class Alert:
    id: int
    type: str  # price, signal, news, social
    symbol: str
    message: str
    severity: str  # info, warning, critical
    timestamp: str
    read: bool = False


class Database:
    """SQLite database for persistent storage"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database tables"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Settings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        ''')

        # Portfolio table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cash REAL,
                initial_capital REAL,
                updated_at TEXT
            )
        ''')

        # Positions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL,
                entry_price REAL,
                current_price REAL,
                stop_loss REAL,
                take_profit REAL,
                entry_time TEXT,
                strategy TEXT
            )
        ''')

        # Trades history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                total REAL,
                pnl REAL,
                strategy TEXT,
                confidence REAL,
                timestamp TEXT,
                notes TEXT
            )
        ''')

        # Alerts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT,
                symbol TEXT,
                message TEXT,
                severity TEXT,
                timestamp TEXT,
                read INTEGER DEFAULT 0
            )
        ''')

        # Watchlist table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS watchlist (
                symbol TEXT PRIMARY KEY,
                asset_type TEXT,
                added_at TEXT,
                notes TEXT
            )
        ''')

        # Performance metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                date TEXT PRIMARY KEY,
                equity REAL,
                pnl REAL,
                trades_count INTEGER,
                win_rate REAL
            )
        ''')

        conn.commit()
        conn.close()

        # Initialize default settings if not exists
        self._init_defaults()

    def _init_defaults(self):
        """Initialize default settings"""
        defaults = {
            "initial_capital": "100",
            "risk_level": "moderate",
            "stop_loss_pct": "0.03",
            "take_profit_pct": "0.06",
            "max_position_pct": "0.20",
            "max_daily_loss_pct": "0.05",
            "min_confidence": "0.65",
            "scan_interval": "5",
            "auto_trade": "false",
            "enable_news": "true",
            "enable_social": "true",
            "stocks": json.dumps(["NVDA", "SPY", "QQQ", "AAPL", "TSLA", "AMD"]),
            "crypto": json.dumps(["bitcoin", "ethereum"]),
            "alpaca_connected": "false"
        }

        for key, value in defaults.items():
            if self.get_setting(key) is None:
                self.set_setting(key, value)

        # Initialize portfolio if not exists
        if self.get_portfolio() is None:
            self.save_portfolio(float(defaults["initial_capital"]), float(defaults["initial_capital"]))

    # =========================================================================
    # SETTINGS
    # =========================================================================

    def get_setting(self, key: str) -> Optional[str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else None

    def set_setting(self, key: str, value: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_all_settings(self) -> Dict[str, str]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        conn.close()
        return {row[0]: row[1] for row in rows}

    # =========================================================================
    # PORTFOLIO
    # =========================================================================

    def get_portfolio(self) -> Optional[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT cash, initial_capital, updated_at FROM portfolio ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"cash": row[0], "initial_capital": row[1], "updated_at": row[2]}
        return None

    def save_portfolio(self, cash: float, initial_capital: float):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO portfolio (cash, initial_capital, updated_at)
            VALUES (?, ?, ?)
        ''', (cash, initial_capital, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def update_cash(self, cash: float):
        portfolio = self.get_portfolio()
        if portfolio:
            self.save_portfolio(cash, portfolio["initial_capital"])

    # =========================================================================
    # POSITIONS
    # =========================================================================

    def get_positions(self) -> List[Position]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions")
        rows = cursor.fetchall()
        conn.close()

        positions = []
        for row in rows:
            positions.append(Position(
                symbol=row[0],
                quantity=row[1],
                entry_price=row[2],
                current_price=row[3],
                stop_loss=row[4],
                take_profit=row[5],
                entry_time=row[6],
                strategy=row[7]
            ))
        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Position(
                symbol=row[0],
                quantity=row[1],
                entry_price=row[2],
                current_price=row[3],
                stop_loss=row[4],
                take_profit=row[5],
                entry_time=row[6],
                strategy=row[7]
            )
        return None

    def save_position(self, position: Position):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO positions
            (symbol, quantity, entry_price, current_price, stop_loss, take_profit, entry_time, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            position.symbol, position.quantity, position.entry_price,
            position.current_price, position.stop_loss, position.take_profit,
            position.entry_time, position.strategy
        ))
        conn.commit()
        conn.close()

    def update_position_price(self, symbol: str, current_price: float):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE positions SET current_price = ? WHERE symbol = ?", (current_price, symbol))
        conn.commit()
        conn.close()

    def delete_position(self, symbol: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    # =========================================================================
    # TRADES
    # =========================================================================

    def add_trade(self, trade: Trade):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trades
            (symbol, side, quantity, price, total, pnl, strategy, confidence, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade.symbol, trade.side, trade.quantity, trade.price,
            trade.total, trade.pnl, trade.strategy, trade.confidence,
            trade.timestamp, trade.notes
        ))
        conn.commit()
        conn.close()

    def get_trades(self, limit: int = 50) -> List[Trade]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [Trade(
            id=row[0], symbol=row[1], side=row[2], quantity=row[3],
            price=row[4], total=row[5], pnl=row[6], strategy=row[7],
            confidence=row[8], timestamp=row[9], notes=row[10]
        ) for row in rows]

    def get_trade_stats(self) -> Dict:
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM trades WHERE pnl > 0")
        winning_trades = cursor.fetchone()[0]

        cursor.execute("SELECT SUM(pnl) FROM trades")
        total_pnl = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(pnl) FROM trades WHERE pnl > 0")
        avg_win = cursor.fetchone()[0] or 0

        cursor.execute("SELECT AVG(pnl) FROM trades WHERE pnl < 0")
        avg_loss = cursor.fetchone()[0] or 0

        conn.close()

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": total_trades - winning_trades,
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2)
        }

    # =========================================================================
    # ALERTS
    # =========================================================================

    def add_alert(self, alert_type: str, symbol: str, message: str, severity: str = "info"):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO alerts (type, symbol, message, severity, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (alert_type, symbol, message, severity, datetime.now().isoformat()))
        conn.commit()
        conn.close()

    def get_alerts(self, unread_only: bool = False, limit: int = 20) -> List[Alert]:
        conn = self._get_conn()
        cursor = conn.cursor()

        if unread_only:
            cursor.execute("SELECT * FROM alerts WHERE read = 0 ORDER BY id DESC LIMIT ?", (limit,))
        else:
            cursor.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [Alert(
            id=row[0], type=row[1], symbol=row[2], message=row[3],
            severity=row[4], timestamp=row[5], read=bool(row[6])
        ) for row in rows]

    def mark_alert_read(self, alert_id: int):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET read = 1 WHERE id = ?", (alert_id,))
        conn.commit()
        conn.close()

    def mark_all_alerts_read(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE alerts SET read = 1")
        conn.commit()
        conn.close()

    # =========================================================================
    # WATCHLIST
    # =========================================================================

    def get_watchlist(self) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist")
        rows = cursor.fetchall()
        conn.close()

        return [{"symbol": row[0], "asset_type": row[1], "added_at": row[2], "notes": row[3]} for row in rows]

    def add_to_watchlist(self, symbol: str, asset_type: str = "stock", notes: str = ""):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO watchlist (symbol, asset_type, added_at, notes)
            VALUES (?, ?, ?, ?)
        ''', (symbol, asset_type, datetime.now().isoformat(), notes))
        conn.commit()
        conn.close()

    def remove_from_watchlist(self, symbol: str):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        conn.commit()
        conn.close()

    # =========================================================================
    # PERFORMANCE
    # =========================================================================

    def save_daily_performance(self, equity: float, pnl: float, trades_count: int, win_rate: float):
        conn = self._get_conn()
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute('''
            INSERT OR REPLACE INTO performance (date, equity, pnl, trades_count, win_rate)
            VALUES (?, ?, ?, ?, ?)
        ''', (today, equity, pnl, trades_count, win_rate))
        conn.commit()
        conn.close()

    def get_performance_history(self, days: int = 30) -> List[Dict]:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM performance ORDER BY date DESC LIMIT ?", (days,))
        rows = cursor.fetchall()
        conn.close()

        return [{"date": row[0], "equity": row[1], "pnl": row[2],
                 "trades_count": row[3], "win_rate": row[4]} for row in rows]


# Global database instance
db = Database()
