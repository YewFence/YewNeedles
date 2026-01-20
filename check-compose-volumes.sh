#!/bin/bash
# 检测 docker compose 文件中挂载的命名卷
# 依赖: yq (https://github.com/mikefarah/yq)
# 用法: ./check-compose-volumes.sh [docker-compose文件路径]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 检查 yq 是否安装
if ! command -v yq &> /dev/null; then
    echo -e "${RED}错误: 需要安装 yq${NC}"
    echo "安装方式: https://github.com/mikefarah/yq#install"
    exit 1
fi

# 查找 compose 文件
find_compose_file() {
    local dir="${1:-.}"
    for file in "docker-compose.yml" "docker-compose.yaml" "compose.yml" "compose.yaml"; do
        if [[ -f "$dir/$file" ]]; then
            echo "$dir/$file"
            return 0
        fi
    done
    return 1
}

main() {
    local compose_file=""
    local compose_args=""

    if [[ -n "$1" ]]; then
        if [[ -f "$1" ]]; then
            compose_file="$1"
            compose_args="-f $1"
        else
            echo -e "${RED}错误: 文件 '$1' 不存在${NC}"
            exit 1
        fi
    else
        compose_file=$(find_compose_file ".")
        if [[ -z "$compose_file" ]]; then
            echo -e "${RED}错误: 当前目录下找不到 docker compose 文件${NC}"
            exit 1
        fi
    fi

    # 获取项目名（目录名）
    local project_dir=$(cd "$(dirname "$compose_file")" && pwd)
    local project_name=$(basename "$project_dir")

    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}检测文件: ${GREEN}$compose_file${NC}"
    echo -e "${BLUE}项目名称: ${GREEN}$project_name${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""

    # 使用 docker compose config 获取解析后的配置，再用 yq 提取
    local config=$(docker compose $compose_args config 2>/dev/null)

    # 提取顶级命名卷
    echo -e "${YELLOW}【命名卷定义】${NC}"
    echo "---"

    local volumes=$(echo "$config" | yq -r '.volumes | keys | .[]' 2>/dev/null || echo "")

    if [[ -n "$volumes" ]]; then
        echo "$volumes" | while read -r vol; do
            local real_name=$(echo "$config" | yq -r ".volumes.\"$vol\".name // \"${project_name}_${vol}\"")
            echo -e "  ${GREEN}✓${NC} $vol -> ${BLUE}$real_name${NC}"
        done
    else
        echo -e "  ${YELLOW}(无命名卷定义)${NC}"
    fi

    # 提取服务卷挂载
    echo ""
    echo -e "${YELLOW}【服务卷挂载】${NC}"
    echo "---"

    local services=$(echo "$config" | yq -r '.services | keys | .[]' 2>/dev/null)

    for service in $services; do
        local service_volumes=$(echo "$config" | yq -r ".services.\"$service\".volumes[]? | .source + \":\" + .target" 2>/dev/null || echo "")

        if [[ -n "$service_volumes" ]]; then
            echo -e "\n${BLUE}$service${NC}:"
            echo "$service_volumes" | while read -r vol; do
                local source=$(echo "$vol" | cut -d: -f1)
                local target=$(echo "$vol" | cut -d: -f2)

                # 判断是命名卷还是绑定挂载
                if [[ "$source" =~ ^/ ]] || [[ "$source" =~ ^\. ]]; then
                    echo -e "  ${YELLOW}[绑定挂载]${NC} $source -> $target"
                else
                    echo -e "  ${GREEN}[命名卷]${NC} $source -> $target"
                fi
            done
        fi
    done

    echo ""
    echo -e "${BLUE}========================================${NC}"
}

main "$@"
