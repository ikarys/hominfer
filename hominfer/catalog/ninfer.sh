#!/usr/bin/env bash
# Ninfer (Neroued/ninfer): ninfer-serve built with CUDA for this GPU, in $INSTALL_DIR.
source "$(dirname "$0")/lib.sh"
need git cmake ninja g++ uv pkg-config
declare -A apt=([hwloc]=libhwloc-dev [liburing]=liburing-dev [libjpeg]=libjpeg-dev [libavformat]=libavformat-dev
                [libavcodec]=libavcodec-dev [libavutil]=libavutil-dev [libswscale]=libswscale-dev [libcurl]=libcurl4-openssl-dev)
pkgs=()
for lib in "${!apt[@]}"; do
  pkg-config --exists "$lib" || { echo "Missing library: $lib"; pkgs+=("${apt[$lib]}"); }
done
if [ ${#pkgs[@]} -gt 0 ]; then
  echo "Install them with: sudo apt install ${pkgs[*]}"
  exit 1
fi
cuda_toolkit
uv pip install -q --python "$CUDA_VENV/bin/python" "nvidia-cuda-profiler-api==$CUDA_VERSION.*"
# older installs cloned the co-l fork: move them to upstream
if [ -d "$INSTALL_DIR/.git" ] && git -C "$INSTALL_DIR" remote get-url origin | grep -q co-l/; then
  step "Switching $INSTALL_DIR to upstream"
  git -C "$INSTALL_DIR" remote set-url origin https://github.com/Neroued/ninfer.git
  git -C "$INSTALL_DIR" fetch --depth 1 origin master
  git -C "$INSTALL_DIR" checkout -B master --track origin/master
fi
git_checkout https://github.com/Neroued/ninfer.git "$INSTALL_DIR"
cd "$INSTALL_DIR"
git submodule update --init --recursive
# upstream tunes one preset per machine: DGX Spark (GB10, cc 12.1), else RTX 5090
PRESET=rtx5090-release
[ "${GPU_CC:-}" = "12.1" ] && PRESET=dgx-spark-release
step "Configuring ($PRESET)"
cmake --preset "$PRESET" -B build/release -DCUDAToolkit_ROOT="$CUDA_ROOT" -DCMAKE_CUDA_COMPILER="$CUDA_ROOT/bin/nvcc"
step "Building (several minutes)"
nice -n 10 cmake --build build/release --target ninfer-serve
ls -la build/release/apps/ninfer-serve
