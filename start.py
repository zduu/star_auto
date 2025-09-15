#!/usr/bin/env python3
"""
极简版 Discourse 自动化脚本（单文件）
- 仅依赖本文件与 fix_startup_issue.py
- 支持随机浏览或直接链接浏览，支持可选点赞
- 跨平台（Windows/macOS/Linux）
"""

import os
import sys
import time
import random
import platform
import json
import argparse
import subprocess
import re
import atexit
import signal

from typing import Optional
from urllib.parse import urlparse


def get_local_chrome_version(chrome_path=None):
    """Return full Chrome version string like '139.0.7258.128' if detectable.
    Prefer Windows registry on Windows; otherwise try `chrome --version`.
    """
    system = platform.system().lower()
    # Windows: query registry BLBeacon version first (most reliable)
    if system == 'windows':
        try:
            import winreg  # type: ignore
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(root, r"Software\\Google\\Chrome\\BLBeacon") as k:
                        val, _ = winreg.QueryValueEx(k, "version")
                        if isinstance(val, str) and val:
                            return val.strip()
                except OSError:
                    pass
        except Exception:
            pass

    # Fallback: invoke chrome binary with --version
    candidates = []
    if chrome_path and os.path.exists(chrome_path):
        candidates.append(chrome_path)
    # Try PATH fallback
    candidates.append('chrome')
    candidates.append('google-chrome')
    for bin_path in candidates:
        try:
            out = subprocess.check_output([bin_path, '--version'], stderr=subprocess.STDOUT, timeout=5)
            s = out.decode(errors='ignore').strip()
            # Outputs like: "Google Chrome 139.0.7258.128" or "Chromium 119.0..."
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", s)
            if m:
                return m.group(1)
        except Exception:
            continue
    return None


def check_dependencies():
    try:
        import selenium  # noqa: F401
        import undetected_chromedriver  # noqa: F401
        from webdriver_manager.chrome import ChromeDriverManager  # noqa: F401
        return True
    except Exception:
        return False


def get_chrome_executable_path():
    system = platform.system().lower()
    candidates = []
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
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def setup_driver(headless=False, user_data_dir=None):
    """优先使用 undetected_chromedriver，失败时回退到标准 webdriver"""
    chrome_path = get_chrome_executable_path()
    system = platform.system().lower()
    chrome_version_full = get_local_chrome_version(chrome_path)
    chrome_version_major = None
    try:
        if chrome_version_full:
            chrome_version_major = int(chrome_version_full.split('.')[0])
    except Exception:
        chrome_version_major = None

    # 首选：undetected_chromedriver
    try:
        import undetected_chromedriver as uc
        uc_options = uc.ChromeOptions()
        uc_options.add_argument("--no-sandbox")
        uc_options.add_argument("--disable-dev-shm-usage")
        uc_options.add_argument("--disable-blink-features=AutomationControlled")
        uc_options.add_argument("--window-size=1920,1080")
        if system == 'linux':
            uc_options.add_argument("--disable-gpu")
        if headless:
            uc_options.add_argument("--headless=new")
        if chrome_path:
            uc_options.binary_location = chrome_path
        # 持久用户数据目录（复用登录状态）
        if user_data_dir:
            uc_options.add_argument(f"--user-data-dir={user_data_dir}")
            uc_options.add_argument("--profile-directory=Default")
            uc_options.add_argument("--no-first-run")
            uc_options.add_argument("--no-default-browser-check")

        driver = uc.Chrome(
            options=uc_options,
            # Pin to detected major version if available to avoid mismatch
            version_main=chrome_version_major,
            driver_executable_path=None,
            browser_executable_path=chrome_path if chrome_path else None,
            use_subprocess=False,
            log_level=3,
        )
        return driver
    except Exception as e:
        print(f"⚠️ undetected_chromedriver 启动失败: {e}")

    # 回退：标准 selenium + webdriver_manager
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager

        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        if system == 'linux':
            options.add_argument("--disable-gpu")
        if headless:
            options.add_argument("--headless=new")
        if chrome_path:
            options.binary_location = chrome_path
        # 持久用户数据目录（复用登录状态）
        if user_data_dir:
            options.add_argument(f"--user-data-dir={user_data_dir}")
            options.add_argument("--profile-directory=Default")
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")

        # If we detected local Chrome version, request matching driver version
        try:
            if chrome_version_major:
                service = Service(ChromeDriverManager(driver_version=str(chrome_version_major)).install())
            else:
                service = Service(ChromeDriverManager().install())
        except TypeError:
            # Fallback for older webdriver-manager API (uses 'version' instead of 'driver_version')
            if chrome_version_major:
                service = Service(ChromeDriverManager(version=str(chrome_version_major)).install())
            else:
                service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"❌ 标准 webdriver 也启动失败: {e}")
        print("👉 请先运行: python fix_startup_issue.py 进行故障排查")
        raise


