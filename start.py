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


def setup_driver(headless=False):
    """优先使用 undetected_chromedriver，失败时回退到标准 webdriver"""
    chrome_path = get_chrome_executable_path()
    system = platform.system().lower()

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

        driver = uc.Chrome(
            options=uc_options,
            version_main=None,
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

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"❌ 标准 webdriver 也启动失败: {e}")
        print("👉 请先运行: python fix_startup_issue.py 进行故障排查")
        raise


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
    liked = 0
    selectors = [
        ".like-button",
        ".post-controls .like",
        ".actions .like",
        "button[title*='like']",
        "button[title*='赞']",
        ".widget-button.like",
        ".post-action-like",
    ]
    seen = set()
    for css in selectors:
        try:
            for btn in driver.find_elements(By.CSS_SELECTOR, css):
                try:
                    key = (btn.location.get('x', 0), btn.location.get('y', 0))
                    if key in seen:
                        continue
                    seen.add(key)

                    aria = (btn.get_attribute('aria-pressed') or '').lower()
                    cls = (btn.get_attribute('class') or '').lower()
                    if 'liked' in cls or 'has-like' in cls or aria == 'true':
                        continue
                    btn.click()
                    liked += 1
                    time.sleep(0.2)
                except Exception:
                    continue
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

    # 启动浏览器
    driver = None
    try:
        driver = setup_driver(headless=headless)
        print("✅ 浏览器已启动")

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
        print("\n程序结束")


if __name__ == '__main__':
    main()
