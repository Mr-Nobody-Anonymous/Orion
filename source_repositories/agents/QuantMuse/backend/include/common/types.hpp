#pragma once
#include <string>
#include <vector>
#include <chrono>
#include <memory>
#include <map>

namespace trading {

using Timestamp = std::chrono::system_clock::time_point;

// 市场数据结构
struct MarketData {
    std::string symbol;
    double last_price;
    double open;
    double high;
    double low;
    double volume;
    Timestamp timestamp;
    
    // 可选的扩展数据
    std::map<std::string, double> indicators;  // 技术指标
    std::map<std::string, double> fundamentals;  // 基本面数据
};

// 订单方向
enum class OrderSide {
    BUY,
    SELL
};

// 订单类型
enum class OrderType {
    MARKET,
    LIMIT,
    STOP,
    STOP_LIMIT
};

// 订单状态
enum class OrderStatus {
    PENDING,
    FILLED,
    PARTIALLY_FILLED,
    CANCELLED,
    REJECTED
};

// 订单类
class Order {
public:
    Order(const std::string& symbol, OrderSide side, OrderType type, double quantity)
        : symbol_(symbol), side_(side), type_(type), quantity_(quantity) {
        order_id_ = generateOrderId();
    }

    // Getters
    std::string getOrderId() const { return order_id_; }
    std::string getSymbol() const { return symbol_; }
    OrderSide getSide() const { return side_; }
    OrderType getType() const { return type_; }
    double getQuantity() const { return quantity_; }
    double getPrice() const { return price_; }
    OrderStatus getStatus() const { return status_; }

    // Setters
    void setPrice(double price) { price_ = price; }
    void setStatus(OrderStatus status) { status_ = status; }
    void setFilledQuantity(double qty) { filled_quantity_ = qty; }

private:
    static std::string generateOrderId() {
        static int counter = 0;
        return "ORD" + std::to_string(++counter);
    }

    std::string order_id_;
    std::string symbol_;
    OrderSide side_;
    OrderType type_;
    double quantity_;
    double price_ = 0.0;
    double filled_quantity_ = 0.0;
    OrderStatus status_ = OrderStatus::PENDING;
    Timestamp create_time_ = std::chrono::system_clock::now();
    Timestamp update_time_ = create_time_;
};

// 持仓类
class Position {
public:
    Position(const std::string& symbol) : symbol_(symbol) {}

    void updatePosition(double quantity, double price) {
        quantity_ += quantity;
        if (quantity_ != 0) {
            average_price_ = (average_price_ * (quantity_ - quantity) + price * quantity) / quantity_;
        }
    }

    double getQuantity() const { return quantity_; }
    double getAveragePrice() const { return average_price_; }
    double getMarketValue(double current_price) const { return quantity_ * current_price; }
    double getUnrealizedPnL(double current_price) const {
        return quantity_ * (current_price - average_price_);
    }

private:
    std::string symbol_;
    double quantity_ = 0.0;
    double average_price_ = 0.0;
};

// 投资组合类
class Portfolio {
public:
    void updatePosition(const std::string& symbol, double quantity, double price) {
        if (positions_.find(symbol) == positions_.end()) {
            positions_[symbol] = std::make_shared<Position>(symbol);
        }
        positions_[symbol]->updatePosition(quantity, price);
    }

    double getTotalValue(const std::map<std::string, double>& current_prices) const {
        double total = cash_;
        for (const auto& [symbol, position] : positions_) {
            if (current_prices.find(symbol) != current_prices.end()) {
                total += position->getMarketValue(current_prices.at(symbol));
            }
        }
        return total;
    }

    double getCash() const { return cash_; }
    void updateCash(double amount) { cash_ += amount; }
    
    std::shared_ptr<Position> getPosition(const std::string& symbol) const {
        auto it = positions_.find(symbol);
        return (it != positions_.end()) ? it->second : nullptr;
    }

    double getTotalExposure() const { return total_exposure_; }
    double getDrawdown() const { return drawdown_; }
    double getLeverage() const { return leverage_; }
    double getDailyPnL() const { return daily_pnl_; }
    double getConcentration() const { return concentration_; }

private:
    double cash_ = 1000000.0;  // 初始资金100万
    std::map<std::string, std::shared_ptr<Position>> positions_;
    double total_exposure_ = 0.0;
    double drawdown_ = 0.0;
    double leverage_ = 1.0;
    double daily_pnl_ = 0.0;
    double concentration_ = 0.0;
};

} // namespace trading 