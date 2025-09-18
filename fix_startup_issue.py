#!/usr/bin/env python3
"""
修复启动卡住问题的脚本
"""

import os
import shutil
import subprocess
import time
import platform
import signal
import glob
import re

from typing import Optional

# 尝试导入psutil，如果没有则使用基础方法
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def get_local_chrome_version(chrome_path: Optional[str] = None) -> Optional[str]:
    system = platform.system().lower()
    if system == 'windows':
        try:
            import winreg  # type: ignore

            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root, r"Software\\Google\\Chrome\\BLBeacon") as key:
                        val, _ = winreg.QueryValueEx(key, "version")
                        if isinstance(val, str) and val:
                            return val.strip()
                except OSError:
                    continue
        except Exception:
            pass

    candidates = []
    if chrome_path and os.path.exists(chrome_path):
        candidates.append(chrome_path)
    candidates.extend(['chrome', 'google-chrome'])

    for bin_path in candidates:
        try:
            out = subprocess.check_output([bin_path, '--version'], stderr=subprocess.STDOUT, timeout=5)
            text = out.decode(errors='ignore').strip()
            match = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
            if match:
                return match.group(1)
        except Exception:
            continue
    return None


def get_chrome_executable_path() -> Optional[str]:
    system = platform.system().lower()
    if system == 'windows':
        candidates = [
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
            os.path.expanduser(r"~\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe"),
        ]
    elif system == 'darwin':
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        ]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return None


def install_matching_chromedriver(chrome_version_full: Optional[str], chrome_version_major: Optional[int]) -> str:
    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except Exception as exc:
        raise RuntimeError("webdriver_manager 未安装或不可用") from exc

    candidates = []
    if chrome_version_full:
        candidates.append(str(chrome_version_full))
    if chrome_version_major is not None:
        candidates.append(str(chrome_version_major))
    candidates.append(None)

    last_error = None
    for candidate in candidates:
        if candidate is None:
            try:
                return ChromeDriverManager().install()
            except Exception as exc:
                last_error = exc
                continue
        for key in ('driver_version', 'version'):
            kwargs = {key: candidate}
            try:
                return ChromeDriverManager(**kwargs).install()
            except TypeError:
                continue
            except Exception as exc:
                last_error = exc
                break
    if last_error:
        raise last_error
    raise RuntimeError("无法自动安装匹配的 ChromeDriver")

