#!/usr/bin/env python3
"""
平台兼容性工具模块
支持Mac和Windows平台的通用性
"""

import os
import sys
import platform
import logging
from pathlib import Path


class PlatformUtils:
    """平台兼容性工具类"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.is_windows = self.system == 'windows'
        self.is_mac = self.system == 'darwin'
        self.is_linux = self.system == 'linux'
        
        # 设置日志
        self.logger = logging.getLogger(__name__)
    
    def get_system_info(self):
        """获取系统信息"""
        return {
            'system': self.system,
            'platform': platform.platform(),
            'architecture': platform.architecture(),
            'python_version': sys.version,
            'is_windows': self.is_windows,
            'is_mac': self.is_mac,
            'is_linux': self.is_linux
        }
    
    def get_chrome_executable_path(self):
        """获取Chrome可执行文件路径"""
        chrome_paths = []
        
        if self.is_windows:
            # Windows Chrome路径
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe"),
                r"C:\Users\%USERNAME%\AppData\Local\Google\Chrome\Application\chrome.exe"
            ]
        elif self.is_mac:
            # Mac Chrome路径
            chrome_paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            ]
        elif self.is_linux:
            # Linux Chrome路径
            chrome_paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium"
            ]
        
        # 检查路径是否存在
        for path in chrome_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                self.logger.info(f"找到Chrome路径: {expanded_path}")
                return expanded_path
        
        self.logger.warning("未找到Chrome可执行文件，将使用webdriver-manager自动下载")
        return None
    
    def get_user_data_dir(self, site_name):
        """获取用户数据目录路径"""
        # 确保site_name是安全的文件名
        safe_site_name = self.sanitize_filename(site_name)
        
        # 基础目录名
        dir_name = f"chrome_user_data_{safe_site_name}"
        
        # 获取当前工作目录
        current_dir = os.getcwd()
        
        # 使用os.path.join确保跨平台兼容
        user_data_dir = os.path.join(current_dir, dir_name)
        
        # 确保目录存在
        os.makedirs(user_data_dir, exist_ok=True)
        
        return user_data_dir
    
    def sanitize_filename(self, filename):
        """清理文件名，移除不安全字符"""
        # 移除或替换不安全的字符
        unsafe_chars = '<>:"/\\|?*'
        for char in unsafe_chars:
            filename = filename.replace(char, '_')
        
        # 移除多余的空格和点
        filename = filename.strip(' .')
        
        # 限制长度
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename
    
    def get_log_filename(self, site_name):
        """获取日志文件名"""
        safe_site_name = self.sanitize_filename(site_name)
        return f"{safe_site_name}_automation.log"
    
    def get_chrome_options_for_platform(self):
        """获取平台特定的Chrome选项"""
        options = []
        
        if self.is_windows:
            # Windows特定选项
            options.extend([
                "--disable-dev-shm-usage",  # 避免Windows上的共享内存问题
                "--no-sandbox",  # Windows上通常需要
            ])
        elif self.is_mac:
            # Mac特定选项
            options.extend([
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ])
        elif self.is_linux:
            # Linux特定选项
            options.extend([
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",  # Linux上可能需要
            ])
        
        # 通用选项
        options.extend([
            "--disable-blink-features=AutomationControlled",
            "--window-size=1920,1080",
            "--disable-web-security",  # 某些网站可能需要
            "--allow-running-insecure-content",
        ])
        
        return options
    
    def check_dependencies(self):
        """检查平台特定的依赖"""
        issues = []
        
        # 检查Python版本
        if sys.version_info < (3, 7):
            issues.append("Python版本过低，建议使用Python 3.7+")
        
        # 检查Chrome是否安装
        chrome_path = self.get_chrome_executable_path()
        if not chrome_path:
            if self.is_windows:
                issues.append("未找到Chrome浏览器，请从 https://www.google.com/chrome/ 下载安装")
            elif self.is_mac:
                issues.append("未找到Chrome浏览器，请从App Store或官网安装")
            elif self.is_linux:
                issues.append("未找到Chrome浏览器，请使用包管理器安装: sudo apt install google-chrome-stable")
        
        return issues
    
    def print_system_info(self):
        """打印系统信息"""
        info = self.get_system_info()
        print("🖥️  系统信息:")
        print(f"   - 操作系统: {info['platform']}")
        print(f"   - 架构: {info['architecture'][0]}")
        print(f"   - Python版本: {info['python_version'].split()[0]}")
        
        # 检查Chrome
        chrome_path = self.get_chrome_executable_path()
        if chrome_path:
            print(f"   - Chrome路径: {chrome_path}")
        else:
            print("   - Chrome: 将自动下载")
        
        # 检查依赖问题
        issues = self.check_dependencies()
        if issues:
            print("⚠️  发现问题:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ 系统检查通过")


# 创建全局实例
platform_utils = PlatformUtils()


def get_platform_utils():
    """获取平台工具实例"""
    return platform_utils
