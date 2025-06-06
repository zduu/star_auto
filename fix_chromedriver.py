#!/usr/bin/env python3
"""
ChromeDriver修复脚本
解决 [WinError 193] %1 不是有效的 Win32 应用程序 错误
"""

import os
import shutil
import requests
import zipfile
import platform
from pathlib import Path

def get_chrome_version():
    """获取Chrome版本"""
    import subprocess
    import winreg

    try:
        # 方法1: 从注册表获取Chrome版本 (Windows)
        if platform.system() == 'Windows':
            try:
                # 尝试从注册表读取Chrome版本
                key_path = r"SOFTWARE\Google\Chrome\BLBeacon"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                    major_version = version.split('.')[0]
                    print(f"从注册表获取Chrome版本: {version}")
                    return major_version
            except:
                pass

            try:
                # 尝试从系统注册表读取
                key_path = r"SOFTWARE\Google\Chrome\BLBeacon"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    version, _ = winreg.QueryValueEx(key, "version")
                    major_version = version.split('.')[0]
                    print(f"从系统注册表获取Chrome版本: {version}")
                    return major_version
            except:
                pass

        # 方法2: 通过命令行获取版本
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        ]

        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                try:
                    result = subprocess.run([chrome_path, '--version'],
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        version_str = result.stdout.strip()
                        # 提取版本号，格式如 "Google Chrome 131.0.6778.86"
                        version = version_str.split()[-1]
                        major_version = version.split('.')[0]
                        print(f"从命令行获取Chrome版本: {version}")
                        return major_version
                except:
                    continue

    except Exception as e:
        print(f"获取Chrome版本失败: {e}")

    # 如果都失败了，返回一个常用的版本
    print("无法自动检测Chrome版本，使用默认版本131")
    return "131"

def download_chromedriver(version):
    """下载正确的ChromeDriver版本"""
    print(f"正在下载ChromeDriver版本 {version}...")

    # 对于Chrome 115+，使用新的下载方式
    if int(version) >= 115:
        return download_chromedriver_new(version)
    else:
        return download_chromedriver_old(version)

def download_chromedriver_new(version):
    """下载新版本的ChromeDriver (Chrome 115+)"""
    print("使用新的ChromeDriver下载方式...")

    # 新的ChromeDriver下载API
    api_url = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"

    try:
        print("获取可用版本列表...")
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # 查找匹配的版本
        matching_version = None
        for version_info in data.get('versions', []):
            if version_info['version'].startswith(f"{version}."):
                matching_version = version_info
                break

        if not matching_version:
            print(f"未找到Chrome {version}的匹配版本，尝试使用最新稳定版本")
            # 使用最后一个版本
            matching_version = data['versions'][-1]

        full_version = matching_version['version']
        print(f"找到匹配版本: {full_version}")

        # 查找Windows版本的下载链接
        downloads = matching_version.get('downloads', {})
        chromedriver_downloads = downloads.get('chromedriver', [])

        win32_download = None
        for download in chromedriver_downloads:
            if download['platform'] == 'win32':
                win32_download = download
                break

        if not win32_download:
            print("未找到Windows版本的ChromeDriver下载链接")
            return None

        download_url = win32_download['url']
        print(f"下载地址: {download_url}")

        return download_and_extract_chromedriver(download_url, full_version)

    except Exception as e:
        print(f"使用新API下载失败: {e}")
        return None

def download_chromedriver_old(version):
    """下载旧版本的ChromeDriver (Chrome < 115)"""
    print("使用旧的ChromeDriver下载方式...")

    # ChromeDriver下载URL
    base_url = "https://chromedriver.storage.googleapis.com"

    # 获取最新的版本号
    try:
        latest_url = f"{base_url}/LATEST_RELEASE_{version}"
        response = requests.get(latest_url, timeout=10)
        if response.status_code == 200:
            full_version = response.text.strip()
            print(f"找到完整版本号: {full_version}")
        else:
            print(f"无法获取版本信息，使用默认版本: {version}.0.0.0")
            full_version = f"{version}.0.0.0"
    except Exception as e:
        print(f"获取版本信息失败: {e}")
        full_version = f"{version}.0.0.0"

    # 下载URL
    download_url = f"{base_url}/{full_version}/chromedriver_win32.zip"

    return download_and_extract_chromedriver(download_url, full_version)

def download_and_extract_chromedriver(download_url, full_version):
    """下载并解压ChromeDriver"""
    
    try:
        print(f"下载地址: {download_url}")
        response = requests.get(download_url, timeout=60)
        response.raise_for_status()

        # 保存到临时文件
        temp_zip = "chromedriver_temp.zip"
        with open(temp_zip, 'wb') as f:
            f.write(response.content)

        print("下载完成，正在解压...")

        # 解压
        with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
            zip_ref.extractall("chromedriver_temp")

        # 查找chromedriver.exe文件（可能在子目录中）
        chromedriver_exe = None
        for root, dirs, files in os.walk("chromedriver_temp"):
            for file in files:
                if file == "chromedriver.exe":
                    chromedriver_exe = os.path.join(root, file)
                    break
            if chromedriver_exe:
                break

        if chromedriver_exe and os.path.exists(chromedriver_exe):
            # 创建目标目录
            target_dir = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "chromedriver", "win64", full_version, "chromedriver-win32")
            os.makedirs(target_dir, exist_ok=True)

            target_path = os.path.join(target_dir, "chromedriver.exe")
            shutil.move(chromedriver_exe, target_path)

            print(f"ChromeDriver已安装到: {target_path}")

            # 清理临时文件
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            if os.path.exists("chromedriver_temp"):
                shutil.rmtree("chromedriver_temp")

            return target_path
        else:
            print("解压后未找到chromedriver.exe文件")
            # 列出解压的文件以便调试
            print("解压的文件:")
            for root, dirs, files in os.walk("chromedriver_temp"):
                for file in files:
                    print(f"  {os.path.join(root, file)}")
            return None

    except Exception as e:
        print(f"下载ChromeDriver失败: {e}")
        # 清理临时文件
        if os.path.exists("chromedriver_temp.zip"):
            os.remove("chromedriver_temp.zip")
        if os.path.exists("chromedriver_temp"):
            shutil.rmtree("chromedriver_temp")
        return None