def cleanup_undetected_chromedriver():
    """清理undetected_chromedriver缓存"""
    print("🧹 清理undetected_chromedriver缓存...")

    try:
        system = platform.system().lower()

        # 根据平台确定缓存目录
        if system == 'windows':
            # Windows缓存目录
            cache_dirs = [
                os.path.join(os.path.expanduser("~"), "appdata", "roaming", "undetected_chromedriver"),
                os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "undetected_chromedriver"),
            ]
            temp_base = os.environ.get('TEMP', os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp"))
        elif system == 'darwin':  # macOS
            # macOS缓存目录
            cache_dirs = [
                os.path.join(os.path.expanduser("~"), "Library", "Caches", "undetected_chromedriver"),
                os.path.join(os.path.expanduser("~"), ".cache", "undetected_chromedriver"),
            ]
            temp_base = "/tmp"
        else:  # Linux
            # Linux缓存目录
            cache_dirs = [
                os.path.join(os.path.expanduser("~"), ".cache", "undetected_chromedriver"),
                os.path.join(os.path.expanduser("~"), ".local", "share", "undetected_chromedriver"),
            ]
            temp_base = "/tmp"

        # 清理缓存目录
        for cache_dir in cache_dirs:
            if os.path.exists(cache_dir):
                shutil.rmtree(cache_dir)
                print(f"✅ 已清理缓存: {cache_dir}")

        # 清理临时目录
        temp_patterns = [
            os.path.join(temp_base, 'scoped_dir*'),
            os.path.join(temp_base, 'chrome_*'),
            os.path.join(temp_base, '.com.google.Chrome.*'),
        ]

        for pattern in temp_patterns:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        print(f"✅ 已清理临时目录: {path}")
                    elif os.path.isfile(path):
                        os.remove(path)
                        print(f"✅ 已清理临时文件: {path}")
                except Exception as e:
                    print(f"⚠️  无法清理 {path}: {e}")

        print("✅ undetected_chromedriver缓存清理完成")
        return True

    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False

def kill_chrome_processes():
    """终止Chrome进程"""
    print("🔄 终止Chrome进程...")

    try:
        system = platform.system().lower()
        killed_count = 0

        if HAS_PSUTIL:
            # 使用psutil精确终止进程
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if any(name in proc_name for name in ['chrome', 'chromedriver']):
                        proc.terminate()
                        killed_count += 1
                        print(f"✅ 已终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        else:
            # 使用系统命令终止进程
            if system == 'windows':
                # Windows
                commands = [
                    ['taskkill', '/F', '/IM', 'chrome.exe'],
                    ['taskkill', '/F', '/IM', 'chromedriver.exe'],
                ]
            else:
                # macOS/Linux
                commands = [
                    ['pkill', '-f', 'chrome'],
                    ['pkill', '-f', 'chromedriver'],
                ]

            for cmd in commands:
                try:
                    result = subprocess.run(cmd, capture_output=True, check=False)
                    if result.returncode == 0:
                        killed_count += 1
                except FileNotFoundError:
                    # 命令不存在，跳过
                    pass

        if killed_count > 0:
            print(f"✅ 已终止 {killed_count} 个Chrome相关进程")
        else:
            print("ℹ️  未找到需要终止的Chrome进程")

        return True

    except Exception as e:
        print(f"❌ 终止进程失败: {e}")
        return False

def test_simple_chrome():
    """测试简单的Chrome启动"""
    print("🧪 测试简单Chrome启动...")

    try:
        import undetected_chromedriver as uc
        import threading
        import queue

        # 平台特定的配置
        system = platform.system().lower()
        options = uc.ChromeOptions()

        chrome_path = get_chrome_executable_path()
        chrome_version_full = get_local_chrome_version(chrome_path)
        chrome_version_major = None
        try:
            if chrome_version_full:
                chrome_version_major = int(chrome_version_full.split('.')[0])
        except Exception:
            chrome_version_major = None

        # 基础选项
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-gpu-logging")
        options.add_argument("--silent")

        # 平台特定选项
        if system == 'linux':
            options.add_argument("--disable-gpu")
        elif system == 'darwin':  # macOS
            options.add_argument("--disable-web-security")
            options.add_argument("--disable-features=VizDisplayCompositor")

        # 使用线程和超时机制
        result_queue = queue.Queue()

        def create_driver():
            try:
                print("正在创建Chrome实例...")
                driver = uc.Chrome(
                    options=options,
                    use_subprocess=False,
                    log_level=3,
                    version_main=chrome_version_major,
                    browser_executable_path=chrome_path if chrome_path else None,
                    driver_executable_path=None
                )
                result_queue.put(('success', driver))
            except Exception as e:
                result_queue.put(('error', str(e)))

        # 启动线程
        thread = threading.Thread(target=create_driver)
        thread.daemon = True
        thread.start()

        # 等待结果，最多30秒
        thread.join(timeout=30)

        if thread.is_alive():
            print("❌ undetected_chromedriver启动超时 (30秒)")
            print("🔄 尝试使用标准selenium webdriver...")
            return test_standard_chrome()

        try:
            result_type, result_data = result_queue.get_nowait()
            if result_type == 'error':
                print(f"❌ Chrome启动失败: {result_data}")
                return False

            driver = result_data
            print("✅ Chrome启动成功")

            # 简单测试 - 使用更稳定的网站
            try:
                print("正在测试页面访问...")
                driver.get("data:text/html,<html><body><h1>Test Page</h1></body></html>")
                time.sleep(1)
                print(f"页面标题: {driver.title}")
                print("✅ 页面访问成功")
            except Exception as e:
                print(f"⚠️  页面访问失败，但Chrome启动正常: {e}")

            # 安全关闭
            try:
                driver.quit()
                print("✅ Chrome已安全关闭")
            except:
                pass

            print("✅ 测试完成")
            return True

        except queue.Empty:
            print("❌ 未收到Chrome启动结果")
            return False

    except Exception as e:
        print(f"❌ undetected_chromedriver测试失败: {e}")
        print("🔄 尝试使用标准selenium webdriver...")
        return test_standard_chrome()

def test_standard_chrome():
    """使用标准selenium测试Chrome启动"""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options

        print("正在使用标准webdriver测试...")

        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless")  # 使用无头模式避免卡住

        chrome_path = get_chrome_executable_path()
        if chrome_path:
            options.binary_location = chrome_path
        chrome_version_full = get_local_chrome_version(chrome_path)
        chrome_version_major = None
        try:
            if chrome_version_full:
                chrome_version_major = int(chrome_version_full.split('.')[0])
        except Exception:
            chrome_version_major = None

        driver_path = install_matching_chromedriver(chrome_version_full, chrome_version_major)
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)

        print("✅ 标准Chrome启动成功")

        # 简单测试
        driver.get("data:text/html,<html><body><h1>Test</h1></body></html>")
        print("✅ 页面访问成功")

        driver.quit()
        print("✅ 标准Chrome测试完成")
        return True

    except Exception as e:
        print(f"❌ 标准webdriver也失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 修复启动卡住问题 - 跨平台版本")
    print("=" * 60)

    # 显示平台信息
    system = platform.system()
    print(f"🖥️  检测到系统: {system}")
    print(f"📦 psutil支持: {'✅ 是' if HAS_PSUTIL else '❌ 否 (将使用基础方法)'}")
    print()
    print("这个脚本将清理缓存并测试Chrome启动")
    print()

    # 步骤1：终止进程
    kill_chrome_processes()
    time.sleep(2)

    # 步骤2：清理缓存
    cleanup_undetected_chromedriver()
    time.sleep(2)

    # 步骤3：测试启动
    if test_simple_chrome():
        print("\n🎉 修复成功！")
        print("现在可以重新运行主脚本了:")
        if system == 'Windows':
            print("start.bat 或 python start.py")
        else:
            print("./start.sh 或 python start.py")
    else:
        print("\n⚠️  仍有问题，尝试以下解决方案:")
        print("1. 重启计算机")
        if system == 'Windows':
            print("2. 以管理员身份运行")
        else:
            print("2. 使用sudo权限运行 (如果需要)")
        print("3. 检查Chrome是否正确安装")
        print("4. 尝试更新Chrome浏览器")

        if system == 'Darwin':  # macOS特定建议
            print("\n🍎 macOS特定解决方案:")
            print("5. 在系统偏好设置 > 安全性与隐私中允许Chrome")
            print("6. 尝试重新安装Chrome浏览器")
            print("7. 检查是否有防病毒软件阻止Chrome")

        print("\n🔧 技术解决方案:")
        print("8. 尝试使用有头模式而不是无头模式")
        print("9. 清理所有Chrome用户数据目录")
        print("10. 使用传统selenium而不是undetected_chromedriver")

        if not HAS_PSUTIL:
            print("\n💡 建议安装psutil以获得更好的进程管理:")
            print("pip install psutil")

if __name__ == "__main__":
    main()
