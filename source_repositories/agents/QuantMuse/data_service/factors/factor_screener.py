import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
import logging
from datetime import datetime
from dataclasses import dataclass

@dataclass
class ScreeningCriteria:
    """Screening criteria for stock selection"""
    factor_name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_percentile: Optional[float] = None
    max_percentile: Optional[float] = None
    weight: float = 1.0

@dataclass
class ScreeningResult:
    """Result of stock screening"""
    symbol: str
    score: float
    passed_criteria: List[str]
    failed_criteria: List[str]
    factor_values: Dict[str, float]
    rank: Optional[int] = None

class FactorScreener:
    """Factor-based stock screener"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.screening_criteria: List[ScreeningCriteria] = []
        self.custom_filters: Dict[str, Callable] = {}
    
    def add_criteria(self, criteria: ScreeningCriteria):
        """Add screening criteria"""
        self.screening_criteria.append(criteria)
        self.logger.info(f"Added screening criteria: {criteria.factor_name}")
    
    def add_custom_filter(self, name: str, filter_func: Callable):
        """Add custom filter function"""
        self.custom_filters[name] = filter_func
        self.logger.info(f"Added custom filter: {name}")
    
    def screen_stocks(self, factor_data: pd.DataFrame, 
                     universe: List[str] = None) -> List[ScreeningResult]:
        """Screen stocks based on criteria"""
        results = []
        
        # Filter by universe if specified
        if universe:
            factor_data = factor_data[factor_data['symbol'].isin(universe)]
        
        if factor_data.empty:
            self.logger.warning("No factor data available for screening")
            return results
        
        # Apply screening criteria
        for symbol in factor_data['symbol'].unique():
            symbol_data = factor_data[factor_data['symbol'] == symbol]
            
            result = self._evaluate_stock(symbol, symbol_data)
            if result:
                results.append(result)
        
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Assign ranks
        for i, result in enumerate(results):
            result.rank = i + 1
        
        self.logger.info(f"Screened {len(results)} stocks from {len(factor_data['symbol'].unique())} candidates")
        return results
    
    def _evaluate_stock(self, symbol: str, symbol_data: pd.DataFrame) -> Optional[ScreeningResult]:
        """Evaluate a single stock against all criteria"""
        passed_criteria = []
        failed_criteria = []
        factor_values = {}
        total_score = 0.0
        total_weight = 0.0
        
        # Extract factor values
        for _, row in symbol_data.iterrows():
            factor_values[row['factor_name']] = row['factor_value']
        
        # Check each criterion
        for criteria in self.screening_criteria:
            factor_value = factor_values.get(criteria.factor_name)
            
            if factor_value is None:
                failed_criteria.append(f"{criteria.factor_name}: No data")
                continue
            
            # Check value constraints
            if criteria.min_value is not None and factor_value < criteria.min_value:
                failed_criteria.append(f"{criteria.factor_name}: {factor_value} < {criteria.min_value}")
                continue
            
            if criteria.max_value is not None and factor_value > criteria.max_value:
                failed_criteria.append(f"{criteria.factor_name}: {factor_value} > {criteria.max_value}")
                continue
            
            # Check percentile constraints
            if criteria.min_percentile is not None or criteria.max_percentile is not None:
                percentile = self._calculate_percentile(factor_value, criteria.factor_name, symbol_data)
                
                if criteria.min_percentile is not None and percentile < criteria.min_percentile:
                    failed_criteria.append(f"{criteria.factor_name}: {percentile:.1f}% < {criteria.min_percentile}%")
                    continue
                
                if criteria.max_percentile is not None and percentile > criteria.max_percentile:
                    failed_criteria.append(f"{criteria.factor_name}: {percentile:.1f}% > {criteria.max_percentile}%")
                    continue
            
            # Criterion passed
            passed_criteria.append(criteria.factor_name)
            total_score += criteria.weight
            total_weight += criteria.weight
        
        # Apply custom filters
        for filter_name, filter_func in self.custom_filters.items():
            try:
                if filter_func(symbol, factor_values):
                    passed_criteria.append(filter_name)
                    total_score += 1.0
                    total_weight += 1.0
                else:
                    failed_criteria.append(filter_name)
            except Exception as e:
                self.logger.error(f"Error in custom filter {filter_name}: {e}")
                failed_criteria.append(f"{filter_name}: Error")
        
        # Calculate final score
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        
        return ScreeningResult(
            symbol=symbol,
            score=final_score,
            passed_criteria=passed_criteria,
            failed_criteria=failed_criteria,
            factor_values=factor_values
        )
    
    def _calculate_percentile(self, value: float, factor_name: str, 
                            all_data: pd.DataFrame) -> float:
        """Calculate percentile of a value within the factor distribution"""
        factor_values = all_data[all_data['factor_name'] == factor_name]['factor_value'].dropna()
        
        if len(factor_values) == 0:
            return 50.0
        
        return (factor_values < value).mean() * 100
    
    def create_value_screener(self, max_pe: float = 20.0, max_pb: float = 3.0, 
                            min_dividend_yield: float = 2.0) -> 'FactorScreener':
        """Create a value investing screener"""
        screener = FactorScreener()
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='pe_ratio',
            max_value=max_pe,
            weight=1.0
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='pb_ratio',
            max_value=max_pb,
            weight=1.0
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='dividend_yield',
            min_value=min_dividend_yield,
            weight=1.0
        ))
        
        return screener
    
    def create_momentum_screener(self, min_momentum: float = 10.0, 
                               min_volume_momentum: float = 5.0) -> 'FactorScreener':
        """Create a momentum investing screener"""
        screener = FactorScreener()
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='momentum_60d',
            min_value=min_momentum,
            weight=1.0
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='volume_momentum_20d',
            min_value=min_volume_momentum,
            weight=0.5
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='rsi',
            min_value=30,
            max_value=70,
            weight=0.5
        ))
        
        return screener
    
    def create_quality_screener(self, min_roe: float = 15.0, max_debt_equity: float = 0.5,
                              min_current_ratio: float = 1.5) -> 'FactorScreener':
        """Create a quality investing screener"""
        screener = FactorScreener()
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='roe',
            min_value=min_roe,
            weight=1.0
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='debt_to_equity',
            max_value=max_debt_equity,
            weight=1.0
        ))
        
        screener.add_criteria(ScreeningCriteria(
            factor_name='current_ratio',
            min_value=min_current_ratio,
            weight=0.5
        ))
        
        return screener
    
    def create_multi_factor_screener(self, factor_weights: Dict[str, float] = None) -> 'FactorScreener':
        """Create a multi-factor screener"""
        if factor_weights is None:
            factor_weights = {
                'momentum_60d': 0.3,
                'pe_ratio': 0.2,
                'roe': 0.2,
                'price_volatility': 0.15,
                'market_cap': 0.15
            }
        
        screener = FactorScreener()
        
        for factor_name, weight in factor_weights.items():
            screener.add_criteria(ScreeningCriteria(
                factor_name=factor_name,
                weight=weight
            ))
        
        return screener
    
    def add_market_cap_filter(self, min_market_cap: float = 1000000000,  # $1B
                            max_market_cap: float = None):
        """Add market cap filter"""
        def market_cap_filter(symbol: str, factor_values: Dict[str, float]) -> bool:
            market_cap = factor_values.get('market_cap', 0)
            
            if market_cap < min_market_cap:
                return False
            
            if max_market_cap and market_cap > max_market_cap:
                return False
            
            return True
        
        self.add_custom_filter('market_cap_filter', market_cap_filter)
    
    def add_volatility_filter(self, max_volatility: float = 30.0):
        """Add volatility filter"""
        def volatility_filter(symbol: str, factor_values: Dict[str, float]) -> bool:
            volatility = factor_values.get('price_volatility', 100)
            return volatility <= max_volatility
        
        self.add_custom_filter('volatility_filter', volatility_filter)
    
    def add_liquidity_filter(self, min_volume: float = 1000000):  # 1M shares
        """Add liquidity filter"""
        def liquidity_filter(symbol: str, factor_values: Dict[str, float]) -> bool:
            volume = factor_values.get('volume', 0)
            return volume >= min_volume
        
        self.add_custom_filter('liquidity_filter', liquidity_filter)
    
    def export_results(self, results: List[ScreeningResult], 
                      filepath: str, format: str = 'csv'):
        """Export screening results"""
        try:
            data = []
            for result in results:
                row = {
                    'symbol': result.symbol,
                    'score': result.score,
                    'rank': result.rank,
                    'passed_criteria': len(result.passed_criteria),
                    'failed_criteria': len(result.failed_criteria),
                    'passed_criteria_list': ';'.join(result.passed_criteria),
                    'failed_criteria_list': ';'.join(result.failed_criteria)
                }
                
                # Add factor values
                for factor_name, value in result.factor_values.items():
                    row[f'factor_{factor_name}'] = value
                
                data.append(row)
            
            df = pd.DataFrame(data)
            
            if format.lower() == 'csv':
                df.to_csv(filepath, index=False)
            elif format.lower() == 'excel':
                df.to_excel(filepath, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            self.logger.info(f"Exported {len(results)} screening results to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error exporting results: {e}")
    
    def get_screening_summary(self, results: List[ScreeningResult]) -> Dict[str, Any]:
        """Get summary statistics of screening results"""
        if not results:
            return {}
        
        summary = {
            'total_stocks': len(results),
            'avg_score': np.mean([r.score for r in results]),
            'min_score': min([r.score for r in results]),
            'max_score': max([r.score for r in results]),
            'score_std': np.std([r.score for r in results]),
            'top_10_symbols': [r.symbol for r in results[:10]],
            'criteria_pass_rates': {}
        }
        
        # Calculate pass rates for each criterion
        all_criteria = set()
        for result in results:
            all_criteria.update(result.passed_criteria)
            all_criteria.update(result.failed_criteria)
        
        for criteria in all_criteria:
            passed_count = sum(1 for r in results if criteria in r.passed_criteria)
            summary['criteria_pass_rates'][criteria] = passed_count / len(results)
        
        return summary 