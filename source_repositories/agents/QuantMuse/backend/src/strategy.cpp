#include "strategy.hpp"
#include <numeric>
#include <spdlog/spdlog.h>

namespace trading {

MovingAverageStrategy::MovingAverageStrategy(int short_period, int long_period)
    : short_period_(short_period)
    , long_period_(long_period) {
}

void MovingAverageStrategy::initialize() {
    prices_.clear();
}

std::vector<Strategy::Signal> MovingAverageStrategy::onMarketData(
    const MarketData& data) {
    
    std::vector<Signal> signals;
    prices_.push_back(data.last_price);
    
    if (prices_.size() < static_cast<size_t>(long_period_)) {
        return signals;
    }
    
    // 计算移动平均
    double short_ma = std::accumulate(
        prices_.end() - short_period_, 
        prices_.end(), 
        0.0
    ) / short_period_;
    
    double long_ma = std::accumulate(
        prices_.end() - long_period_, 
        prices_.end(), 
        0.0
    ) / long_period_;
    
    Signal signal;
    signal.symbol = data.symbol;
    signal.timestamp = data.timestamp;
    
    if (short_ma > long_ma) {
        signal.side = OrderSide::BUY;
        signal.strength = (short_ma - long_ma) / long_ma;
    } else {
        signal.side = OrderSide::SELL;
        signal.strength = (long_ma - short_ma) / long_ma;
    }
    
    signals.push_back(signal);
    return signals;
}

void MovingAverageStrategy::onOrderUpdate(const Order& order) {
    spdlog::info("Order {} updated: status = {}", 
                 order.getOrderId(), 
                 static_cast<int>(order.getStatus()));
}

} // namespace trading 