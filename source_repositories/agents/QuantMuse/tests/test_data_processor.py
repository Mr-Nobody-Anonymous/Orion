import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from data_service.processors.data_processor import DataProcessor
from data_service.utils.exceptions import ProcessingError

class TestDataProcessor(unittest.TestCase):
    """Test cases for DataProcessor"""

    def setUp(self):
        """Set up test fixtures"""
        self.processor = DataProcessor()
        
        # Create proper sample data
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        self.sample_data = pd.DataFrame({
            'open': np.random.randn(len(dates)) + 100,
            'high': np.random.randn(len(dates)) + 101,
            'low': np.random.randn(len(dates)) + 99,
            'close': np.random.randn(len(dates)) + 100,
            'volume': np.random.randn(len(dates)) * 1000
        }, index=dates)

    def test_process_market_data(self):
        """Test market data processing with valid data"""
        result = self.processor.process_market_data(self.sample_data)
        
        # Verify results
        self.assertIsNotNone(result.indicators)
        self.assertIsNotNone(result.statistics)
        self.assertIsNotNone(result.signals)

    def test_error_handling(self):
        """Test error handling with invalid data"""
        # Create invalid dataframe (missing required columns)
        invalid_data = pd.DataFrame({
            'wrong_column': [1, 2, 3]
        })
        
        with self.assertRaises(ProcessingError):
            self.processor.process_market_data(invalid_data)

    def test_empty_data(self):
        """Test handling of empty data"""
        empty_data = pd.DataFrame()
        
        with self.assertRaises(ProcessingError):
            self.processor.process_market_data(empty_data)

if __name__ == '__main__':
    unittest.main() 