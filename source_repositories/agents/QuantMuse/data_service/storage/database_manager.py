import sqlite3
import pandas as pd
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
from pathlib import Path

class DatabaseManager:
    """Database manager supporting SQLite and PostgreSQL"""
    
    def __init__(self, db_type: str = "sqlite", db_path: str = "trading_data.db", 
                 connection_string: Optional[str] = None):
        self.db_type = db_type
        self.db_path = db_path
        self.connection_string = connection_string
        self.logger = logging.getLogger(__name__)
        self._init_database()
    
    def _init_database(self):
        """Initialize database and create tables"""
        if self.db_type == "sqlite":
            self.conn = sqlite3.connect(self.db_path)
            self._create_tables()
        elif self.db_type == "postgresql":
            import psycopg2
            self.conn = psycopg2.connect(self.connection_string)
            self._create_tables()
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")
    
    def _create_tables(self):
        """Create necessary database tables"""
        cursor = self.conn.cursor()
        
        # Market data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp)
            )
        ''')
        
        # Trade records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                status TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Strategy signals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                strength REAL,
                timestamp DATETIME NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance statistics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                total_pnl REAL,
                daily_return REAL,
                max_drawdown REAL,
                sharpe_ratio REAL,
                win_rate REAL,
                total_trades INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        ''')
        
        self.conn.commit()
    
    def save_market_data(self, symbol: str, df: pd.DataFrame):
        """Save market data to database"""
        df['symbol'] = symbol
        df['created_at'] = datetime.now()
        
        # Rename columns to match database structure
        df = df.rename(columns={
            'open': 'open',
            'high': 'high', 
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        df.to_sql('market_data', self.conn, if_exists='append', index=False)
        self.logger.info(f"Saved {len(df)} records for {symbol}")
    
    def get_market_data(self, symbol: str, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> pd.DataFrame:
        """Get market data from database"""
        query = f"SELECT * FROM market_data WHERE symbol = '{symbol}'"
        if start_date:
            query += f" AND timestamp >= '{start_date}'"
        if end_date:
            query += f" AND timestamp <= '{end_date}'"
        query += " ORDER BY timestamp"
        
        return pd.read_sql_query(query, self.conn)
    
    def save_trade(self, trade_data: Dict[str, Any]):
        """Save trade record to database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO trades 
            (order_id, symbol, side, quantity, price, status, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data['order_id'],
            trade_data['symbol'],
            trade_data['side'],
            trade_data['quantity'],
            trade_data['price'],
            trade_data['status'],
            trade_data['timestamp']
        ))
        self.conn.commit()
    
    def save_signal(self, signal_data: Dict[str, Any]):
        """Save strategy signal to database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO signals 
            (strategy_name, symbol, signal_type, strength, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            signal_data['strategy_name'],
            signal_data['symbol'],
            signal_data['signal_type'],
            signal_data['strength'],
            signal_data['timestamp']
        ))
        self.conn.commit()
    
    def save_performance(self, performance_data: Dict[str, Any]):
        """Save performance data to database"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO performance 
            (date, total_pnl, daily_return, max_drawdown, sharpe_ratio, win_rate, total_trades)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            performance_data['date'],
            performance_data['total_pnl'],
            performance_data['daily_return'],
            performance_data['max_drawdown'],
            performance_data['sharpe_ratio'],
            performance_data['win_rate'],
            performance_data['total_trades']
        ))
        self.conn.commit()
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close() 