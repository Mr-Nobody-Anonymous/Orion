from data_service.fetchers import BinanceFetcher
import pandas as pd
pd.set_option('display.max_rows', 10)

def main():
    # 初始化 fetcher (不需要 API key)
    fetcher = BinanceFetcher()
    
    try:
        # 获取 BTC 当前价格
        btc_price = fetcher.get_current_price("BTCUSD")
        print(f"\nBTC 当前价格: ${btc_price:,.2f}")
        
        # 获取历史K线数据
        df = fetcher.fetch_historical_data(
            symbol="BTCUSD",
            interval="1h"  # 1小时K线
        )
        print("\n历史数据最后5条:")
        print(df.tail())
        
        # 获取市场深度
        depth = fetcher.get_market_depth("BTCUSD", limit=5)
        print("\n市场深度:")
        print("买盘:", depth['bids'])
        print("卖盘:", depth['asks'])
        
    except Exception as e:
        print(f"错误: {str(e)}")

if __name__ == "__main__":
    main() 