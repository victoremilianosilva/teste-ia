cmake_minimum_required(VERSION 3.20)

project(tft_combat_engine
    VERSION 0.1.0
    LANGUAGES CXX
)

# ==========================================
# C++20
# ==========================================

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ==========================================
# Diretórios de saída
# ==========================================

set(CMAKE_RUNTIME_OUTPUT_DIRECTORY
    ${CMAKE_BINARY_DIR}/bin
)

set(CMAKE_LIBRARY_OUTPUT_DIRECTORY
    ${CMAKE_BINARY_DIR}/bin
)

set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY
    ${CMAKE_BINARY_DIR}/lib
)

# ==========================================
# Python
# ==========================================

find_package(Python REQUIRED COMPONENTS
    Interpreter
    Development
)

# ==========================================
# pybind11
# ==========================================

set(pybind11_DIR
    "C:/Users/cilio/Desktop/Ideia louca/TFT/.venv/Lib/site-packages/pybind11/share/cmake/pybind11"
)

find_package(pybind11 CONFIG REQUIRED)

# ==========================================
# Python module
# ==========================================

pybind11_add_module(
    combat_engine
    src/CombatEngine.cpp
    src/bindings.cpp
)

target_include_directories(
    combat_engine
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)