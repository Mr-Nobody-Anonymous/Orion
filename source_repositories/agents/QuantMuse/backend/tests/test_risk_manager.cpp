#include <gtest/gtest.h>
#include "risk_manager.hpp"

class RiskManagerTest : public ::testing::Test {
protected:
    void SetUp() override {
        trading::RiskManager::RiskLimits limits{
            .max_position_size = 0.1,
            .max_drawdown = 0.2,
            .max_leverage = 2.0,
            .daily_loss_limit = 10000.0,
            .position_concentration = 0.3
        };
        risk_manager_ = std::make_unique<trading::RiskManager>(limits);
    }

    std::unique_ptr<trading::RiskManager> risk_manager_;
};

TEST_F(RiskManagerTest, CheckOrderRisk) {
    trading::Order order("AAPL", trading::OrderSide::BUY, 
                        trading::OrderType::MARKET, 100);
    trading::Portfolio portfolio;
    
    EXPECT_TRUE(risk_manager_->checkOrderRisk(order, portfolio));
} 