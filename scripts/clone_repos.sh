#!/bin/bash

# ============================================================
# Orion - Master Repository Cloner
# Clones all known trading/ML/finance repos into external_repos/
# ============================================================

set -e

EXTERNAL_DIR="external_repos"
mkdir -p $EXTERNAL_DIR

echo "========================================"
echo " Orion Repository Cloner Starting..."
echo "========================================"

# ============================================================
# BACKTESTING FRAMEWORKS
# ============================================================
echo "[1/10] Cloning Backtesting Frameworks..."

git clone https://github.com/mementum/backtrader.git $EXTERNAL_DIR/backtrader
git clone https://github.com/quantopian/zipline.git $EXTERNAL_DIR/zipline
git clone https://github.com/gbeced/pyalgotrade.git $EXTERNAL_DIR/pyalgotrade
git clone https://github.com/polakowo/vectorbt.git $EXTERNAL_DIR/vectorbt
git clone https://github.com/pmorissette/bt.git $EXTERNAL_DIR/bt
git clone https://github.com/kernc/backtesting.py.git $EXTERNAL_DIR/backtesting_py
git clone https://github.com/trading-engineers/quantstats.git $EXTERNAL_DIR/quantstats
git clone https://github.com/wilsonfreitas/awesome-quant.git $EXTERNAL_DIR/awesome_quant

# ============================================================
# ML / AI TRADING
# ============================================================
echo "[2/10] Cloning ML/AI Trading Repos..."

git clone https://github.com/AI4Finance-Foundation/FinRL.git $EXTERNAL_DIR/FinRL
git clone https://github.com/AI4Finance-Foundation/FinRL-Meta.git $EXTERNAL_DIR/FinRL_Meta
git clone https://github.com/AI4Finance-Foundation/FinGPT.git $EXTERNAL_DIR/FinGPT
git clone https://github.com/huseinzol05/Stock-Prediction-Models.git $EXTERNAL_DIR/Stock_Prediction_Models
git clone https://github.com/microsoft/qlib.git $EXTERNAL_DIR/qlib
git clone https://github.com/google/tf-quant-finance.git $EXTERNAL_DIR/tf_quant_finance
git clone https://github.com/pskrunner14/trading-bot.git $EXTERNAL_DIR/trading_bot
git clone https://github.com/nicehash/NiceHashQuickMiner.git $EXTERNAL_DIR/nicehash || true

# ============================================================
# RISK MANAGEMENT
# ============================================================
echo "[3/10] Cloning Risk Management Repos..."

git clone https://github.com/riskprofiler/PyPortfolioOpt.git $EXTERNAL_DIR/PyPortfolioOpt || \
git clone https://github.com/robertmartin8/PyPortfolioOpt.git $EXTERNAL_DIR/PyPortfolioOpt
git clone https://github.com/dcajasn/Riskfolio-Lib.git $EXTERNAL_DIR/Riskfolio_Lib
git clone https://github.com/portfolioplus/pystockfilter.git $EXTERNAL_DIR/pystockfilter
git clone https://github.com/quantopian/empyrical.git $EXTERNAL_DIR/empyrical
git clone https://github.com/hudson-and-thames/mlfinlab.git $EXTERNAL_DIR/mlfinlab
git clone https://github.com/ranaroussi/quantstats.git $EXTERNAL_DIR/quantstats2

# ============================================================
# PORTFOLIO OPTIMIZATION
# ============================================================
echo "[4/10] Cloning Portfolio Optimization Repos..."

git clone https://github.com/cvxpy/cvxpy.git $EXTERNAL_DIR/cvxpy
git clone https://github.com/pmorissette/ffn.git $EXTERNAL_DIR/ffn
git clone https://github.com/quantopian/alphalens.git $EXTERNAL_DIR/alphalens
git clone https://github.com/quantopian/pyfolio.git $EXTERNAL_DIR/pyfolio
git clone https://github.com/quantopian/trading-calendars.git $EXTERNAL_DIR/trading_calendars

# ============================================================
# DATA SOURCES
# ============================================================
echo "[5/10] Cloning Data Source Repos..."

