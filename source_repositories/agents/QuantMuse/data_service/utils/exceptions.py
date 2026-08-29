class DataFetchError(Exception):
    """Raised when there's an error fetching data from APIs"""
    pass

class ProcessingError(Exception):
    """Raised when there's an error processing market data"""
    pass

class ValidationError(Exception):
    """Raised when input data validation fails"""
    pass 