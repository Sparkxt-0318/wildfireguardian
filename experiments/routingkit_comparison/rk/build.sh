#!/bin/sh
# Build rk_tool against a RoutingKit checkout. RK_DIR defaults to ./RoutingKit.
set -e
here=$(cd "$(dirname "$0")" && pwd)
RK_DIR=${RK_DIR:-$here/RoutingKit}
if [ ! -d "$RK_DIR" ]; then
  git clone --depth 1 https://github.com/RoutingKit/RoutingKit.git "$RK_DIR"
fi
(cd "$RK_DIR" && make -j4 lib/libroutingkit.a >/dev/null)
g++ -O3 -DNDEBUG -std=c++17 -fopenmp -I"$RK_DIR/include" "$here/rk_tool.cpp" "$RK_DIR/lib/libroutingkit.a" -o "$here/rk_tool"
echo "built $here/rk_tool"