# -----------------------
# Cross-platform cleanup
# -----------------------
_CLEANUP_CTX = {
    'driver': None,            # type: Optional[object]
    'user_data_dir': None,     # type: Optional[str]
    'handlers_installed': False,
}


def _kill_chrome_for_profile(user_data_dir: Optional[str]):
    if not user_data_dir:
        return
    try:
        import psutil  # type: ignore
    except Exception:
        psutil = None

    try:
        system = platform.system().lower()
        if psutil:
            targets = []
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = (p.info.get('name') or '').lower()
                    cmdline = p.info.get('cmdline') or []
                    cmd = ' '.join(cmdline)
                    if ('chrome' in name or 'google chrome' in name) and (user_data_dir in cmd):
                        targets.append(p)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            # Graceful terminate, then kill if needed
            for p in targets:
                try:
                    p.terminate()
                except Exception:
                    pass
            if targets:
                psutil.wait_procs(targets, timeout=5)
            for p in targets:
                try:
                    if p.is_running():
                        p.kill()
                except Exception:
                    pass
            # Also try to stop stray chromedriver processes (best effort)
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = (p.info.get('name') or '').lower()
                    if 'chromedriver' in name:
                        p.terminate()
                except Exception:
                    continue
        else:
            if system == 'windows':
                # Best-effort: this may close all Chrome instances
                subprocess.call(['taskkill', '/F', '/IM', 'chrome.exe'])
                subprocess.call(['taskkill', '/F', '/IM', 'chromedriver.exe'])
            else:
                # Narrow down by profile dir to avoid killing user's real Chrome
                try:
                    subprocess.call(['pkill', '-f', f'Google Chrome.*--user-data-dir={user_data_dir}'])
                except Exception:
                    # Fallback broad kill (avoid unless necessary)
                    subprocess.call(['pkill', '-f', 'chromedriver'])
    except Exception:
        # Best-effort cleanup; ignore errors
        pass


def _cleanup():
    drv = _CLEANUP_CTX.get('driver')
    user_data_dir = _CLEANUP_CTX.get('user_data_dir')
    # Try closing the webdriver session first
    try:
        if drv:
            try:
                drv.quit()
            except Exception:
                pass
    finally:
        # Ensure Chrome for this profile is not left hanging
        _kill_chrome_for_profile(user_data_dir)


def _install_cleanup_handlers():
    if _CLEANUP_CTX.get('handlers_installed'):
        return
    _CLEANUP_CTX['handlers_installed'] = True

    # Run on normal interpreter exit
    atexit.register(_cleanup)

    # Handle common termination signals so Chrome is closed on macOS/Linux
    def handler(signum, frame):  # noqa: ARG001
        try:
            _cleanup()
        finally:
            # Exit immediately to avoid running further code paths
            os._exit(128 + int(signum))

    for sig_name in ('SIGINT', 'SIGTERM', 'SIGHUP'):
        if hasattr(signal, sig_name):
            try:
                signal.signal(getattr(signal, sig_name), handler)
            except Exception:
                # Some environments disallow setting handlers; ignore
                pass


