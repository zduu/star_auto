#!/usr/bin/env python3
"""
Discourse网站自动化脚本启动器
支持多网站配置和有头/无头模式切换
"""

import sys
import subprocess
import json
import os

def check_dependencies():
    """检查依赖是否已安装"""
    try:
        import selenium  # noqa: F401
        from webdriver_manager.chrome import ChromeDriverManager  # noqa: F401
        return True
    except ImportError:
        return False

def load_sites_config():
    """加载网站配置"""
    try:
        if os.path.exists("sites_config.json"):
            with open("sites_config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            print("⚠️  未找到sites_config.json配置文件，使用默认配置")
            return None
    except Exception as e:
        print(f"⚠️  加载配置文件失败: {e}")
        return None

def install_dependencies():
    """安装依赖包"""
    print("正在安装依赖包...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("依赖包安装成功！")
        return True
    except subprocess.CalledProcessError:
        print("依赖包安装失败，请手动运行: pip install -r requirements.txt")
        return False

def select_site(config):
    """选择要访问的网站"""
    if not config or "sites" not in config:
        return None

    sites = config["sites"]
    site_keys = list(sites.keys())

    print("📋 可用的网站:")
    for i, key in enumerate(site_keys, 1):
        site = sites[key]
        print(f"   {i}. {site['name']} ({site['base_url']})")

    print()
    default_site = config.get("default_site", site_keys[0])
    default_index = site_keys.index(default_site) + 1 if default_site in site_keys else 1

    try:
        choice = input(f"请选择网站 (1-{len(site_keys)}, 默认{default_index}): ").strip()
        if not choice:
            selected_key = default_site
        else:
            index = int(choice) - 1
            if 0 <= index < len(site_keys):
                selected_key = site_keys[index]
            else:
                print("选择无效，使用默认网站")
                selected_key = default_site

        return sites[selected_key]
    except ValueError:
        print("输入无效，使用默认网站")
        return sites[default_site]

def main():
    print("=" * 60)
    print("🌐 Discourse网站自动化脚本")
    print("=" * 60)
    print()

    # 检查依赖
    if not check_dependencies():
        print("⚠️  检测到缺少依赖包")
        install = input("是否自动安装依赖包？(y/n): ").strip().lower()
        if install in ['y', 'yes', '']:
            if not install_dependencies():
                return
        else:
            print("请手动安装依赖包: pip install -r requirements.txt")
            return

    print("✅ 依赖检查完成")
    print()

    # 加载网站配置
    config = load_sites_config()

    # 选择网站
    if config:
        selected_site = select_site(config)
        if not selected_site:
            print("❌ 网站选择失败")
            return
    else:
        selected_site = None

    print()

    # 获取用户输入
    default_cycles = config.get("settings", {}).get("default_cycles", 5) if config else 5
    try:
        cycles = input(f"请输入要执行的循环次数 (默认{default_cycles}次): ").strip()
        cycles = int(cycles) if cycles else default_cycles

        if cycles <= 0:
            print("循环次数必须大于0")
            return

    except ValueError:
        print(f"输入无效，使用默认值{default_cycles}次")
        cycles = default_cycles

    # 选择浏览器模式
    default_headless = config.get("settings", {}).get("default_headless", False) if config else False
    headless_input = input(f"是否使用无头模式？(y/n，默认{'y' if default_headless else 'n'}): ").strip().lower()
    if headless_input == '':
        headless = default_headless
    else:
        headless = headless_input in ['y', 'yes']

    # 选择是否启用点赞
    default_like = config.get("settings", {}).get("default_like", True) if config else True
    like_input = input(f"是否启用点赞功能？(y/n，默认{'y' if default_like else 'n'}): ").strip().lower()
    if like_input == '':
        enable_like = default_like
    else:
        enable_like = like_input in ['y', 'yes']

    print(f"📋 配置信息:")
    print(f"   - 网站: {selected_site['name'] if selected_site else '默认(水源社区)'}")
    print(f"   - URL: {selected_site['base_url'] if selected_site else 'https://shuiyuan.sjtu.edu.cn'}")
    print(f"   - 循环次数: {cycles}")
    print(f"   - 浏览器模式: {'无头模式' if headless else '有头模式'}")
    print(f"   - 点赞功能: {'启用' if enable_like else '禁用'}")
    print(f"   - 登录状态: 自动保存")
    print()

    confirm = input("确认开始运行？(y/n): ").strip().lower()
    if confirm not in ['y', 'yes', '']:
        print("已取消运行")
        return

    print()
    print("🚀 启动自动化脚本...")
    print("💡 提示: 如果是首次运行，请在浏览器中手动完成登录")
    site_name = selected_site['name'].replace(' ', '_').lower() if selected_site else 'discourse'
    print(f"📝 详细日志将保存在 {site_name}_automation.log 文件中")
    print()

    # 导入并运行主脚本
    try:
        from shuiyuan_automation import DiscourseAutomation
        automation = DiscourseAutomation(site_config=selected_site, headless=headless, enable_like=enable_like)
        automation.run_automation(cycles)
    except KeyboardInterrupt:
        print("\n⏹️  用户中断程序")
    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        print("请查看日志文件获取详细信息")

if __name__ == "__main__":
    main()
