#!/usr/bin/env bash
# llama.cpp (ggml-org): llama-server built with Vulkan (AMD, Intel, NVIDIA), in $INSTALL_DIR.
# Needs the Vulkan headers and loader, and glslc to compile the shaders.
source "$(dirname "$0")/lib.sh"
need git cmake ninja g++ glslc
git_checkout https://github.com/ggml-org/llama.cpp "$INSTALL_DIR"
cd "$INSTALL_DIR"
step "Configuring (Vulkan)"
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_VULKAN=ON -DLLAMA_CURL=OFF
step "Building llama-server (several minutes)"
nice -n 10 cmake --build build --target llama-server
build/bin/llama-server --version
