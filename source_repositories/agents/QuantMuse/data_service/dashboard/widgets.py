import streamlit as st
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
import logging

class DashboardWidgets:
    """Interactive widgets for trading dashboard"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def sidebar_filters(self) -> Dict[str, Any]:
        """Create sidebar filters"""
        st.sidebar.header("📊 Dashboard Filters")
        
        # Date range selector
        st.sidebar.subheader("📅 Date Range")
        date_range = st.sidebar.date_input(
            "Select Date Range",
            value=(datetime.now() - timedelta(days=365), datetime.now()),
            max_value=datetime.now()
        )
        
        # Strategy selector
        st.sidebar.subheader("🎯 Strategy")
        strategies = ["Momentum", "Value", "Quality", "Multi-Factor", "Mean Reversion"]
        selected_strategy = st.sidebar.selectbox(
            "Select Strategy",
            strategies,
            index=0
        )
        
        # Symbol selector
        st.sidebar.subheader("📈 Symbols")
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN", "NVDA", "META", "NFLX"]
        selected_symbols = st.sidebar.multiselect(
            "Select Symbols",
            symbols,
            default=["AAPL", "GOOGL", "MSFT"]
        )
        
        # Timeframe selector
        st.sidebar.subheader("⏰ Timeframe")
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
        selected_timeframe = st.sidebar.selectbox(
            "Select Timeframe",
            timeframes,
            index=5  # Default to 1d
        )
        
        # Risk level selector
        st.sidebar.subheader("⚠️ Risk Level")
        risk_level = st.sidebar.slider(
            "Risk Tolerance",
            min_value=1,
            max_value=10,
            value=5,
            help="1 = Conservative, 10 = Aggressive"
        )
        
        return {
            'date_range': date_range,
            'strategy': selected_strategy,
            'symbols': selected_symbols,
            'timeframe': selected_timeframe,
            'risk_level': risk_level
        }
    
    def performance_metrics_cards(self, metrics: Dict[str, float]):
        """Display performance metrics as cards"""
        st.subheader("📈 Performance Metrics")
        
        # Create columns for metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Total Return",
                value=f"{metrics.get('total_return', 0):.2%}",
                delta=f"{metrics.get('daily_return', 0):.2%}"
            )
        
        with col2:
            st.metric(
                label="Sharpe Ratio",
                value=f"{metrics.get('sharpe_ratio', 0):.2f}",
                delta=f"{metrics.get('sharpe_change', 0):.2f}"
            )
        
        with col3:
            st.metric(
                label="Max Drawdown",
                value=f"{metrics.get('max_drawdown', 0):.2%}",
                delta=f"{metrics.get('drawdown_change', 0):.2%}"
            )
        
        with col4:
            st.metric(
                label="Win Rate",
                value=f"{metrics.get('win_rate', 0):.2%}",
                delta=f"{metrics.get('win_rate_change', 0):.2%}"
            )
    
    def portfolio_summary(self, portfolio_data: Dict[str, Any]):
        """Display portfolio summary"""
        st.subheader("💼 Portfolio Summary")
        
        # Portfolio value and P&L
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Total Value",
                value=f"${portfolio_data.get('total_value', 0):,.2f}",
                delta=f"${portfolio_data.get('daily_pnl', 0):,.2f}"
            )
        
        with col2:
            st.metric(
                label="Cash",
                value=f"${portfolio_data.get('cash', 0):,.2f}",
                delta=f"${portfolio_data.get('cash_change', 0):,.2f}"
            )
        
        with col3:
            st.metric(
                label="Positions",
                value=f"{portfolio_data.get('num_positions', 0)}",
                delta=f"{portfolio_data.get('positions_change', 0)}"
            )
        
        # Positions table
        if 'positions' in portfolio_data and portfolio_data['positions']:
            st.subheader("📋 Current Positions")
            positions_df = pd.DataFrame(portfolio_data['positions']).T
            positions_df['Unrealized P&L'] = positions_df['unrealized_pnl']
            positions_df['Unrealized P&L %'] = positions_df['unrealized_pnl_pct']
            
            # Format columns
            positions_df['Quantity'] = positions_df['quantity'].astype(int)
            positions_df['Avg Price'] = positions_df['avg_price'].round(2)
            positions_df['Current Price'] = positions_df['current_price'].round(2)
            positions_df['Unrealized P&L'] = positions_df['Unrealized P&L'].round(2)
            positions_df['Unrealized P&L %'] = positions_df['Unrealized P&L %'].round(2)
            
            st.dataframe(
                positions_df[['Quantity', 'Avg Price', 'Current Price', 'Unrealized P&L', 'Unrealized P&L %']],
                use_container_width=True
            )
    
    def real_time_data_widget(self, symbol: str, price_data: pd.DataFrame):
        """Display real-time price data"""
        st.subheader(f"📊 {symbol} Real-Time Data")
        
        # Current price and change
        current_price = price_data['close'].iloc[-1]
        prev_price = price_data['close'].iloc[-2]
        price_change = current_price - prev_price
        price_change_pct = (price_change / prev_price) * 100
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="Current Price",
                value=f"${current_price:.2f}",
                delta=f"{price_change_pct:.2f}%"
            )
        
        with col2:
            st.metric(
                label="Volume",
                value=f"{price_data['volume'].iloc[-1]:,.0f}"
            )
        
        with col3:
            st.metric(
                label="High",
                value=f"${price_data['high'].iloc[-1]:.2f}"
            )
        
        with col4:
            st.metric(
                label="Low",
                value=f"${price_data['low'].iloc[-1]:.2f}"
            )
    
    def strategy_controls(self, strategies: List[str]) -> Dict[str, Any]:
        """Strategy control panel"""
        st.subheader("🎮 Strategy Controls")
        
        # Strategy selection
        selected_strategy = st.selectbox(
            "Active Strategy",
            strategies,
            index=0
        )
        
        # Strategy parameters
        st.subheader("⚙️ Strategy Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            lookback_period = st.slider(
                "Lookback Period (days)",
                min_value=5,
                max_value=252,
                value=60,
                step=5
            )
            
            position_size = st.slider(
                "Position Size (%)",
                min_value=1,
                max_value=20,
                value=5,
                step=1
            )
        
        with col2:
            stop_loss = st.slider(
                "Stop Loss (%)",
                min_value=1,
                max_value=20,
                value=10,
                step=1
            )
            
            take_profit = st.slider(
                "Take Profit (%)",
                min_value=5,
                max_value=50,
                value=20,
                step=5
            )
        
        # Strategy actions
        st.subheader("🚀 Strategy Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            start_strategy = st.button("▶️ Start Strategy", type="primary")
        
        with col2:
            pause_strategy = st.button("⏸️ Pause Strategy")
        
        with col3:
            stop_strategy = st.button("⏹️ Stop Strategy")
        
        return {
            'strategy': selected_strategy,
            'lookback_period': lookback_period,
            'position_size': position_size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'start': start_strategy,
            'pause': pause_strategy,
            'stop': stop_strategy
        }
    
    def order_management(self, orders: pd.DataFrame):
        """Order management interface"""
        st.subheader("📋 Order Management")
        
        # Order status summary
        if not orders.empty:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_orders = len(orders)
                st.metric("Total Orders", total_orders)
            
            with col2:
                pending_orders = len(orders[orders['status'] == 'pending'])
                st.metric("Pending", pending_orders)
            
            with col3:
                filled_orders = len(orders[orders['status'] == 'filled'])
                st.metric("Filled", filled_orders)
            
            with col4:
                cancelled_orders = len(orders[orders['status'] == 'cancelled'])
                st.metric("Cancelled", cancelled_orders)
            
            # Orders table
            st.subheader("📊 Recent Orders")
            
            # Format orders for display
            display_orders = orders.copy()
            display_orders['timestamp'] = pd.to_datetime(display_orders['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            display_orders['price'] = display_orders['price'].round(2)
            display_orders['quantity'] = display_orders['quantity'].round(2)
            
            st.dataframe(
                display_orders[['timestamp', 'symbol', 'side', 'quantity', 'price', 'status']],
                use_container_width=True
            )
        else:
            st.info("No orders found.")
    
    def risk_management_panel(self, risk_metrics: Dict[str, float]):
        """Risk management panel"""
        st.subheader("⚠️ Risk Management")
        
        # Risk metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label="VaR (95%)",
                value=f"{risk_metrics.get('var_95', 0):.2%}",
                delta=f"{risk_metrics.get('var_change', 0):.2%}"
            )
        
        with col2:
            st.metric(
                label="CVaR (95%)",
                value=f"{risk_metrics.get('cvar_95', 0):.2%}",
                delta=f"{risk_metrics.get('cvar_change', 0):.2%}"
            )
        
        with col3:
            st.metric(
                label="Beta",
                value=f"{risk_metrics.get('beta', 0):.2f}",
                delta=f"{risk_metrics.get('beta_change', 0):.2f}"
            )
        
        with col4:
            st.metric(
                label="Correlation",
                value=f"{risk_metrics.get('correlation', 0):.2f}",
                delta=f"{risk_metrics.get('correlation_change', 0):.2f}"
            )
        
        # Risk limits
        st.subheader("🎯 Risk Limits")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_position_size = st.number_input(
                "Max Position Size (%)",
                min_value=1.0,
                max_value=50.0,
                value=10.0,
                step=1.0
            )
            
            max_daily_loss = st.number_input(
                "Max Daily Loss (%)",
                min_value=1.0,
                max_value=20.0,
                value=5.0,
                step=0.5
            )
        
        with col2:
            max_leverage = st.number_input(
                "Max Leverage",
                min_value=1.0,
                max_value=5.0,
                value=2.0,
                step=0.1
            )
            
            max_drawdown = st.number_input(
                "Max Drawdown (%)",
                min_value=5.0,
                max_value=50.0,
                value=20.0,
                step=1.0
            )
        
        return {
            'max_position_size': max_position_size,
            'max_daily_loss': max_daily_loss,
            'max_leverage': max_leverage,
            'max_drawdown': max_drawdown
        }
    
    def alerts_panel(self, alerts: List[Dict[str, Any]]):
        """Alerts and notifications panel"""
        st.subheader("🔔 Alerts & Notifications")
        
        if alerts:
            for alert in alerts:
                alert_type = alert.get('type', 'info')
                message = alert.get('message', '')
                timestamp = alert.get('timestamp', '')
                
                if alert_type == 'error':
                    st.error(f"🚨 {message} - {timestamp}")
                elif alert_type == 'warning':
                    st.warning(f"⚠️ {message} - {timestamp}")
                elif alert_type == 'success':
                    st.success(f"✅ {message} - {timestamp}")
                else:
                    st.info(f"ℹ️ {message} - {timestamp}")
        else:
            st.info("No active alerts.")
        
        # Alert settings
        st.subheader("⚙️ Alert Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            price_alerts = st.checkbox("Price Alerts", value=True)
            volume_alerts = st.checkbox("Volume Alerts", value=True)
            risk_alerts = st.checkbox("Risk Alerts", value=True)
        
        with col2:
            strategy_alerts = st.checkbox("Strategy Alerts", value=True)
            order_alerts = st.checkbox("Order Alerts", value=True)
            system_alerts = st.checkbox("System Alerts", value=True)
    
    def data_export_widget(self, data: Dict[str, pd.DataFrame]):
        """Data export widget"""
        st.subheader("📤 Data Export")
        
        # Export options
        export_options = st.multiselect(
            "Select data to export",
            ["Performance Data", "Trade History", "Portfolio Data", "Risk Metrics", "Factor Data"],
            default=["Performance Data", "Trade History"]
        )
        
        # Export format
        export_format = st.selectbox(
            "Export Format",
            ["CSV", "Excel", "JSON"],
            index=0
        )
        
        # Export button
        if st.button("📥 Export Data"):
            st.success("Data export initiated!")
            # Here you would implement the actual export logic
    
    def settings_panel(self) -> Dict[str, Any]:
        """Settings panel"""
        st.subheader("⚙️ Settings")
        
        # Display settings
        st.subheader("🎨 Display Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            theme = st.selectbox(
                "Theme",
                ["Light", "Dark"],
                index=0
            )
            
            chart_height = st.slider(
                "Chart Height",
                min_value=300,
                max_value=800,
                value=400,
                step=50
            )
        
        with col2:
            auto_refresh = st.checkbox("Auto Refresh", value=True)
            refresh_interval = st.selectbox(
                "Refresh Interval",
                ["5s", "10s", "30s", "1m", "5m"],
                index=1
            )
        
        # Data settings
        st.subheader("📊 Data Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            max_data_points = st.number_input(
                "Max Data Points",
                min_value=100,
                max_value=10000,
                value=1000,
                step=100
            )
            
            cache_duration = st.number_input(
                "Cache Duration (minutes)",
                min_value=1,
                max_value=60,
                value=5,
                step=1
            )
        
        with col2:
            enable_real_time = st.checkbox("Enable Real-time Data", value=True)
            enable_notifications = st.checkbox("Enable Notifications", value=True)
        
        return {
            'theme': theme,
            'chart_height': chart_height,
            'auto_refresh': auto_refresh,
            'refresh_interval': refresh_interval,
            'max_data_points': max_data_points,
            'cache_duration': cache_duration,
            'enable_real_time': enable_real_time,
            'enable_notifications': enable_notifications
        } 