def wait_for_cloudflare(driver, headless=False, max_wait=30):
    # 无头模式下适当等待 Cloudflare 页面
    if not headless:
        return
    try:
        for _ in range(max_wait // 3):
            src = driver.page_source.lower()
            if all(k not in src for k in ["cloudflare", "just a moment", "checking your browser"]):
                return
            time.sleep(3)
    except Exception:
        pass


def get_random_topic(driver, base_url):
    from selenium.webdriver.common.by import By

    def is_topic_url(url: str) -> bool:
        if not url:
            return False
        if not url.startswith(base_url):
            return False
        # 只接受真实主题链接，例如 /t/slug/12345
        if "/t/" not in url:
            return False
        # 排除标签、用户、分类等页面
        blocked = ["/tag", "/tags", "/u/", "/users/", "/c/"]
        return not any(b in url for b in blocked)

    # 更精确的选择器，避免匹配到标签链接
    selectors = [
        "a.raw-topic-link",
        "a.title",
        ".topic-list-item .main-link a",
        "tr.topic-list-item .main-link a",
        "a[href*='/t/']",
    ]

    topics = []
    for _ in range(3):
        for css in selectors:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, css)
                topics.extend(els)
            except Exception:
                continue
        # 过滤成候选项
        candidates = []
        for el in topics:
            try:
                href = el.get_attribute('href')
                if is_topic_url(href):
                    candidates.append(el)
            except Exception:
                continue
        if candidates:
            return random.choice(candidates)
        topics.clear()
        time.sleep(2)
    return None


def like_visible_posts(driver):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    liked = 0

    # Prefer robust Discourse selectors; fall back to title/aria-label in multiple languages
    selectors = [
        ".post-controls button[data-action='like']",
        "button.toggle-like",
        ".actions button.like",
        "button[aria-label*='Like'], button[aria-label*='赞'], button[title*='Like'], button[title*='赞']",
    ]

    seen_positions = set()
    for css in selectors:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, css)
        except Exception:
            buttons = []
        for btn in buttons:
            try:
                # Only operate on real buttons
                tag = (btn.tag_name or '').lower()
                if tag != 'button':
                    continue

                # De-duplicate by location on screen
                loc = btn.location or {}
                key = (int(loc.get('x', 0)), int(loc.get('y', 0)))
                if key in seen_positions:
                    continue
                seen_positions.add(key)

                # Skip if already liked
                aria = (btn.get_attribute('aria-pressed') or '').lower()
                cls = (btn.get_attribute('class') or '').lower()
                if 'liked' in cls or 'has-like' in cls or aria == 'true':
                    continue

                # Scroll into view and wait until clickable, then click via JS for reliability
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                except Exception:
                    pass
                try:
                    WebDriverWait(driver, 3).until(EC.element_to_be_clickable(btn))
                except Exception:
                    pass
                try:
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    try:
                        btn.click()
                    except Exception:
                        continue

                # Confirm state change; some sites require a short debounce
                ok = False
                for _ in range(5):
                    time.sleep(0.2)
                    aria2 = (btn.get_attribute('aria-pressed') or '').lower()
                    cls2 = (btn.get_attribute('class') or '').lower()
                    if 'liked' in cls2 or 'has-like' in cls2 or aria2 == 'true':
                        ok = True
                        break
                if ok:
                    liked += 1
            except Exception:
                continue
    return liked


def scroll_and_read(driver, enable_like=False, max_scrolls=200):
    last_height = 0
    stable = 0
    total_liked = 0
    for i in range(max_scrolls):
        if enable_like:
            total_liked += like_visible_posts(driver)
        driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(random.uniform(0.6, 1.4))
        h = driver.execute_script("return document.body.scrollHeight")
        if h == last_height:
            stable += 1
        else:
            stable = 0
            last_height = h
        if stable >= 3:
            break
    return total_liked


def ensure_login(driver, base_url):
    from selenium.webdriver.common.by import By
    try:
        driver.get(base_url)
        time.sleep(3)
        # 检查是否存在明显的登录按钮
        login_candidates = driver.find_elements(By.CSS_SELECTOR, "a[href*='login'], .login-button, button.login-button")
        if login_candidates:
            print("ℹ️ 检测到未登录状态，请在打开的浏览器中手动登录后返回终端。")
            print("   登录完成后本脚本会自动继续……(最多等待5分钟)")
            start = time.time()
            while time.time() - start < 300:
                time.sleep(3)
                driver.get(base_url)
                time.sleep(2)
                if not driver.find_elements(By.CSS_SELECTOR, "a[href*='login'], .login-button, button.login-button"):
                    print("✅ 已检测到登录状态")
                    return True
            print("⚠️ 登录超时，继续尝试未登录流程……")
        return True
    except Exception:
        return True


