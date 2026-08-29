#include "data_loader.hpp"
#include "strategy.hpp"
#include "risk_manager.hpp"
#include "order_executor.hpp"
#include "utils/logger.hpp"
#include "common/config.hpp"
#include <csignal>
#include <atomic>
#include <thread>
#include <memory>

namespace {
    std::atomic<bool> running{true};
    
    void signalHandler(int signal) {
        spdlog::info("Received signal {}, shutting down...", signal);
        running = false;
    }
}

class TradingEngine {
public:
    TradingEngine() {
        initialize();
    }

    void run() {
        try {
            // 启动订单执行器
            order_executor_->start();
            
            // 主事件循环
            while (running) {
                processMarketData();
                processSignals();
                updateRiskMetrics();
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            
            // 优雅退出
            shutdown();
            
        } catch (const std::exception& e) {
            spdlog::critical("Fatal error in trading engine: {}", e.what());
            shutdown();
            throw;
        }
    }

private:
    void initialize() {
        // 初始化日志
        Logger::init();
        spdlog::info("Initializing trading engine...");
        
        // 加载配置
        config_ = std::make_unique<Config>("config.json");
        
        // 初始化组件
        data_loader_ = std::make_unique<DataLoader>();
        strategy_ = std::make_unique<MovingAverageStrategy>();
        risk_manager_ = std::make_unique<RiskManager>(config_->getRiskLimits());
        order_executor_ = std::make_unique<OrderExecutor>();
        
        // 设置信号处理
        signal(SIGINT, signalHandler);
        signal(SIGTERM, signalHandler);
        
        spdlog::info("Trading engine initialized successfully");
    }

    void processMarketData() {
        try {
            for (const auto& symbol : config_->getSymbols()) {
                auto market_data = data_loader_->loadMarketData(symbol);
                strategy_->onMarketData(market_data);
            }
        } catch (const std::exception& e) {
            spdlog::error("Error processing market data: {}", e.what());
        }
    }

    void processSignals() {
        try {
            auto signals = strategy_->getSignals();
            for (const auto& signal : signals) {
                auto order = createOrder(signal);
                if (risk_manager_->checkOrderRisk(*order, portfolio_)) {
                    order_executor_->submitOrder(order);
                }
            }
        } catch (const std::exception& e) {
            spdlog::error("Error processing signals: {}", e.what());
        }
    }

    void updateRiskMetrics() {
        try {
            risk_manager_->updateRiskMetrics(portfolio_);
            auto metrics = risk_manager_->getRiskMetrics();
            
            // 记录风险指标
            spdlog::debug("Risk metrics - Drawdown: {:.2f}%, Leverage: {:.2f}x",
                metrics["drawdown"] * 100,
                metrics["leverage"]);
                
        } catch (const std::exception& e) {
            spdlog::error("Error updating risk metrics: {}", e.what());
        }
    }

    void shutdown() {
        spdlog::info("Shutting down trading engine...");
        order_executor_->stop();
        // 保存状态和清理资源
        spdlog::info("Trading engine shutdown complete");
    }

    std::shared_ptr<Order> createOrder(const Strategy::Signal& signal) {
        return std::make_shared<Order>(
            signal.symbol,
            signal.side,
            OrderType::MARKET,
            calculateOrderSize(signal)
        );
    }

    double calculateOrderSize(const Strategy::Signal& signal) {
        // 根据信号强度和资金管理规则计算订单大小
        double portfolio_value = portfolio_.getTotalValue(getCurrentPrices());
        return portfolio_value * config_->getPositionSizeLimit() * signal.strength;
    }

    std::map<std::string, double> getCurrentPrices() {
        std::map<std::string, double> prices;
        for (const auto& symbol : config_->getSymbols()) {
            auto market_data = data_loader_->loadMarketData(symbol);
            prices[symbol] = market_data.last_price;
        }
        return prices;
    }

private:
    std::unique_ptr<Config> config_;
    std::unique_ptr<DataLoader> data_loader_;
    std::unique_ptr<Strategy> strategy_;
    std::unique_ptr<RiskManager> risk_manager_;
    std::unique_ptr<OrderExecutor> order_executor_;
    Portfolio portfolio_;
};

int main() {
    try {
        TradingEngine engine;
        engine.run();
        return 0;
    } catch (const std::exception& e) {
        spdlog::critical("Fatal error: {}", e.what());
        return 1;
    }
} 