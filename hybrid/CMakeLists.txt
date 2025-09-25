cmake_minimum_required(VERSION 3.20)
project(cppcore LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

find_package(pybind11 CONFIG REQUIRED)
find_package(Open3D REQUIRED)
find_package(Eigen3 REQUIRED)

# OpenNURBS
set(OPENNURBS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/docker-extract")
set(OPENNURBS_INCLUDE_DIR "${OPENNURBS_DIR}/OpenNURBS")
set(OPENNURBS_LIB "${OPENNURBS_DIR}/libOpenNURBS.so")

option(WITH_IGL "Enable libigl for Brep meshing" OFF)
if (WITH_IGL)
  find_package(PkgConfig REQUIRED)
  find_path(LIBIGL_INCLUDE_DIR igl/readOBJ.h)
  if (LIBIGL_INCLUDE_DIR)
    target_compile_definitions(cppcore PRIVATE HYBRID_WITH_IGL)
    target_include_directories(cppcore PRIVATE ${LIBIGL_INCLUDE_DIR})
  endif()
endif()

pybind11_add_module(cppcore cpp/bindings.cpp)

# 确保我们的 Open3D 头文件路径优先于系统安装的版本
target_include_directories(cppcore PRIVATE 
    ${CMAKE_CURRENT_SOURCE_DIR}/docker-extract
    ${OPENNURBS_INCLUDE_DIR}
)
target_link_libraries(cppcore PRIVATE Open3D::Open3D Eigen3::Eigen ${OPENNURBS_LIB})

if (MSVC)
  target_compile_options(cppcore PRIVATE /O2 /DNDEBUG /EHsc)
else()
  target_compile_options(cppcore PRIVATE -O3 -DNDEBUG -fPIC)
  find_package(OpenMP)
  if (OpenMP_CXX_FOUND)
    target_link_libraries(cppcore PRIVATE OpenMP::OpenMP_CXX)
    target_compile_definitions(cppcore PRIVATE HYBRID_WITH_OPENMP)
  endif()
endif()

install(TARGETS cppcore LIBRARY DESTINATION .)