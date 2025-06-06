@echo off
REM Windows批处理启动脚本
REM 适用于Windows平台

echo ========================================
echo Discourse网站自动化脚本 - Windows版本
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 检查是否在正确的目录
if not exist "start.py" (
    echo 错误: 未找到start.py文件
    echo 请确保在正确的目录中运行此脚本
    pause
    exit /b 1
)

REM 检查虚拟环境
if defined VIRTUAL_ENV (
    echo 检测到虚拟环境: %VIRTUAL_ENV%
) else (
    echo 提示: 建议在虚拟环境中运行
)

echo.
echo 启动自动化脚本...
echo.

REM 运行Python脚本
python start.py

REM 如果出错，暂停以查看错误信息
if errorlevel 1 (
    echo.
    echo 程序执行出错，请查看上方错误信息
    pause
)
