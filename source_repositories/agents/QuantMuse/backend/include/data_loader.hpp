#pragma once
#include <string>
#include <memory>
#include <vector>
#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include "common/types.hpp"

namespace trading {

class DataLoader {
public:
    DataLoader();
    ~DataLoader();

    // 从Python数据服务获取数据
    MarketData loadMarketData(const std::string& symbol);
    
    // 获取历史数据
    std::vector<MarketData> loadHistoricalData(
        const std::string& symbol,
        const Timestamp& start,
        const Timestamp& end
    );
    
    // 订阅实时数据
    void subscribeToRealTimeData(
        const std::string& symbol,
        std::function<void(const MarketData&)> callback
    );

private:
    py::module data_service_;  // Python模块
    py::object fetcher_;       // Python数据获取器实例
};

} // namespace trading 