def run_random_mode(driver, base_url, cycles, enable_like, headless):
    from selenium.webdriver.common.by import By
    for idx in range(cycles):
        print(f"➡️  循环 {idx + 1}/{cycles}")
        driver.get(base_url)
        wait_for_cloudflare(driver, headless=headless)
        time.sleep(3)
        topic = get_random_topic(driver, base_url)
        if not topic:
            print("⚠️ 未找到帖子，跳过本次循环")
            continue
        title = (topic.text or '').strip()[:50]
        print(f"🧭 打开帖子: {title}")
        try:
            topic.click()
        except Exception:
            href = topic.get_attribute('href')
            if href:
                driver.get(href)
        time.sleep(2)
        liked = scroll_and_read(driver, enable_like=enable_like)
        if enable_like:
            print(f"✅ 已浏览并点赞 {liked} 次")
        else:
            print("✅ 已浏览（未开启点赞）")


def run_direct_mode(driver, url, enable_like, headless):
    print(f"🧭 打开链接: {url}")
    driver.get(url)
    wait_for_cloudflare(driver, headless=headless)
    time.sleep(3)
    liked = scroll_and_read(driver, enable_like=enable_like)
    if enable_like:
        print(f"✅ 已浏览并点赞 {liked} 次")
    else:
        print("✅ 已浏览（未开启点赞）")


def ensure_dependencies():
    if check_dependencies():
        return True
    print("⚠️ 缺少依赖：selenium / undetected_chromedriver / webdriver_manager")
    # 在无参数场景下，尽量降低门槛，提供自动安装
    ans = input("是否自动安装依赖? (Y/n): ").strip().lower()
    if ans in ['', 'y', 'yes']:
        try:
            # 优先使用 requirements.txt
            if os.path.exists('requirements.txt'):
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
            else:
                subprocess.check_call([sys.executable, '-m', 'pip', 'install',
                                       'selenium', 'undetected-chromedriver', 'webdriver-manager'])
            print('✅ 依赖安装完成\n')
            return True
        except Exception as e:
            print(f"❌ 自动安装失败: {e}")
            print("请手动执行: pip install -r requirements.txt")
            return False
    else:
        print("请先安装依赖后再运行: pip install -r requirements.txt")
        return False