def clear_webdriver_cache():
    """清理WebDriver Manager缓存"""
    cache_dir = os.path.join(os.path.expanduser("~"), ".wdm")
    if os.path.exists(cache_dir):
        try:
            shutil.rmtree(cache_dir)
            print("已清理WebDriver Manager缓存")
            return True
        except Exception as e:
            print(f"清理缓存失败: {e}")
            return False
    else:
        print("缓存目录不存在")
        return True

def main():
    print("ChromeDriver修复工具")
    print("=" * 40)
    
    # 检查系统
    if platform.system() != 'Windows':
        print("此脚本仅适用于Windows系统")
        return
    
    # 获取Chrome版本
    chrome_version = get_chrome_version()
    if not chrome_version:
        print("无法检测Chrome版本，请确保Chrome已正确安装")
        return
    
    print(f"检测到Chrome主版本: {chrome_version}")
    
    # 清理缓存
    print("\n步骤1: 清理旧的ChromeDriver缓存...")
    clear_webdriver_cache()
    
    # 下载新的ChromeDriver
    print(f"\n步骤2: 下载匹配的ChromeDriver...")
    driver_path = download_chromedriver(chrome_version)
    
    if driver_path:
        print(f"\n✅ ChromeDriver修复完成!")
        print(f"   安装路径: {driver_path}")
        print("\n现在可以重新运行您的自动化脚本了。")
    else:
        print("\n❌ ChromeDriver修复失败")
        print("请尝试手动下载ChromeDriver:")
        print(f"1. 访问: https://chromedriver.chromium.org/")
        print(f"2. 下载与Chrome版本 {chrome_version} 匹配的ChromeDriver")
        print(f"3. 解压到任意目录，并记住路径")

if __name__ == "__main__":
    main()
