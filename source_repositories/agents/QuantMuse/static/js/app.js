// Trading System Dashboard - Main JavaScript Application

class TradingDashboard {
    constructor() {
        this.apiBaseUrl = '/api';
        this.currentPage = 'dashboard';
        this.charts = {};
        this.candlestickChart = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadDashboardData();
        this.setupCharts();
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigateToPage(e.target.getAttribute('data-page'));
            });
        });

        // Strategy form
        document.getElementById('save-strategy')?.addEventListener('click', () => {
            this.saveStrategy();
        });

        // Backtest form
        document.getElementById('backtest-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.runBacktest();
        });

        // Sentiment analysis form
        document.getElementById('sentiment-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.analyzeSentiment();
        });

        // Market analysis form
        document.getElementById('market-analysis-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.analyzeMarket();
        });

        // Chart controls
        document.getElementById('load-chart-btn')?.addEventListener('click', () => {
            this.loadCandlestickChart();
        });

        // Technical indicators
        document.querySelectorAll('input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateChartIndicators();
            });
        });

        // Auto-refresh dashboard every 30 seconds
        setInterval(() => {
            if (this.currentPage === 'dashboard') {
                this.loadDashboardData();
            }
        }, 30000);
    }

    navigateToPage(page) {
        // Hide all pages
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        
        // Show target page
        document.getElementById(`${page}-page`).classList.add('active');
        
        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => link.classList.remove('active'));
        document.querySelector(`[data-page="${page}"]`).classList.add('active');
        
        this.currentPage = page;
        
        // Load page-specific data
        switch (page) {
            case 'dashboard':
                this.loadDashboardData();
                break;
            case 'strategies':
                this.loadStrategies();
                break;
            case 'portfolio':
                this.loadPortfolioData();
                break;
            case 'charts':
                this.initCandlestickChart();
                this.loadCandlestickChart();
                break;
        }
    }

    async loadDashboardData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/system/status`);
            const data = await response.json();
            
            this.updateDashboardMetrics(data);
            this.loadRecentActivity();
            this.loadRecentTrades();
            
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
            this.showError('Failed to load dashboard data');
        }
    }

    updateDashboardMetrics(data) {
        // Update system status
        document.getElementById('system-status').textContent = data.status;
        document.getElementById('uptime').textContent = data.uptime;
        document.getElementById('active-strategies').textContent = data.active_strategies;
        document.getElementById('total-trades').textContent = data.total_trades.toLocaleString();
        
        // Update performance metrics
        if (data.performance_metrics) {
            document.getElementById('total-return').textContent = `${(data.performance_metrics.total_return * 100).toFixed(1)}%`;
            document.getElementById('sharpe-ratio').textContent = data.performance_metrics.sharpe_ratio.toFixed(1);
            document.getElementById('max-drawdown').textContent = `${(data.performance_metrics.max_drawdown * 100).toFixed(1)}%`;
            document.getElementById('win-rate').textContent = `${(data.performance_metrics.win_rate * 100).toFixed(1)}%`;
        }
        
        // Update risk metrics
        if (data.risk_metrics) {
            document.getElementById('var-95').textContent = `${(data.risk_metrics.var_95 * 100).toFixed(1)}%`;
            document.getElementById('cvar-95').textContent = `${(data.risk_metrics.cvar_95 * 100).toFixed(1)}%`;
            document.getElementById('beta').textContent = data.risk_metrics.beta.toFixed(2);
            document.getElementById('volatility').textContent = `${(data.risk_metrics.volatility * 100).toFixed(1)}%`;
        }
    }

    async loadRecentActivity() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/dashboard/activity`);
            const activities = await response.json();
            
            const activityList = document.getElementById('activity-list');
            activityList.innerHTML = '';
            
            activities.forEach(activity => {
                const activityItem = this.createActivityItem(activity);
                activityList.appendChild(activityItem);
            });
            
        } catch (error) {
            console.error('Failed to load recent activity:', error);
        }
    }

    createActivityItem(activity) {
        const div = document.createElement('div');
        div.className = 'activity-item fade-in';
        
        const iconClass = this.getActivityIconClass(activity.type);
        
        div.innerHTML = `
            <div class="activity-icon ${activity.type}">
                <i class="${iconClass}"></i>
            </div>
            <div class="activity-content">
                <div class="activity-title">${activity.description}</div>
                <div class="activity-time">${this.formatTime(activity.timestamp)}</div>
            </div>
        `;
        
        return div;
    }

    getActivityIconClass(type) {
        const icons = {
            'trade': 'bx bx-transfer',
            'strategy': 'bx bx-cog',
            'alert': 'bx bx-error',
            'system': 'bx bx-server'
        };
        return icons[type] || 'bx bx-info-circle';
    }

    async loadRecentTrades() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/trades/recent?limit=10`);
            const data = await response.json();
            
            const tradesTable = document.getElementById('trades-table');
            tradesTable.innerHTML = '';
            
            data.trades.forEach(trade => {
                const row = this.createTradeRow(trade);
                tradesTable.appendChild(row);
            });
            
        } catch (error) {
            console.error('Failed to load recent trades:', error);
        }
    }

    createTradeRow(trade) {
        const row = document.createElement('tr');
        row.className = 'fade-in';
        
        const sideClass = trade.side === 'buy' ? 'text-success' : 'text-danger';
        const sideIcon = trade.side === 'buy' ? 'bx bx-up-arrow-alt' : 'bx bx-down-arrow-alt';
        
        row.innerHTML = `
            <td>${this.formatTime(trade.timestamp)}</td>
            <td><strong>${trade.symbol}</strong></td>
            <td><i class="${sideIcon} ${sideClass}"></i> ${trade.side.toUpperCase()}</td>
            <td>${trade.quantity}</td>
            <td>$${trade.price.toFixed(2)}</td>
        `;
        
        return row;
    }

    setupCharts() {
        this.setupEquityChart();
        this.setupAllocationChart();
    }

    setupEquityChart() {
        const ctx = document.getElementById('equity-chart')?.getContext('2d');
        if (!ctx) return;
        
        this.charts.equity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Portfolio Value',
                    data: [],
                    borderColor: '#1f77b4',
                    backgroundColor: 'rgba(31, 119, 180, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    x: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Date'
                        }
                    },
                    y: {
                        display: true,
                        title: {
                            display: true,
                            text: 'Value ($)'
                        }
                    }
                }
            }
        });
        
        this.loadEquityData();
    }

    setupAllocationChart() {
        const ctx = document.getElementById('allocation-chart')?.getContext('2d');
        if (!ctx) return;
        
        this.charts.allocation = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'AMZN', 'Cash'],
                datasets: [{
                    data: [12, 4, 16, 24, 16, 20],
                    backgroundColor: [
                        '#FF6384', '#36A2EB', '#FFCE56', 
                        '#4BC0C0', '#9966FF', '#FF9F40'
                    ],
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            padding: 20,
                            usePointStyle: true
                        }
                    }
                }
            }
        });
    }

    async loadEquityData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/market/data/AAPL`);
            const data = await response.json();
            
            if (this.charts.equity) {
                this.charts.equity.data.labels = data.data.map(d => d.date);
                this.charts.equity.data.datasets[0].data = data.data.map(d => d.price * 1000); // Scale for demo
                this.charts.equity.update();
            }
            
        } catch (error) {
            console.error('Failed to load equity data:', error);
        }
    }

    async loadStrategies() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/strategies`);
            const data = await response.json();
            
            const strategiesGrid = document.getElementById('strategies-grid');
            strategiesGrid.innerHTML = '';
            
            data.strategies.forEach(strategy => {
                const card = this.createStrategyCard(strategy);
                strategiesGrid.appendChild(card);
            });
            
        } catch (error) {
            console.error('Failed to load strategies:', error);
        }
    }

    createStrategyCard(strategy) {
        const col = document.createElement('div');
        col.className = 'col-md-6 col-lg-4 mb-4';
        
        const statusClass = strategy.status === 'active' ? 'active' : 'inactive';
        const statusText = strategy.status.charAt(0).toUpperCase() + strategy.status.slice(1);
        
        col.innerHTML = `
            <div class="card strategy-card">
                <div class="card-body">
                    <div class="strategy-status ${statusClass}">${statusText}</div>
                    <h5 class="card-title">${strategy.name}</h5>
                    <p class="card-text">${strategy.description}</p>
                    <div class="strategy-performance">
                        <div class="performance-metric">
                            <div class="value">${(strategy.performance.total_return * 100).toFixed(1)}%</div>
                            <div class="label">Return</div>
                        </div>
                        <div class="performance-metric">
                            <div class="value">${strategy.performance.sharpe_ratio.toFixed(1)}</div>
                            <div class="label">Sharpe</div>
                        </div>
                        <div class="performance-metric">
                            <div class="value">${(strategy.performance.max_drawdown * 100).toFixed(1)}%</div>
                            <div class="label">DD</div>
                        </div>
                    </div>
                    <div class="mt-3">
                        <button class="btn btn-sm btn-primary me-2" onclick="dashboard.viewStrategy('${strategy.id}')">
                            <i class='bx bx-show'></i> View
                        </button>
                        <button class="btn btn-sm btn-success me-2" onclick="dashboard.startStrategy('${strategy.id}')">
                            <i class='bx bx-play'></i> Start
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="dashboard.stopStrategy('${strategy.id}')">
                            <i class='bx bx-stop'></i> Stop
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        return col;
    }

    async saveStrategy() {
        const form = document.getElementById('new-strategy-form');
        const formData = new FormData(form);
        
        const strategyData = {
            name: document.getElementById('strategy-name').value,
            description: document.getElementById('strategy-description').value,
            category: document.getElementById('strategy-category').value,
            parameters: JSON.parse(document.getElementById('strategy-parameters').value || '{}')
        };
        
        try {
            const response = await fetch(`${this.apiBaseUrl}/strategies`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(strategyData)
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.showSuccess('Strategy created successfully');
                bootstrap.Modal.getInstance(document.getElementById('strategyModal')).hide();
                this.loadStrategies();
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to save strategy:', error);
            this.showError('Failed to save strategy');
        }
    }

    async runBacktest() {
        const form = document.getElementById('backtest-form');
        const formData = new FormData(form);
        
        const backtestData = {
            strategy_config: {
                strategy_name: document.getElementById('strategy-select').value,
                symbols: document.getElementById('symbols-input').value.split(',').map(s => s.trim()),
                start_date: document.getElementById('start-date').value,
                end_date: document.getElementById('end-date').value,
                initial_capital: parseFloat(document.getElementById('initial-capital').value)
            },
            commission_rate: 0.001
        };
        
        try {
            this.showLoading('Running backtest...');
            
            const response = await fetch(`${this.apiBaseUrl}/backtest/run`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(backtestData)
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.displayBacktestResults(result.results);
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to run backtest:', error);
            this.showError('Failed to run backtest');
        } finally {
            this.hideLoading();
        }
    }

    displayBacktestResults(results) {
        const resultsDiv = document.getElementById('backtest-results');
        
        resultsDiv.innerHTML = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Performance Summary</h6>
                    <div class="metric">
                        <label>Total Return</label>
                        <span>${(results.total_return * 100).toFixed(2)}%</span>
                    </div>
                    <div class="metric">
                        <label>Sharpe Ratio</label>
                        <span>${results.sharpe_ratio.toFixed(2)}</span>
                    </div>
                    <div class="metric">
                        <label>Max Drawdown</label>
                        <span>${(results.max_drawdown * 100).toFixed(2)}%</span>
                    </div>
                    <div class="metric">
                        <label>Win Rate</label>
                        <span>${(results.win_rate * 100).toFixed(1)}%</span>
                    </div>
                </div>
                <div class="col-md-6">
                    <h6>Trade Summary</h6>
                    <div class="metric">
                        <label>Total Trades</label>
                        <span>${results.total_trades}</span>
                    </div>
                    <div class="metric">
                        <label>Strategy</label>
                        <span>${results.strategy_name}</span>
                    </div>
                </div>
            </div>
        `;
    }

    async analyzeSentiment() {
        const text = document.getElementById('sentiment-text').value;
        
        if (!text.trim()) {
            this.showError('Please enter text to analyze');
            return;
        }
        
        try {
            this.showLoading('Analyzing sentiment...');
            
            const response = await fetch(`${this.apiBaseUrl}/ai/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text,
                    analysis_type: 'sentiment'
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.displaySentimentResults(result.results);
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to analyze sentiment:', error);
            this.showError('Failed to analyze sentiment');
        } finally {
            this.hideLoading();
        }
    }

    displaySentimentResults(results) {
        const resultsDiv = document.getElementById('sentiment-results');
        
        const sentimentClass = results.sentiment === 'positive' ? 'text-success' : 
                              results.sentiment === 'negative' ? 'text-danger' : 'text-warning';
        
        resultsDiv.innerHTML = `
            <div class="alert alert-info">
                <h6>Analysis Results</h6>
                <div class="metric">
                    <label>Sentiment</label>
                    <span class="${sentimentClass}">${results.sentiment.toUpperCase()}</span>
                </div>
                <div class="metric">
                    <label>Confidence</label>
                    <span>${(results.confidence * 100).toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <label>Keywords</label>
                    <span>${results.keywords.join(', ')}</span>
                </div>
            </div>
        `;
    }

    async analyzeMarket() {
        const symbol = document.getElementById('analysis-symbol').value;
        const analysisType = document.getElementById('analysis-type').value;
        
        if (!symbol.trim()) {
            this.showError('Please enter a symbol');
            return;
        }
        
        try {
            this.showLoading('Analyzing market...');
            
            const response = await fetch(`${this.apiBaseUrl}/ai/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: `Analyze ${symbol} for ${analysisType} analysis`,
                    analysis_type: analysisType
                })
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.displayMarketResults(result.results, symbol);
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to analyze market:', error);
            this.showError('Failed to analyze market');
        } finally {
            this.hideLoading();
        }
    }

    displayMarketResults(results, symbol) {
        const resultsDiv = document.getElementById('market-analysis-results');
        
        resultsDiv.innerHTML = `
            <div class="alert alert-info">
                <h6>${symbol} Analysis Results</h6>
                <div class="metric">
                    <label>Analysis</label>
                    <span>${results.analysis}</span>
                </div>
                <div class="metric">
                    <label>Confidence</label>
                    <span>${(results.confidence * 100).toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <label>Recommendations</label>
                    <ul>
                        ${results.recommendations.map(rec => `<li>${rec}</li>`).join('')}
                    </ul>
                </div>
            </div>
        `;
    }

    async loadPortfolioData() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/portfolio/status`);
            const data = await response.json();
            
            this.updatePortfolioDisplay(data);
            
        } catch (error) {
            console.error('Failed to load portfolio data:', error);
        }
    }

    updatePortfolioDisplay(data) {
        // Update portfolio summary
        document.getElementById('portfolio-total-value').textContent = `$${data.total_value.toLocaleString()}`;
        document.getElementById('portfolio-cash').textContent = `$${data.cash.toLocaleString()}`;
        document.getElementById('portfolio-invested').textContent = `$${data.invested.toLocaleString()}`;
        document.getElementById('portfolio-daily-pnl').textContent = `$${data.daily_pnl.toLocaleString()}`;
        document.getElementById('portfolio-total-pnl').textContent = `$${data.total_pnl.toLocaleString()}`;
        
        // Update positions table
        const positionsTable = document.getElementById('positions-table');
        positionsTable.innerHTML = '';
        
        data.positions.forEach(position => {
            const row = document.createElement('tr');
            const pnlClass = position.pnl >= 0 ? 'text-success' : 'text-danger';
            const pnlSign = position.pnl >= 0 ? '+' : '';
            
            row.innerHTML = `
                <td><strong>${position.symbol}</strong></td>
                <td>${position.quantity}</td>
                <td>$${position.avg_price.toFixed(2)}</td>
                <td>$${position.current_price.toFixed(2)}</td>
                <td>$${position.value.toLocaleString()}</td>
                <td class="${pnlClass}">${pnlSign}$${position.pnl.toLocaleString()}</td>
                <td>${(position.weight * 100).toFixed(1)}%</td>
            `;
            
            positionsTable.appendChild(row);
        });
    }

    // K线图相关方法
    initCandlestickChart() {
        const container = document.getElementById('candlestick-chart');
        if (!container) return;
        
        // 清除现有图表
        container.innerHTML = '';
        
        // 创建TradingView Lightweight Charts
        this.candlestickChart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: 400,
            layout: {
                backgroundColor: '#ffffff',
                textColor: '#333',
            },
            grid: {
                vertLines: {
                    color: '#f0f0f0',
                },
                horzLines: {
                    color: '#f0f0f0',
                },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#cccccc',
            },
            timeScale: {
                borderColor: '#cccccc',
                timeVisible: true,
                secondsVisible: false,
            },
        });
        
        // 添加K线图系列
        this.candlestickSeries = this.candlestickChart.addCandlestickSeries({
            upColor: '#26a69a',
            downColor: '#ef5350',
            borderVisible: false,
            wickUpColor: '#26a69a',
            wickDownColor: '#ef5350',
        });
        
        // 添加移动平均线
        this.smaSeries = this.candlestickChart.addLineSeries({
            color: '#2196F3',
            lineWidth: 2,
            title: 'SMA 20',
        });
        
        this.emaSeries = this.candlestickChart.addLineSeries({
            color: '#FF9800',
            lineWidth: 2,
            title: 'EMA 20',
        });
        
        // 响应式调整
        window.addEventListener('resize', () => {
            this.candlestickChart.applyOptions({
                width: container.clientWidth,
            });
        });
    }

    async loadCandlestickChart() {
        const symbol = document.getElementById('symbol-input').value || 'AAPL';
        const timeframe = document.getElementById('timeframe-select').value;
        
        try {
            this.showLoading('Loading chart data...');
            
            const response = await fetch(`${this.apiBaseUrl}/market/data/${symbol}?period=${timeframe}`);
            const data = await response.json();
            
            if (data.data && data.data.length > 0) {
                this.updateCandlestickChart(data.data, symbol);
                this.updateChartInfo(data.data[data.data.length - 1], symbol);
            } else {
                this.showError('No data available for this symbol');
            }
            
        } catch (error) {
            console.error('Failed to load chart data:', error);
            this.showError('Failed to load chart data');
        } finally {
            this.hideLoading();
        }
    }

    updateCandlestickChart(data, symbol) {
        if (!this.candlestickSeries) return;
        
        // 转换数据格式
        const candlestickData = data.map(item => ({
            time: new Date(item.date).getTime() / 1000,
            open: item.price * 0.99, // 模拟OHLC数据
            high: item.price * 1.02,
            low: item.price * 0.98,
            close: item.price,
        }));
        
        // 更新K线图
        this.candlestickSeries.setData(candlestickData);
        
        // 计算并添加移动平均线
        this.addMovingAverages(candlestickData);
        
        // 更新图表标题
        document.getElementById('current-symbol').textContent = symbol;
    }

    addMovingAverages(data) {
        if (!this.smaSeries || !this.emaSeries) return;
        
        // 计算SMA 20
        const smaData = [];
        const period = 20;
        
        for (let i = period - 1; i < data.length; i++) {
            const sum = data.slice(i - period + 1, i + 1).reduce((acc, item) => acc + item.close, 0);
            const sma = sum / period;
            smaData.push({
                time: data[i].time,
                value: sma,
            });
        }
        
        // 计算EMA 20
        const emaData = [];
        const multiplier = 2 / (period + 1);
        let ema = data[0].close;
        
        for (let i = 0; i < data.length; i++) {
            ema = (data[i].close * multiplier) + (ema * (1 - multiplier));
            emaData.push({
                time: data[i].time,
                value: ema,
            });
        }
        
        // 更新移动平均线
        this.smaSeries.setData(smaData);
        this.emaSeries.setData(emaData);
    }

    updateChartInfo(latestData, symbol) {
        const price = latestData.price;
        const change = (Math.random() - 0.5) * 10; // 模拟价格变化
        const volume = Math.floor(Math.random() * 1000000) + 500000; // 模拟成交量
        
        document.getElementById('current-price').textContent = `$${price.toFixed(2)}`;
        document.getElementById('price-change').textContent = `${change >= 0 ? '+' : ''}$${change.toFixed(2)} (${(change/price*100).toFixed(2)}%)`;
        document.getElementById('price-change').className = change >= 0 ? 'text-success' : 'text-danger';
        document.getElementById('current-volume').textContent = volume.toLocaleString();
    }

    updateChartIndicators() {
        // 根据复选框状态显示/隐藏技术指标
        const showSMA = document.getElementById('show-sma').checked;
        const showEMA = document.getElementById('show-ema').checked;
        
        if (this.smaSeries) {
            this.smaSeries.applyOptions({
                visible: showSMA,
            });
        }
        
        if (this.emaSeries) {
            this.emaSeries.applyOptions({
                visible: showEMA,
            });
        }
    }

    // Utility methods
    formatTime(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString();
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showError(message) {
        this.showNotification(message, 'danger');
    }

    showNotification(message, type) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
        
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.remove();
            }
        }, 5000);
    }

    showLoading(message) {
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-overlay';
        loadingDiv.className = 'position-fixed w-100 h-100 d-flex align-items-center justify-content-center';
        loadingDiv.style.cssText = 'top: 0; left: 0; background: rgba(0,0,0,0.5); z-index: 9999;';
        
        loadingDiv.innerHTML = `
            <div class="text-center text-white">
                <div class="loading mb-3"></div>
                <div>${message}</div>
            </div>
        `;
        
        document.body.appendChild(loadingDiv);
    }

    hideLoading() {
        const loadingDiv = document.getElementById('loading-overlay');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }

    // Strategy management methods
    async startStrategy(strategyId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/strategies/${strategyId}/start`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.showSuccess('Strategy started successfully');
                this.loadStrategies();
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to start strategy:', error);
            this.showError('Failed to start strategy');
        }
    }

    async stopStrategy(strategyId) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/strategies/${strategyId}/stop`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.status === 'success') {
                this.showSuccess('Strategy stopped successfully');
                this.loadStrategies();
            } else {
                this.showError(result.message);
            }
            
        } catch (error) {
            console.error('Failed to stop strategy:', error);
            this.showError('Failed to stop strategy');
        }
    }

    viewStrategy(strategyId) {
        // Navigate to strategy details page or show modal
        this.showNotification('Strategy details feature coming soon', 'info');
    }
}

// Initialize the dashboard when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new TradingDashboard();
}); 