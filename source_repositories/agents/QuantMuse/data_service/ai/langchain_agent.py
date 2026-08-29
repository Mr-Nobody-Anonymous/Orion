import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
import logging
from datetime import datetime, timedelta
import json
from dataclasses import dataclass

@dataclass
class StrategyRecommendation:
    """Strategy recommendation from LLM agent"""
    strategy_name: str
    description: str
    symbols: List[str]
    signal: str  # 'buy', 'sell', 'hold'
    confidence: float
    reasoning: str
    parameters: Dict[str, Any]
    risk_level: str
    expected_return: float
    time_horizon: str
    timestamp: datetime

@dataclass
class MarketAnalysis:
    """Market analysis from LLM agent"""
    summary: str
    key_events: List[str]
    sentiment: str
    trends: List[str]
    risks: List[str]
    opportunities: List[str]
    recommendations: List[str]
    timestamp: datetime

class LangChainAgent:
    """LangChain agent for intelligent trading analysis"""
    
    def __init__(self, llm_integration, nlp_processor=None):
        self.llm_integration = llm_integration
        self.nlp_processor = nlp_processor
        self.logger = logging.getLogger(__name__)
        
        # Initialize LangChain components
        self._init_langchain()
        
        # Agent tools
        self.tools = self._create_tools()
        
    def _init_langchain(self):
        """Initialize LangChain components"""
        try:
            from langchain.agents import initialize_agent, AgentType
            from langchain.tools import Tool
            from langchain.memory import ConversationBufferMemory
            from langchain.chains import LLMChain
            from langchain.prompts import PromptTemplate
            
            self.langchain_available = True
            self.memory = ConversationBufferMemory()
            
        except ImportError:
            self.logger.warning("LangChain not available. Install with: pip install langchain")
            self.langchain_available = False
    
    def _create_tools(self) -> List[Any]:
        """Create tools for the agent"""
        tools = []
        
        if not self.langchain_available:
            return tools
        
        try:
            from langchain.tools import Tool
            
            # Market data analysis tool
            market_tool = Tool(
                name="market_analysis",
                func=self._analyze_market_data,
                description="Analyze market data and identify trends"
            )
            tools.append(market_tool)
            
            # Sentiment analysis tool
            sentiment_tool = Tool(
                name="sentiment_analysis",
                func=self._analyze_sentiment,
                description="Analyze sentiment from news and social media"
            )
            tools.append(sentiment_tool)
            
            # Technical analysis tool
            technical_tool = Tool(
                name="technical_analysis",
                func=self._perform_technical_analysis,
                description="Perform technical analysis on price data"
            )
            tools.append(technical_tool)
            
            # Risk assessment tool
            risk_tool = Tool(
                name="risk_assessment",
                func=self._assess_risk,
                description="Assess portfolio and market risk"
            )
            tools.append(risk_tool)
            
        except Exception as e:
            self.logger.error(f"Error creating tools: {e}")
        
        return tools
    
    def generate_strategy_recommendation(self, 
                                       market_data: pd.DataFrame,
                                       sentiment_data: pd.DataFrame,
                                       portfolio_data: Dict[str, Any],
                                       symbols: List[str]) -> StrategyRecommendation:
        """Generate strategy recommendation using LLM agent"""
        try:
            # Create comprehensive prompt
            prompt = self._create_strategy_prompt(market_data, sentiment_data, portfolio_data, symbols)
            
            # Get LLM response
            response = self.llm_integration.provider.generate_response(prompt)
            
            # Parse response
            strategy = self._parse_strategy_response(response.content, symbols)
            
            return strategy
            
        except Exception as e:
            self.logger.error(f"Error generating strategy recommendation: {e}")
            return self._create_default_strategy_recommendation(symbols)
    
    def analyze_market_intelligence(self, 
                                  news_data: List[Dict[str, Any]],
                                  social_data: List[Dict[str, Any]],
                                  market_data: pd.DataFrame) -> MarketAnalysis:
        """Analyze market intelligence using LLM agent"""
        try:
            # Create analysis prompt
            prompt = self._create_market_analysis_prompt(news_data, social_data, market_data)
            
            # Get LLM response
            response = self.llm_integration.provider.generate_response(prompt)
            
            # Parse response
            analysis = self._parse_market_analysis_response(response.content)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error analyzing market intelligence: {e}")
            return self._create_default_market_analysis()
    
    def generate_automated_report(self, 
                                strategy_results: List[StrategyRecommendation],
                                market_analysis: MarketAnalysis,
                                performance_metrics: Dict[str, float]) -> str:
        """Generate automated trading report"""
        try:
            # Create report prompt
            prompt = self._create_report_prompt(strategy_results, market_analysis, performance_metrics)
            
            # Get LLM response
            response = self.llm_integration.provider.generate_response(prompt)
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error generating automated report: {e}")
            return "Unable to generate report due to technical issues."
    
    def _create_strategy_prompt(self, market_data: pd.DataFrame, 
                              sentiment_data: pd.DataFrame,
                              portfolio_data: Dict[str, Any],
                              symbols: List[str]) -> str:
        """Create prompt for strategy generation"""
        
        # Market data summary
        market_summary = f"""
        Market Data Summary:
        - Symbols: {symbols}
        - Data points: {len(market_data)}
        - Date range: {market_data.index.min()} to {market_data.index.max()}
        - Price volatility: {market_data['close'].pct_change().std():.3f}
        """
        
        # Sentiment summary
        if not sentiment_data.empty:
            avg_sentiment = sentiment_data['sentiment_score'].mean()
            sentiment_summary = f"""
            Sentiment Summary:
            - Average sentiment: {avg_sentiment:.3f}
            - Sentiment sources: {sentiment_data['source'].nunique()}
            - Recent sentiment trend: {'positive' if avg_sentiment > 0 else 'negative' if avg_sentiment < 0 else 'neutral'}
            """
        else:
            sentiment_summary = "No sentiment data available."
        
        # Portfolio summary
        portfolio_summary = f"""
        Portfolio Summary:
        - Total value: ${portfolio_data.get('total_value', 0):,.2f}
        - Cash: ${portfolio_data.get('cash', 0):,.2f}
        - Number of positions: {portfolio_data.get('num_positions', 0)}
        - Current risk level: {portfolio_data.get('risk_level', 'medium')}
        """
        
        prompt = f"""
        You are an expert quantitative trading strategist. Based on the following information, generate a comprehensive trading strategy recommendation.
        
        {market_summary}
        
        {sentiment_summary}
        
        {portfolio_summary}
        
        Please provide a JSON response with the following structure:
        {{
            "strategy_name": "Descriptive strategy name",
            "description": "Detailed strategy description",
            "symbols": ["list", "of", "recommended", "symbols"],
            "signal": "buy/sell/hold",
            "confidence": 0.0-1.0,
            "reasoning": "Detailed reasoning for the recommendation",
            "parameters": {{
                "lookback_period": 20,
                "position_size": 0.05,
                "stop_loss": 0.10,
                "take_profit": 0.20
            }},
            "risk_level": "low/medium/high",
            "expected_return": 0.0-1.0,
            "time_horizon": "short/medium/long"
        }}
        
        Consider market conditions, sentiment analysis, and portfolio constraints in your recommendation.
        """
        
        return prompt
    
    def _create_market_analysis_prompt(self, news_data: List[Dict[str, Any]],
                                     social_data: List[Dict[str, Any]],
                                     market_data: pd.DataFrame) -> str:
        """Create prompt for market analysis"""
        
        # News summary
        news_summary = f"Recent news items: {len(news_data)} articles analyzed"
        if news_data:
            news_summary += f"\nKey topics: {', '.join(set([item.get('topic', 'general') for item in news_data[:5]]))}"
        
        # Social media summary
        social_summary = f"Social media posts: {len(social_data)} posts analyzed"
        if social_data:
            social_summary += f"\nPlatforms: {', '.join(set([item.get('platform', 'unknown') for item in social_data[:5]]))}"
        
        # Market data summary
        market_summary = f"""
        Market Data:
        - Price trend: {'Upward' if market_data['close'].iloc[-1] > market_data['close'].iloc[-20] else 'Downward'}
        - Volatility: {market_data['close'].pct_change().std():.3f}
        - Volume trend: {'Increasing' if market_data['volume'].iloc[-5:].mean() > market_data['volume'].iloc[-20:-5].mean() else 'Decreasing'}
        """
        
        prompt = f"""
        You are a market intelligence analyst. Analyze the following market information and provide insights.
        
        {news_summary}
        
        {social_summary}
        
        {market_summary}
        
        Please provide a JSON response with the following structure:
        {{
            "summary": "Executive summary of market conditions",
            "key_events": ["list", "of", "key", "events"],
            "sentiment": "overall market sentiment",
            "trends": ["list", "of", "identified", "trends"],
            "risks": ["list", "of", "potential", "risks"],
            "opportunities": ["list", "of", "trading", "opportunities"],
            "recommendations": ["list", "of", "action", "recommendations"]
        }}
        """
        
        return prompt
    
    def _create_report_prompt(self, strategy_results: List[StrategyRecommendation],
                            market_analysis: MarketAnalysis,
                            performance_metrics: Dict[str, float]) -> str:
        """Create prompt for automated report generation"""
        
        # Strategy summary
        strategy_summary = f"Generated {len(strategy_results)} strategy recommendations"
        if strategy_results:
            strategy_summary += f"\nTop recommendation: {strategy_results[0].strategy_name}"
        
        # Performance summary
        performance_summary = f"""
        Performance Metrics:
        - Total Return: {performance_metrics.get('total_return', 0):.2%}
        - Sharpe Ratio: {performance_metrics.get('sharpe_ratio', 0):.2f}
        - Max Drawdown: {performance_metrics.get('max_drawdown', 0):.2%}
        - Win Rate: {performance_metrics.get('win_rate', 0):.2%}
        """
        
        prompt = f"""
        You are a financial analyst creating a daily trading report. Based on the following information, generate a comprehensive report.
        
        {strategy_summary}
        
        Market Analysis:
        - Summary: {market_analysis.summary}
        - Sentiment: {market_analysis.sentiment}
        - Key Risks: {', '.join(market_analysis.risks[:3])}
        
        {performance_summary}
        
        Please generate a professional trading report with the following sections:
        1. Executive Summary
        2. Market Overview
        3. Strategy Recommendations
        4. Risk Assessment
        5. Performance Review
        6. Outlook and Recommendations
        
        Make the report clear, actionable, and professional.
        """
        
        return prompt
    
    def _parse_strategy_response(self, response_content: str, symbols: List[str]) -> StrategyRecommendation:
        """Parse LLM response into StrategyRecommendation"""
        try:
            # Try to parse JSON response
            if response_content.strip().startswith('{'):
                data = json.loads(response_content)
            else:
                # Fallback parsing
                data = self._extract_strategy_from_text(response_content)
            
            return StrategyRecommendation(
                strategy_name=data.get('strategy_name', 'Default Strategy'),
                description=data.get('description', 'No description available'),
                symbols=data.get('symbols', symbols),
                signal=data.get('signal', 'hold'),
                confidence=data.get('confidence', 0.5),
                reasoning=data.get('reasoning', 'No reasoning provided'),
                parameters=data.get('parameters', {}),
                risk_level=data.get('risk_level', 'medium'),
                expected_return=data.get('expected_return', 0.0),
                time_horizon=data.get('time_horizon', 'medium'),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing strategy response: {e}")
            return self._create_default_strategy_recommendation(symbols)
    
    def _parse_market_analysis_response(self, response_content: str) -> MarketAnalysis:
        """Parse LLM response into MarketAnalysis"""
        try:
            # Try to parse JSON response
            if response_content.strip().startswith('{'):
                data = json.loads(response_content)
            else:
                # Fallback parsing
                data = self._extract_analysis_from_text(response_content)
            
            return MarketAnalysis(
                summary=data.get('summary', 'No summary available'),
                key_events=data.get('key_events', []),
                sentiment=data.get('sentiment', 'neutral'),
                trends=data.get('trends', []),
                risks=data.get('risks', []),
                opportunities=data.get('opportunities', []),
                recommendations=data.get('recommendations', []),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error parsing market analysis response: {e}")
            return self._create_default_market_analysis()
    
    def _extract_strategy_from_text(self, text: str) -> Dict[str, Any]:
        """Extract strategy information from text response"""
        # Simple text parsing as fallback
        data = {
            'strategy_name': 'Text-Based Strategy',
            'description': text[:200] + '...' if len(text) > 200 else text,
            'symbols': [],
            'signal': 'hold',
            'confidence': 0.5,
            'reasoning': text,
            'parameters': {},
            'risk_level': 'medium',
            'expected_return': 0.0,
            'time_horizon': 'medium'
        }
        
        # Try to extract signal
        if 'buy' in text.lower():
            data['signal'] = 'buy'
        elif 'sell' in text.lower():
            data['signal'] = 'sell'
        
        return data
    
    def _extract_analysis_from_text(self, text: str) -> Dict[str, Any]:
        """Extract analysis information from text response"""
        return {
            'summary': text[:200] + '...' if len(text) > 200 else text,
            'key_events': [],
            'sentiment': 'neutral',
            'trends': [],
            'risks': [],
            'opportunities': [],
            'recommendations': []
        }
    
    def _create_default_strategy_recommendation(self, symbols: List[str]) -> StrategyRecommendation:
        """Create default strategy recommendation"""
        return StrategyRecommendation(
            strategy_name="Default Strategy",
            description="No strategy recommendation available",
            symbols=symbols,
            signal="hold",
            confidence=0.0,
            reasoning="Unable to generate strategy recommendation",
            parameters={},
            risk_level="medium",
            expected_return=0.0,
            time_horizon="medium",
            timestamp=datetime.now()
        )
    
    def _create_default_market_analysis(self) -> MarketAnalysis:
        """Create default market analysis"""
        return MarketAnalysis(
            summary="No market analysis available",
            key_events=[],
            sentiment="neutral",
            trends=[],
            risks=[],
            opportunities=[],
            recommendations=[],
            timestamp=datetime.now()
        )
    
    # Tool functions for LangChain agent
    def _analyze_market_data(self, query: str) -> str:
        """Tool for market data analysis"""
        return "Market data analysis tool - implementation needed"
    
    def _analyze_sentiment(self, query: str) -> str:
        """Tool for sentiment analysis"""
        return "Sentiment analysis tool - implementation needed"
    
    def _perform_technical_analysis(self, query: str) -> str:
        """Tool for technical analysis"""
        return "Technical analysis tool - implementation needed"
    
    def _assess_risk(self, query: str) -> str:
        """Tool for risk assessment"""
        return "Risk assessment tool - implementation needed" 