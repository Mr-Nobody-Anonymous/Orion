#!/usr/bin/env python3
"""
Plotly Chart Generator
Advanced interactive charts for trading analysis
"""

import plotly.graph_objects as go
import plotly.express as px
import plotly.subplots as sp
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

class PlotlyChartGenerator:
    """Generate interactive Plotly charts for trading analysis"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Chart themes
        self.themes = {
            'light': {
                'bgcolor': '#ffffff',
                'textcolor': '#2c3e50',
                'gridcolor': '#ecf0f1',
                'up_color': '#27ae60',
                'down_color': '#e74c3c'
            },
            'dark': {
                'bgcolor': '#1a1a1a',
                'textcolor': '#ffffff',
                'gridcolor': '#2c2c2c',
                'up_color': '#00ff88',
                'down_color': '#ff4444'
            }
        }
        
        self.current_theme = 'light'
    
    def create_candlestick_chart(self, 
                                data: pd.DataFrame,
                                symbol: str,
                                title: str = None,
                                theme: str = 'light') -> go.Figure:
        """Create interactive candlestick chart"""
        
        if title is None:
            title = f"{symbol} Price Chart"
        
        colors = self.themes[theme]
        
        fig = go.Figure()
        
        # Add candlestick
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name=symbol,
            increasing_line_color=colors['up_color'],
            decreasing_line_color=colors['down_color'],
            increasing_fillcolor=colors['up_color'],
            decreasing_fillcolor=colors['down_color']
        ))
        
        # Add volume bars
        if 'volume' in data.columns:
            fig.add_trace(go.Bar(
                x=data.index,
                y=data['volume'],
                name='Volume',
                yaxis='y2',
                opacity=0.3,
                marker_color='#3498db'
            ))
        
        # Update layout
        fig.update_layout(
            title=title,
            xaxis_title='Date',
            yaxis_title='Price',
            template='plotly_white',
            height=600,
            plot_bgcolor=colors['bgcolor'],
            paper_bgcolor=colors['bgcolor'],
            font=dict(color=colors['textcolor']),
            xaxis=dict(
                gridcolor=colors['gridcolor'],
                rangeslider=dict(visible=False)
            ),
            yaxis=dict(
                gridcolor=colors['gridcolor'],
                side='left'
            ),
            yaxis2=dict(
                title='Volume',
                overlaying='y',
                side='right',
                showgrid=False
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        return fig
    
    def create_technical_analysis_chart(self,
                                      data: pd.DataFrame,
                                      symbol: str,
                                      indicators: List[str] = None) -> go.Figure:
        """Create technical analysis chart with indicators"""
        
        if indicators is None:
            indicators = ['sma', 'ema', 'bollinger']
        
        colors = self.themes[self.current_theme]
        
        # Create subplots
        fig = sp.make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            subplot_titles=(f'{symbol} Price & Indicators', 'Volume', 'RSI'),
            row_heights=[0.6, 0.2, 0.2]
        )
        
        # Price candlestick
        fig.add_trace(go.Candlestick(
            x=data.index,
            open=data['open'],
            high=data['high'],
            low=data['low'],
            close=data['close'],
            name=symbol,
            increasing_line_color=colors['up_color'],
            decreasing_line_color=colors['down_color']
        ), row=1, col=1)
        
        # Add indicators
        if 'sma' in indicators and 'sma_20' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['sma_20'],
                name='SMA 20',
                line=dict(color='#e74c3c', width=2)
            ), row=1, col=1)
        
        if 'ema' in indicators and 'ema_20' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['ema_20'],
                name='EMA 20',
                line=dict(color='#f39c12', width=2)
            ), row=1, col=1)
        
        if 'bollinger' in indicators and 'bb_upper' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['bb_upper'],
                name='BB Upper',
                line=dict(color='#9b59b6', width=1, dash='dash')
            ), row=1, col=1)
            
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['bb_lower'],
                name='BB Lower',
                line=dict(color='#9b59b6', width=1, dash='dash'),
                fill='tonexty',
                fillcolor='rgba(155, 89, 182, 0.1)'
            ), row=1, col=1)
        
        # Volume
        if 'volume' in data.columns:
            fig.add_trace(go.Bar(
                x=data.index,
                y=data['volume'],
                name='Volume',
                marker_color='#3498db',
                opacity=0.7
            ), row=2, col=1)
        
        # RSI
        if 'rsi' in data.columns:
            fig.add_trace(go.Scatter(
                x=data.index,
                y=data['rsi'],
                name='RSI',
                line=dict(color='#e67e22', width=2)
            ), row=3, col=1)
            
            # Add RSI overbought/oversold lines
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)
        
        # Update layout
        fig.update_layout(
            title=f'{symbol} Technical Analysis',
            height=800,
            showlegend=True,
            template='plotly_white'
        )
        
        return fig
    
    def create_factor_analysis_chart(self,
                                   factor_data: pd.DataFrame,
                                   factor_names: List[str]) -> go.Figure:
        """Create factor analysis visualization"""
        
        colors = self.themes[self.current_theme]
        
        fig = sp.make_subplots(
            rows=2, cols=2,
            subplot_titles=('Factor Performance', 'Factor Correlation', 
                          'Factor Returns', 'Factor Weights'),
            specs=[[{"secondary_y": False}, {"secondary_y": False}],
                   [{"secondary_y": False}, {"secondary_y": False}]]
        )
        
        # Factor performance over time
        for factor in factor_names:
            if factor in factor_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=factor_data.index,
                        y=factor_data[factor],
                        mode='lines',
                        name=factor,
                        line=dict(width=2)
                    ),
                    row=1, col=1
                )
        
        # Factor correlation heatmap
        corr_matrix = factor_data[factor_names].corr()
        fig.add_trace(
            go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.columns,
                colorscale='RdBu',
                zmid=0,
                colorbar=dict(title="Correlation")
            ),
            row=1, col=2
        )
        
        # Factor returns (assuming we have returns data)
        if 'returns' in factor_data.columns:
            fig.add_trace(
                go.Bar(
                    x=factor_names,
                    y=[factor_data[f].mean() for f in factor_names if f in factor_data.columns],
                    name='Factor Returns',
                    marker_color='#1f77b4'
                ),
                row=2, col=1
            )
        
        # Factor weights (equal weights for demo)
        weights = [1/len(factor_names)] * len(factor_names)
        fig.add_trace(
            go.Pie(
                labels=factor_names,
                values=weights,
                name='Factor Weights'
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title='Factor Analysis Dashboard',
            height=600,
            template='plotly_white'
        )
        
        return fig
    
    def create_portfolio_performance_chart(self,
                                         equity_curve: pd.Series,
                                         benchmark: pd.Series = None,
                                         trades: pd.DataFrame = None) -> go.Figure:
        """Create portfolio performance chart"""
        
        colors = self.themes[self.current_theme]
        
        fig = sp.make_subplots(
            rows=2, cols=1,
            subplot_titles=('Portfolio Performance', 'Drawdown'),
            vertical_spacing=0.1
        )
        
        # Equity curve
        fig.add_trace(go.Scatter(
            x=equity_curve.index,
            y=equity_curve.values,
            mode='lines',
            name='Portfolio',
            line=dict(color=colors['up_color'], width=2)
        ), row=1, col=1)
        
        if benchmark is not None:
            fig.add_trace(go.Scatter(
                x=benchmark.index,
                y=benchmark.values,
                mode='lines',
                name='Benchmark',
                line=dict(color=colors['down_color'], width=2, dash='dash')
            ), row=1, col=1)
        
        # Add trade markers if available
        if trades is not None and not trades.empty:
            # Buy trades
            buy_trades = trades[trades['side'] == 'buy']
            if not buy_trades.empty:
                fig.add_trace(go.Scatter(
                    x=buy_trades['timestamp'],
                    y=buy_trades['price'],
                    mode='markers',
                    name='Buy Trades',
                    marker=dict(
                        color='green',
                        size=8,
                        symbol='triangle-up'
                    )
                ), row=1, col=1)
            
            # Sell trades
            sell_trades = trades[trades['side'] == 'sell']
            if not sell_trades.empty:
                fig.add_trace(go.Scatter(
                    x=sell_trades['timestamp'],
                    y=sell_trades['price'],
                    mode='markers',
                    name='Sell Trades',
                    marker=dict(
                        color='red',
                        size=8,
                        symbol='triangle-down'
                    )
                ), row=1, col=1)
        
        # Drawdown
        returns = equity_curve.pct_change().dropna()
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values * 100,
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(231, 76, 60, 0.3)',
            line=dict(color='red', width=2),
            name='Drawdown'
        ), row=2, col=1)
        
        fig.update_layout(
            title='Portfolio Performance Analysis',
            height=700,
            template='plotly_white'
        )
        
        return fig
    
    def create_real_time_chart(self,
                              symbol: str,
                              data: List[Dict[str, Any]]) -> go.Figure:
        """Create real-time updating chart"""
        
        colors = self.themes[self.current_theme]
        
        fig = go.Figure()
        
        # Extract data
        timestamps = [d['timestamp'] for d in data]
        prices = [d['price'] for d in data]
        volumes = [d.get('volume', 0) for d in data]
        
        # Price line
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=prices,
            mode='lines+markers',
            name=f'{symbol} Price',
            line=dict(color=colors['up_color'], width=2),
            marker=dict(size=4)
        ))
        
        # Volume bars
        fig.add_trace(go.Bar(
            x=timestamps,
            y=volumes,
            name='Volume',
            yaxis='y2',
            opacity=0.3,
            marker_color='#3498db'
        ))
        
        fig.update_layout(
            title=f'{symbol} Real-time Data',
            xaxis_title='Time',
            yaxis_title='Price',
            yaxis2=dict(
                title='Volume',
                overlaying='y',
                side='right',
                showgrid=False
            ),
            template='plotly_white',
            height=500,
            uirevision=True  # Preserve zoom level on updates
        )
        
        return fig
    
    def create_heatmap_chart(self,
                           data: pd.DataFrame,
                           x_col: str,
                           y_col: str,
                           value_col: str,
                           title: str = "Heatmap") -> go.Figure:
        """Create heatmap chart"""
        
        fig = go.Figure(data=go.Heatmap(
            z=data.pivot_table(
                index=y_col, 
                columns=x_col, 
                values=value_col, 
                aggfunc='mean'
            ).values,
            x=data[x_col].unique(),
            y=data[y_col].unique(),
            colorscale='Viridis',
            colorbar=dict(title=value_col)
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_col,
            yaxis_title=y_col,
            template='plotly_white',
            height=500
        )
        
        return fig
    
    def create_3d_surface_chart(self,
                              x_data: np.ndarray,
                              y_data: np.ndarray,
                              z_data: np.ndarray,
                              title: str = "3D Surface") -> go.Figure:
        """Create 3D surface chart"""
        
        fig = go.Figure(data=go.Surface(
            x=x_data,
            y=y_data,
            z=z_data,
            colorscale='Viridis'
        ))
        
        fig.update_layout(
            title=title,
            scene=dict(
                xaxis_title='X',
                yaxis_title='Y',
                zaxis_title='Z'
            ),
            template='plotly_white',
            height=600
        )
        
        return fig
    
    def export_chart(self, fig: go.Figure, filename: str, format: str = 'html'):
        """Export chart to file"""
        try:
            if format == 'html':
                fig.write_html(filename)
            elif format == 'png':
                fig.write_image(filename)
            elif format == 'pdf':
                fig.write_image(filename)
            else:
                raise ValueError(f"Unsupported format: {format}")
            
            self.logger.info(f"Chart exported to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to export chart: {e}")
            raise 