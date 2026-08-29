from data_service import BinanceFetcher, DataProcessor
import pandas as pd
from data_service.utils.logger import setup_logger

def main():
    # 设置日志
    logger = setup_logger("crypto_data")
    
    try:
        # 1. 初始化 Binance 数据获取器
        fetcher = BinanceFetcher()
        
        # 2. 初始化数据处理器
        processor = DataProcessor()
        
        # 3. 获取 BTC 数据
        logger.info("正在获取 BTC 数据...")
        
        # 获取当前价格
        btc_price = fetcher.get_current_price("BTCUSD")
        print(f"\nBTC 当前价格: ${btc_price:,.2f}")
        
        # 获取历史K线数据
        df = fetcher.fetch_historical_data(
            symbol="BTCUSD",
            interval="1h"  # 1小时K线
        )
        print("\n历史数据最后5条:")
        print(df.tail())
        
        # 4. 处理数据
        processed_data = processor.process_market_data(df)
        
        # 5. 打印分析结果
        print("\n=== 市场统计 ===")
        for key, value in processed_data.statistics.items():
            print(f"{key}: {value:.4f}")
        
        print("\n=== 交易信号 ===")
        for key, value in processed_data.signals.items():
            print(f"{key}: {value}")
        
        # 6. 获取市场深度
        depth = fetcher.get_market_depth("BTCUSD", limit=5)
        print("\n=== 市场深度 ===")
        print("买盘:", depth['bids'])
        print("卖盘:", depth['asks'])
        
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main() 