#include "data_loader.hpp"
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <spdlog/spdlog.h>
#include <stdexcept>

namespace py = pybind11;

namespace trading {

class DataLoader::Impl {
public:
    Impl() {
        try {
            // 初始化Python接口
            py::module::import("sys").attr("path").attr("append")("../");
            data_service_ = py::module::import("data_service");
            fetcher_ = data_service_.attr("YahooFetcher")();
            
        } catch (const std::exception& e) {
            spdlog::error("Failed to initialize Python interface: {}", e.what());
            throw;
        }
    }

    MarketData loadMarketData(const std::string& symbol) {
        try {
            py::object data = fetcher_.attr("get_current_price")(symbol);
            return convertPyToMarketData(data, symbol);
            
        } catch (const std::exception& e) {
            spdlog::error("Failed to load market data for {}: {}", symbol, e.what());
            throw;
        }
    }

    std::vector<MarketData> loadHistoricalData(
        const std::string& symbol,
        const Timestamp& start,
        const Timestamp& end
    ) {
        try {
            py::object data = fetcher_.attr("fetch_historical_data")(
                symbol,
                py::cast(start),
                py::cast(end)
            );
            
            std::vector<MarketData> result;
            for (const auto& item : data) {
                result.push_back(convertPyToMarketData(item, symbol));
            }
            return result;
            
        } catch (const std::exception& e) {
            spdlog::error("Failed to load historical data for {}: {}", symbol, e.what());
            throw;
        }
    }

    void subscribeToRealTimeData(
        const std::string& symbol,
        std::function<void(const MarketData&)> callback
    ) {
        try {
            auto py_callback = [callback](const py::object& data) {
                callback(convertPyToMarketData(data, data.attr("symbol").cast<std::string>()));
            };
            
            fetcher_.attr("start_websocket")(symbol, py_callback);
            
        } catch (const std::exception& e) {
            spdlog::error("Failed to subscribe to real-time data for {}: {}", symbol, e.what());
            throw;
        }
    }

private:
    static MarketData convertPyToMarketData(const py::object& data, const std::string& symbol) {
        MarketData market_data;
        market_data.symbol = symbol;
        market_data.last_price = data.attr("close").cast<double>();
        market_data.open = data.attr("open").cast<double>();
        market_data.high = data.attr("high").cast<double>();
        market_data.low = data.attr("low").cast<double>();
        market_data.volume = data.attr("volume").cast<double>();
        market_data.timestamp = data.attr("timestamp").cast<Timestamp>();
        
        // 转换技术指标
        if (py::hasattr(data, "indicators")) {
            py::dict indicators = data.attr("indicators");
            for (const auto& item : indicators) {
                std::string key = item.first.cast<std::string>();
                double value = item.second.cast<double>();
                market_data.indicators[key] = value;
            }
        }
        
        return market_data;
    }

    py::module data_service_;
    py::object fetcher_;
};

// DataLoader类的实现
DataLoader::DataLoader() : pimpl_(std::make_unique<Impl>()) {}
DataLoader::~DataLoader() = default;

MarketData DataLoader::loadMarketData(const std::string& symbol) {
    return pimpl_->loadMarketData(symbol);
}

std::vector<MarketData> DataLoader::loadHistoricalData(
    const std::string& symbol,
    const Timestamp& start,
    const Timestamp& end
) {
    return pimpl_->loadHistoricalData(symbol, start, end);
}

void DataLoader::subscribeToRealTimeData(
    const std::string& symbol,
    std::function<void(const MarketData&)> callback
) {
    pimpl_->subscribeToRealTimeData(symbol, callback);
}

} // namespace trading 