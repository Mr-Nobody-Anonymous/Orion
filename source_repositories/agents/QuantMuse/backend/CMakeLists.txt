cmake_minimum_required(VERSION 3.12)
project(trading_engine)

# 设置C++标准
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# 查找依赖包
find_package(pybind11 REQUIRED)  # Python接口
find_package(spdlog REQUIRED)    # 日志
find_package(nlohmann_json REQUIRED)  # JSON处理
find_package(Boost REQUIRED COMPONENTS system)  # Boost

# 添加头文件路径
include_directories(${CMAKE_SOURCE_DIR}/include)

# 收集源文件
file(GLOB_RECURSE SOURCES "src/*.cpp")

# 创建可执行文件
add_executable(trading_engine ${SOURCES})

# 链接依赖库
target_link_libraries(trading_engine
    PRIVATE
        pybind11::embed
        spdlog::spdlog
        nlohmann_json::nlohmann_json
        Boost::system
        pthread
) 