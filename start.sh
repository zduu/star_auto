#!/bin/bash
# Mac/Linux Shell启动脚本
# 适用于Mac和Linux平台

echo "========================================"
echo "Discourse网站自动化脚本 - Mac/Linux版本"
echo "========================================"
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到Python，请先安装Python 3.7+"
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "Mac用户可以通过以下方式安装:"
            echo "1. 从官网下载: https://www.python.org/downloads/"
            echo "2. 使用Homebrew: brew install python"
        elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "Linux用户可以通过包管理器安装:"
            echo "Ubuntu/Debian: sudo apt install python3 python3-pip"
            echo "CentOS/RHEL: sudo yum install python3 python3-pip"
        fi
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# 检查Python版本
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | cut -d' ' -f2)
echo "Python版本: $PYTHON_VERSION"

# 检查是否在正确的目录
if [ ! -f "start.py" ]; then
    echo "错误: 未找到start.py文件"
    echo "请确保在正确的目录中运行此脚本"
    exit 1
fi

# 检查虚拟环境
if [ -n "$VIRTUAL_ENV" ]; then
    echo "检测到虚拟环境: $VIRTUAL_ENV"
else
    echo "提示: 建议在虚拟环境中运行"
fi

echo
echo "启动自动化脚本..."
echo

# 运行Python脚本
$PYTHON_CMD start.py

# 检查退出状态
if [ $? -ne 0 ]; then
    echo
    echo "程序执行出错，请查看上方错误信息"
    read -p "按Enter键退出..."
fi