git clone https://github.com/ranaroussi/yfinance.git $EXTERNAL_DIR/yfinance
git clone https://github.com/alpacahq/alpaca-trade-api-python.git $EXTERNAL_DIR/alpaca_api
git clone https://github.com/binance/binance-connector-python.git $EXTERNAL_DIR/binance_connector
git clone https://github.com/sammchardy/python-binance.git $EXTERNAL_DIR/python_binance
git clone https://github.com/polygon-io/client-python.git $EXTERNAL_DIR/polygon_io
git clone https://github.com/InteractiveBrokers/tws-api.git $EXTERNAL_DIR/ib_tws || true
git clone https://github.com/bfortuner/ml4trading.git $EXTERNAL_DIR/ml4trading

# ============================================================
# SENTIMENT & NLP
# ============================================================
echo "[6/10] Cloning Sentiment/NLP Repos..."

git clone https://github.com/ProsusAI/finbert.git $EXTERNAL_DIR/finbert
git clone https://github.com/yya518/FinBERT.git $EXTERNAL_DIR/finbert2
git clone https://github.com/oliverguhr/german-sentiment-lib.git $EXTERNAL_DIR/sentiment_lib || true
git clone https://github.com/twintproject/twint.git $EXTERNAL_DIR/twint || true

# ============================================================
# TECHNICAL ANALYSIS
# ============================================================
echo "[7/10] Cloning Technical Analysis Repos..."

git clone https://github.com/bukosabino/ta.git $EXTERNAL_DIR/ta
git clone https://github.com/twopirllc/pandas-ta.git $EXTERNAL_DIR/pandas_ta
git clone https://github.com/mrjbq7/ta-lib.git $EXTERNAL_DIR/ta_lib
git clone https://github.com/jealous/stockstats.git $EXTERNAL_DIR/stockstats
git clone https://github.com/peerchemist/finta.git $EXTERNAL_DIR/finta

# ============================================================
# EXECUTION / BROKERAGE
# ============================================================
echo "[8/10] Cloning Execution Repos..."

git clone https://github.com/ccxt/ccxt.git $EXTERNAL_DIR/ccxt
git clone https://github.com/freqtrade/freqtrade.git $EXTERNAL_DIR/freqtrade
git clone https://github.com/hummingbot/hummingbot.git $EXTERNAL_DIR/hummingbot
git clone https://github.com/tensortrade-org/tensortrade.git $EXTERNAL_DIR/tensortrade
git clone https://github.com/Drakkar-Software/OctoBot.git $EXTERNAL_DIR/octobot

# ============================================================
# QUANTITATIVE FINANCE
# ============================================================
echo "[9/10] Cloning Quant Finance Repos..."

git clone https://github.com/goldmansachs/gs-quant.git $EXTERNAL_DIR/gs_quant
git clone https://github.com/ratesquant/KSP.git $EXTERNAL_DIR/ksp || true
git clone https://github.com/quantlib/QuantLib-Python.git $EXTERNAL_DIR/quantlib || true
git clone https://github.com/jasonstrimpel/volatility-trading.git $EXTERNAL_DIR/vol_trading
git clone https://github.com/matplotlib/mplfinance.git $EXTERNAL_DIR/mplfinance
git clone https://github.com/kernc/backtesting.py $EXTERNAL_DIR/backtesting_py2 || true

# ============================================================
# REINFORCEMENT LEARNING
# ============================================================
echo "[10/10] Cloning RL Repos..."

git clone https://github.com/openai/gym.git $EXTERNAL_DIR/openai_gym
git clone https://github.com/DLR-RM/stable-baselines3.git $EXTERNAL_DIR/stable_baselines3
git clone https://github.com/tensortrade-org/tensortrade.git $EXTERNAL_DIR/tensortrade2 || true
git clone https://github.com/nicknochnack/TradingRL.git $EXTERNAL_DIR/trading_rl || true

echo ""
echo "========================================"
echo " All Repositories Cloned Successfully!"
echo "========================================"
echo "Total repos in external_repos/:"
ls $EXTERNAL_DIR | wc -l
