#include <gtest/gtest.h>
#include "data_loader.hpp"

class DataLoaderTest : public ::testing::Test {
protected:
    void SetUp() override {
        data_loader_ = std::make_unique<trading::DataLoader>();
    }

    std::unique_ptr<trading::DataLoader> data_loader_;
};

TEST_F(DataLoaderTest, LoadMarketData) {
    auto data = data_loader_->loadMarketData("AAPL");
    EXPECT_FALSE(data.symbol.empty());
    EXPECT_GT(data.last_price, 0);
}

TEST_F(DataLoaderTest, LoadHistoricalData) {
    auto end = std::chrono::system_clock::now();
    auto start = end - std::chrono::hours(24);
    
    auto data = data_loader_->loadHistoricalData("AAPL", start, end);
    EXPECT_FALSE(data.empty());
} 