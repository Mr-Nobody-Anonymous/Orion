import unittest
from data_service.fetchers import BinanceFetcher
from data_service.processors import DataProcessor

class TestIntegration(unittest.TestCase):
    """Integration tests for data service"""

    def setUp(self):
        """Set up test fixtures"""
        self.fetcher = BinanceFetcher()
        self.processor = DataProcessor()

    @unittest.skip("Skipping live API test")  # Skip live API calls during testing
    def test_fetch_and_process_flow(self):
        """Test complete data fetch and process flow"""
        try:
            # Fetch data
            data = self.fetcher.fetch_historical_data(
                symbol="BTCUSDT",
                interval="1d",
                limit=100
            )
            
            # Process data
            processed = self.processor.process_market_data(data)
            
            # Verify results
            self.assertIsNotNone(processed.indicators)
            self.assertIsNotNone(processed.statistics)
            self.assertTrue(len(processed.signals) > 0)
            
        except Exception as e:
            self.fail(f"Integration test failed: {str(e)}")

if __name__ == '__main__':
    unittest.main() 