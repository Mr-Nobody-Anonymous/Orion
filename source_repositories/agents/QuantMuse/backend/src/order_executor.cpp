#include "order_executor.hpp"
#include <spdlog/spdlog.h>

namespace trading {

OrderExecutor::OrderExecutor() : running_(false) {
}

OrderExecutor::~OrderExecutor() {
    stop();
}

void OrderExecutor::start() {
    running_ = true;
    execution_thread_ = std::thread(&OrderExecutor::executionLoop, this);
    spdlog::info("Order executor started");
}

void OrderExecutor::stop() {
    running_ = false;
    cv_.notify_one();
    
    if (execution_thread_.joinable()) {
        execution_thread_.join();
    }
    spdlog::info("Order executor stopped");
}

void OrderExecutor::submitOrder(std::shared_ptr<Order> order) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        order_queue_.push(order);
    }
    cv_.notify_one();
    spdlog::info("Order submitted: {}", order->getOrderId());
}

void OrderExecutor::executionLoop() {
    while (running_) {
        std::shared_ptr<Order> order;
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this] { 
                return !order_queue_.empty() || !running_; 
            });
            
            if (!running_) break;
            
            order = order_queue_.front();
            order_queue_.pop();
        }
        
        executeOrder(order);
    }
}

void OrderExecutor::executeOrder(std::shared_ptr<Order> order) {
    try {
        // 实现实际的订单执行逻辑
        order->setStatus(OrderStatus::FILLED);
        spdlog::info("Order executed: {}", order->getOrderId());
        
    } catch (const std::exception& e) {
        order->setStatus(OrderStatus::REJECTED);
        spdlog::error("Order execution failed: {}", e.what());
    }
}

} // namespace trading 