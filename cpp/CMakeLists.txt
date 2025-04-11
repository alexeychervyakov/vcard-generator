cmake_minimum_required(VERSION 3.10)
project(CreateCard)

set(CMAKE_CXX_STANDARD 17)

find_package(OpenCV REQUIRED)
find_package(libharu REQUIRED)
find_package(Zint REQUIRED)

add_executable(CreateCard main.cpp)
target_link_libraries(CreateCard ${OpenCV_LIBS} haru zint)