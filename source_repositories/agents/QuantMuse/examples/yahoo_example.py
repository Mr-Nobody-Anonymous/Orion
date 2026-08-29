import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import numpy as np

class YahooDataAnalyzer:
    def __init__(self):
        self.data = {}
    
    def fetch_stock_data(self, symbols: list, period: str = '1y') -> None:
        """
        获取股票数据
        :param symbols: 股票代码列表 ['AAPL', 'MSFT', etc.]
        :param period: 时间范围 ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
        """
        for symbol in symbols:
            try:
                print(f"\n获取 {symbol} 的数据...")
                ticker = yf.Ticker(symbol)
                
                # 获取历史数据
                self.data[symbol] = {
                    'history': ticker.history(period=period),
                    'info': ticker.info,
                    'financials': ticker.financials,
                    'balance_sheet': ticker.balance_sheet,
                    'cashflow': ticker.cashflow
                }
                print(f"成功获取 {symbol} 的数据")
                
            except Exception as e:
                print(f"获取 {symbol} 数据时出错: {str(e)}")

    def analyze_stock(self, symbol: str) -> None:
        """分析单个股票"""
        if symbol not in self.data:
            print(f"没有找到 {symbol} 的数据")
            return
        
        stock_data = self.data[symbol]
        history = stock_data['history']
        info = stock_data['info']
        
        print(f"\n=== {symbol} 分析报告 ===")
        
        # 1. 基本信息
        print("\n基本信息:")
        print(f"公司名称: {info.get('longName', 'N/A')}")
        print(f"行业: {info.get('industry', 'N/A')}")
        print(f"市值: ${info.get('marketCap', 0)/1e9:.2f}B")
        print(f"PE比率: {info.get('trailingPE', 'N/A')}")
        print(f"52周最高: ${info.get('fiftyTwoWeekHigh', 'N/A')}")
        print(f"52周最低: ${info.get('fiftyTwoWeekLow', 'N/A')}")
        
        # 2. 技术指标
        # 计算移动平均线
        history['MA20'] = history['Close'].rolling(window=20).mean()
        history['MA50'] = history['Close'].rolling(window=50).mean()
        
        # 计算RSI
        delta = history['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        history['RSI'] = 100 - (100 / (1 + rs))
        
        print("\n技术指标 (最新):")
        print(f"收盘价: ${history['Close'][-1]:.2f}")
        print(f"20日均线: ${history['MA20'][-1]:.2f}")
        print(f"50日均线: ${history['MA50'][-1]:.2f}")
        print(f"RSI: {history['RSI'][-1]:.2f}")
        
        # 3. 绘制图表
        plt.figure(figsize=(15, 10))
        
        # 价格和均线
        plt.subplot(2, 1, 1)
        plt.plot(history.index, history['Close'], label='价格')
        plt.plot(history.index, history['MA20'], label='MA20')
        plt.plot(history.index, history['MA50'], label='MA50')
        plt.title(f'{symbol} 价格走势')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # 成交量
        plt.subplot(2, 1, 2)
        plt.bar(history.index, history['Volume'])
        plt.title('成交量')
        plt.xlabel('日期')
        plt.ylabel('成交量')
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()

def main():
    # 设置要分析的股票
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
    
    # 创建分析器实例
    analyzer = YahooDataAnalyzer()
    
    # 获取数据
    analyzer.fetch_stock_data(symbols)
    
    # 分析每只股票
    for symbol in symbols:
        analyzer.analyze_stock(symbol)
        
        # 等待用户按Enter继续
        input("\n按Enter继续下一个分析...")

if __name__ == "__main__":
    # 设置pandas显示选项
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.float_format', lambda x: '%.2f' % x)
    
    main() 