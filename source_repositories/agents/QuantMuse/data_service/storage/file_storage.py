import pandas as pd
import json
import pickle
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union
from datetime import datetime
import logging

class FileStorage:
    """File storage manager for trading system data"""
    
    def __init__(self, base_path: str = "data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.base_path / "market_data").mkdir(exist_ok=True)
        (self.base_path / "trades").mkdir(exist_ok=True)
        (self.base_path / "signals").mkdir(exist_ok=True)
        (self.base_path / "performance").mkdir(exist_ok=True)
        (self.base_path / "backtest").mkdir(exist_ok=True)
        
        self.logger = logging.getLogger(__name__)
    
    def save_market_data_csv(self, symbol: str, df: pd.DataFrame, 
                           interval: str = "1h") -> str:
        """Save market data to CSV file"""
        try:
            filename = f"{symbol}_{interval}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath = self.base_path / "market_data" / filename
            
            df.to_csv(filepath, index=True)
            self.logger.info(f"Market data saved to CSV: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Save market data CSV error: {e}")
            return ""
    
    def load_market_data_csv(self, filepath: str) -> Optional[pd.DataFrame]:
        """Load market data from CSV file"""
        try:
            df = pd.read_csv(filepath, index_col=0, parse_dates=True)
            self.logger.info(f"Market data loaded from CSV: {filepath}")
            return df
        except Exception as e:
            self.logger.error(f"Load market data CSV error: {e}")
            return None
    
    def save_trades_json(self, trades: list, filename: Optional[str] = None) -> str:
        """Save trade records to JSON file"""
        try:
            if filename is None:
                filename = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            filepath = self.base_path / "trades" / filename
            
            # Handle datetime serialization
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(trades, f, default=datetime_handler, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Trades saved to JSON: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Save trades JSON error: {e}")
            return ""
    
    def load_trades_json(self, filepath: str) -> Optional[list]:
        """Load trade records from JSON file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                trades = json.load(f)
            
            # Convert datetime strings
            for trade in trades:
                if 'timestamp' in trade:
                    trade['timestamp'] = datetime.fromisoformat(trade['timestamp'])
            
            self.logger.info(f"Trades loaded from JSON: {filepath}")
            return trades
        except Exception as e:
            self.logger.error(f"Load trades JSON error: {e}")
            return None
    
    def save_performance_report(self, performance_data: Dict[str, Any], 
                              strategy_name: str) -> str:
        """Save performance report to JSON file"""
        try:
            filename = f"performance_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.base_path / "performance" / filename
            
            # Handle numpy types
            def numpy_handler(obj):
                if hasattr(obj, 'item'):
                    return obj.item()
                return str(obj)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(performance_data, f, default=numpy_handler, indent=2, ensure_ascii=False)
            
            self.logger.info(f"Performance report saved: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Save performance report error: {e}")
            return ""
    
    def save_backtest_results(self, results: Dict[str, Any], 
                            strategy_name: str) -> str:
        """Save backtest results to pickle file"""
        try:
            filename = f"backtest_{strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            filepath = self.base_path / "backtest" / filename
            
            with open(filepath, 'wb') as f:
                pickle.dump(results, f)
            
            self.logger.info(f"Backtest results saved: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Save backtest results error: {e}")
            return ""
    
    def load_backtest_results(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Load backtest results from pickle file"""
        try:
            with open(filepath, 'rb') as f:
                results = pickle.load(f)
            
            self.logger.info(f"Backtest results loaded: {filepath}")
            return results
        except Exception as e:
            self.logger.error(f"Load backtest results error: {e}")
            return None
    
    def export_to_excel(self, data_dict: Dict[str, pd.DataFrame], 
                       filename: str) -> str:
        """Export multiple DataFrames to Excel file"""
        try:
            filepath = self.base_path / f"{filename}.xlsx"
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                for sheet_name, df in data_dict.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=True)
            
            self.logger.info(f"Data exported to Excel: {filepath}")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Export to Excel error: {e}")
            return ""
    
    def list_files(self, subdir: str) -> list:
        """List all files in specified subdirectory"""
        try:
            dir_path = self.base_path / subdir
            if not dir_path.exists():
                return []
            
            files = []
            for file in dir_path.iterdir():
                if file.is_file():
                    files.append({
                        'name': file.name,
                        'path': str(file),
                        'size': file.stat().st_size,
                        'modified': datetime.fromtimestamp(file.stat().st_mtime)
                    })
            
            return sorted(files, key=lambda x: x['modified'], reverse=True)
        except Exception as e:
            self.logger.error(f"List files error: {e}")
            return []
    
    def delete_file(self, filepath: str) -> bool:
        """Delete file"""
        try:
            path = Path(filepath)
            if path.exists():
                path.unlink()
                self.logger.info(f"File deleted: {filepath}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Delete file error: {e}")
            return False 