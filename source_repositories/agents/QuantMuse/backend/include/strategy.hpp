#pragma once
#include "common/types.hpp"
#include <vector>
#include <memory>

namespace trading {

class Strategy {
public:
    struct Signal {
        std::string symbol;
        OrderSide side;
        double strength;  // 信号强度 [-1, 1]
        Timestamp timestamp;
    };

    virtual ~Strategy() = default;
    virtual void initialize() = 0;
    virtual std::vector<Signal> onMarketData(const MarketData& data) = 0;
    virtual void onOrderUpdate(const Order& order) = 0;
};

// 移动平均策略
class MovingAverageStrategy : public Strategy {
public:
    MovingAverageStrategy(int short_period = 10, int long_period = 30);
    void initialize() override;
    std::vector<Signal> onMarketData(const MarketData& data) override;
    void onOrderUpdate(const Order& order) override;

private:
    int short_period_;
    int long_period_;
    std::vector<double> prices_;
};

} // namespace trading 