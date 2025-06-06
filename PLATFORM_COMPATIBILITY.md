# 平台兼容性说明

## 概述

本项目现已完全支持Mac、Windows和Linux三大主流操作系统，提供了统一的用户体验和平台特定的优化。

## 支持的平台

### ✅ macOS
- **支持版本**: macOS 10.14 (Mojave) 及以上
- **架构**: Intel x64 和 Apple Silicon (M1/M2)
- **Chrome路径**: 自动检测 `/Applications/Google Chrome.app`
- **启动方式**: `./start.sh` 或 `python start.py`

### ✅ Windows
- **支持版本**: Windows 10/11
- **架构**: x64 和 x86
- **Chrome路径**: 自动检测多个可能的安装位置
- **启动方式**: 双击 `start.bat` 或 `python start.py`

### ✅ Linux
- **支持发行版**: Ubuntu, Debian, CentOS, RHEL, Fedora等
- **架构**: x64
- **Chrome路径**: 自动检测包管理器安装的Chrome/Chromium
- **启动方式**: `./start.sh` 或 `python start.py`

## 平台特定功能

### 自动Chrome检测
```python
# Windows路径
C:\Program Files\Google\Chrome\Application\chrome.exe
C:\Program Files (x86)\Google\Chrome\Application\chrome.exe
%USERPROFILE%\AppData\Local\Google\Chrome\Application\chrome.exe

# macOS路径
/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome

# Linux路径
/usr/bin/google-chrome
/usr/bin/google-chrome-stable
/usr/bin/chromium-browser
/snap/bin/chromium
```

### 平台特定Chrome选项
- **Windows**: 额外的沙盒和共享内存选项
- **macOS**: 优化的安全选项
- **Linux**: GPU禁用和额外的稳定性选项

### 文件系统兼容性
- **路径分隔符**: 自动使用 `os.path.join()`
- **文件名清理**: 移除平台不支持的字符
- **用户数据目录**: 平台特定的安全目录创建
- **日志文件**: UTF-8编码确保中文支持

## 安装和使用

### 1. 环境要求
- Python 3.7+
- Chrome浏览器
- 网络连接

### 2. 依赖安装
```bash
pip install -r requirements.txt
```

### 3. 启动方式

#### Windows
```cmd
# 方式1: 双击启动
start.bat

# 方式2: 命令行
python start.py
```

#### macOS/Linux
```bash
# 方式1: 脚本启动
./start.sh

# 方式2: 命令行
python start.py
```

## 平台检测和诊断

### 自动系统检测
程序启动时会自动检测：
- 操作系统类型和版本
- Python版本
- Chrome安装状态
- 依赖包状态

### 诊断工具
```bash
# 运行平台兼容性测试
python test_platform.py
```

输出示例：
```
🖥️  系统信息:
   - 操作系统: macOS-14.7.1-arm64-arm-64bit
   - 架构: 64bit
   - Python版本: 3.12.2
   - Chrome路径: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
✅ 系统检查通过
```

## 故障排除

### Chrome未找到
**Windows**:
- 从 https://www.google.com/chrome/ 下载安装
- 确保安装在标准位置

**macOS**:
- 从App Store或官网安装Chrome
- 确保安装在 `/Applications/` 目录

**Linux**:
```bash
# Ubuntu/Debian
sudo apt install google-chrome-stable

# CentOS/RHEL
sudo yum install google-chrome-stable

# 或使用Chromium
sudo apt install chromium-browser
```

### Python版本问题
- 确保使用Python 3.7+
- Windows用户建议从官网下载
- macOS用户可使用Homebrew: `brew install python`
- Linux用户使用包管理器: `sudo apt install python3`

### 权限问题
**macOS/Linux**:
```bash
# 给启动脚本执行权限
chmod +x start.sh

# 如果遇到安全提示，在系统偏好设置中允许
```

**Windows**:
- 以管理员身份运行可能解决某些权限问题

## 技术实现

### 平台检测
```python
import platform
system = platform.system().lower()
is_windows = system == 'windows'
is_mac = system == 'darwin'
is_linux = system == 'linux'
```

### 路径处理
```python
import os
# 跨平台路径拼接
user_data_dir = os.path.join(os.getcwd(), dir_name)
# 文件名清理
safe_name = filename.replace('<>:"/\\|?*', '_')
```

### Chrome选项优化
```python
# 平台特定选项
if is_windows:
    options.extend(["--disable-dev-shm-usage", "--no-sandbox"])
elif is_mac:
    options.extend(["--no-sandbox", "--disable-dev-shm-usage"])
elif is_linux:
    options.extend(["--no-sandbox", "--disable-gpu"])
```

## 更新日志

### v2.0 - 平台兼容性版本
- ✅ 添加完整的Mac、Windows、Linux支持
- ✅ 自动Chrome路径检测
- ✅ 平台特定优化选项
- ✅ 跨平台启动脚本
- ✅ 统一的错误处理和诊断
- ✅ 改进的文件系统兼容性

### v1.x - 基础版本
- 基本的自动化功能
- 主要针对单一平台设计