def main():
    print("=" * 60)
    print("🌐 Discourse 自动化（极简单文件版）")
    print("=" * 60)

    # 依赖检查（支持自动安装）
    if not ensure_dependencies():
        return

    # 解析参数
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument('--configure', action='store_true', help='交互式配置并保存到 settings.json')
    parser.add_argument('--base-url', dest='base_url', help='网站主页 URL，如 https://shuiyuan.sjtu.edu.cn')
    parser.add_argument('--mode', choices=['random', 'direct'], help='运行模式')
    parser.add_argument('--url', help='当 mode=direct 时的帖子链接')
    parser.add_argument('--cycles', type=int, help='随机浏览模式循环次数')
    parser.add_argument('--headless', action='store_true', help='启用无头模式')
    parser.add_argument('--no-headless', action='store_true', help='禁用无头模式')
    parser.add_argument('--like', action='store_true', help='启用点赞')
    parser.add_argument('--no-like', action='store_true', help='禁用点赞')
    args = parser.parse_args()

    # 配置文件加载/保存
    def load_settings(path='settings.json'):
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def save_settings(settings, path='settings.json'):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            print(f"✅ 已保存配置到 {path}")
        except Exception as e:
            print(f"⚠️ 保存配置失败: {e}")

    def do_configure():
        print("\n🛠️  配置网站与默认参数")
        current = load_settings()
        def ask(prompt, default=None):
            sfx = f" (默认: {default})" if default not in [None, ''] else ''
            val = input(f"{prompt}{sfx}: ").strip()
            return val if val else default
        base = ask('网站主页URL', current.get('base_url', 'https://shuiyuan.sjtu.edu.cn'))
        cycles_def = current.get('default_cycles', 5)
        try:
            cyc = int(ask('默认循环次数', cycles_def))
        except Exception:
            cyc = cycles_def
        head = ask('默认无头模式? (y/n)', 'n').lower() in ['y', 'yes']
        like = ask('默认启用点赞? (y/n)', 'y').lower() not in ['n', 'no']
        settings = {
            'base_url': base,
            'default_cycles': max(1, int(cyc)),
            'default_headless': bool(head),
            'default_like': bool(like),
        }
        save_settings(settings)

    # 无需指令即可运行：首次运行自动进入配置向导
    if args.configure:
        do_configure()
        return

    settings = load_settings()
    if not settings or 'base_url' not in settings:
        print('\n🧭 检测到首次运行，进入一次性配置向导...')
        do_configure()
        settings = load_settings()

    # 参数与默认值合并
    base_url = args.base_url or settings.get('base_url') or 'https://shuiyuan.sjtu.edu.cn'
    cycles = args.cycles if args.cycles is not None else int(settings.get('default_cycles', 5))
    headless = args.headless or (settings.get('default_headless', False) and not args.no_headless)
    if args.no_headless:
        headless = False
    enable_like = True
    if args.like:
        enable_like = True
    elif args.no_like:
        enable_like = False
    else:
        enable_like = bool(settings.get('default_like', True))

    # 未通过指令指定时，提供模式选择（不需要命令行参数）
    mode = args.mode
    if not mode:
        print("\n📋 运行模式: 1=随机浏览, 2=直接链接")
        raw = input("请选择(1/2, 默认1): ").strip()
        mode = 'direct' if raw == '2' else 'random'
    direct_url = args.url

    # 若缺少必要输入则交互补足
    if mode == 'direct' and not direct_url:
        direct_url = input('请输入帖子链接(URL): ').strip()
        if not direct_url:
            print('❌ 未提供链接，退出')
            return

    if mode == 'random' and (args.cycles is None):
        try:
            raw = input(f"请输入循环次数(默认{cycles}): ").strip()
            if raw:
                cycles = max(1, int(raw))
        except Exception:
            pass

    if args.headless is False and args.no_headless is False:
        # 未通过参数指定时，询问一次
        ans = input(f"是否无头模式? (y/n, 默认{'y' if headless else 'n'}): ").strip().lower()
        if ans in ['y', 'yes']:
            headless = True
        elif ans in ['n', 'no']:
            headless = False

    if not (args.like or args.no_like):
        ans = input(f"是否启用点赞? (y/n, 默认{'y' if enable_like else 'n'}): ").strip().lower()
        if ans in ['y', 'yes']:
            enable_like = True
        elif ans in ['n', 'no']:
            enable_like = False

    # 概览
    print('\n配置概览:')
    print(f"- 站点: {base_url}")
    print(f"- 模式: {mode}")
    if mode == 'direct':
        print(f"- 链接: {direct_url}")
    else:
        print(f"- 循环: {cycles}")
    print(f"- 无头: {'是' if headless else '否'}")
    print(f"- 点赞: {'启用' if enable_like else '禁用'}")

    # 启动浏览器（按站点使用持久用户数据目录，复用登录状态）
    driver = None
    try:
        def get_user_data_dir_for_site(site_url: str):
            try:
                host = urlparse(site_url).netloc or 'default'
            except Exception:
                host = 'default'
            safe_host = re.sub(r"[^a-zA-Z0-9_.-]", "_", host)
            root = os.path.join(os.path.abspath(os.getcwd()), ".chrome-profiles")
            path = os.path.join(root, safe_host)
            os.makedirs(path, exist_ok=True)
            return path

        user_data_dir = get_user_data_dir_for_site(base_url)
        # Install cleanup hooks early with profile information
        _CLEANUP_CTX['user_data_dir'] = user_data_dir
        _install_cleanup_handlers()

        driver = setup_driver(headless=headless, user_data_dir=user_data_dir)
        # Make driver available to cleanup hooks
        _CLEANUP_CTX['driver'] = driver
        print("✅ 浏览器已启动")
        print(f"🔐 使用持久会话目录: {user_data_dir}")

        # 登录（如需要）
        ensure_login(driver, base_url)

        # 跑模式
        if mode == 'direct':
            run_direct_mode(driver, direct_url, enable_like, headless)
        else:
            run_random_mode(driver, base_url, cycles, enable_like, headless)

    except KeyboardInterrupt:
        print("\n⏹️ 用户已中断")
    except Exception as e:
        print(f"❌ 运行失败: {e}")
        print("👉 可尝试运行: python fix_startup_issue.py")
    finally:
        try:
            if driver:
                driver.quit()
        except Exception:
            pass
        # Ensure no stray Chrome remains for this profile (especially on macOS)
        try:
            _kill_chrome_for_profile(_CLEANUP_CTX.get('user_data_dir'))
        except Exception:
            pass
        print("\n程序结束")


if __name__ == '__main__':
    main()
