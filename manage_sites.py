#!/usr/bin/env python3
"""
网站配置管理脚本
用于添加、修改、删除Discourse网站配置
"""

import json
import os

def load_config():
    """加载配置文件"""
    if os.path.exists("sites_config.json"):
        with open("sites_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {
            "sites": {},
            "default_site": "",
            "settings": {
                "default_cycles": 5,
                "default_headless": False,
                "default_like": True,
                "scroll_delay_min": 1,
                "scroll_delay_max": 3,
                "cycle_delay_min": 5,
                "cycle_delay_max": 10
            }
        }

def save_config(config):
    """保存配置文件"""
    with open("sites_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def list_sites(config):
    """列出所有网站"""
    sites = config.get("sites", {})
    if not sites:
        print("📋 当前没有配置任何网站")
        return
    
    print("📋 已配置的网站:")
    for key, site in sites.items():
        default_mark = " (默认)" if key == config.get("default_site") else ""
        print(f"   - {key}: {site['name']} - {site['base_url']}{default_mark}")

def add_site(config):
    """添加新网站"""
    print("\n➕ 添加新网站")
    print("-" * 30)
    
    # 获取网站信息
    site_key = input("网站标识符 (如: mysite): ").strip()
    if not site_key:
        print("❌ 网站标识符不能为空")
        return
    
    if site_key in config["sites"]:
        print("❌ 该标识符已存在")
        return
    
    name = input("网站名称: ").strip()
    if not name:
        print("❌ 网站名称不能为空")
        return
    
    base_url = input("网站URL (如: https://example.com): ").strip()
    if not base_url:
        print("❌ 网站URL不能为空")
        return
    
    login_url = input("登录URL (可选，按回车跳过): ").strip()
    
    # 使用默认选择器
    like_selectors = [
        ".like-button",
        ".post-controls .like",
        ".actions .like",
        "button[title*='like']"
    ]
    
    topic_selectors = [
        "a.title",
        ".topic-list-item a.title",
        ".topic-list tbody tr .main-link a"
    ]
    
    user_data_dir = f"chrome_user_data_{site_key}"
    
    # 添加到配置
    config["sites"][site_key] = {
        "name": name,
        "base_url": base_url,
        "login_url": login_url,
        "like_selectors": like_selectors,
        "topic_selectors": topic_selectors,
        "user_data_dir": user_data_dir
    }
    
    # 如果是第一个网站，设为默认
    if not config.get("default_site"):
        config["default_site"] = site_key
    
    save_config(config)
    print(f"✅ 网站 '{name}' 添加成功")

def remove_site(config):
    """删除网站"""
    sites = config.get("sites", {})
    if not sites:
        print("❌ 没有可删除的网站")
        return
    
    print("\n🗑️  删除网站")
    print("-" * 30)
    list_sites(config)
    
    site_key = input("\n请输入要删除的网站标识符: ").strip()
    if site_key not in sites:
        print("❌ 网站不存在")
        return
    
    site_name = sites[site_key]["name"]
    confirm = input(f"确认删除网站 '{site_name}'？(y/n): ").strip().lower()
    if confirm in ['y', 'yes']:
        del config["sites"][site_key]
        
        # 如果删除的是默认网站，重新设置默认
        if config.get("default_site") == site_key:
            remaining_sites = list(config["sites"].keys())
            config["default_site"] = remaining_sites[0] if remaining_sites else ""
        
        save_config(config)
        print(f"✅ 网站 '{site_name}' 删除成功")
    else:
        print("❌ 删除操作已取消")

def set_default_site(config):
    """设置默认网站"""
    sites = config.get("sites", {})
    if not sites:
        print("❌ 没有可设置的网站")
        return
    
    print("\n🎯 设置默认网站")
    print("-" * 30)
    list_sites(config)
    
    site_key = input("\n请输入要设为默认的网站标识符: ").strip()
    if site_key not in sites:
        print("❌ 网站不存在")
        return
    
    config["default_site"] = site_key
    save_config(config)
    print(f"✅ 已将 '{sites[site_key]['name']}' 设为默认网站")

def edit_settings(config):
    """编辑全局设置"""
    print("\n⚙️  编辑全局设置")
    print("-" * 30)
    
    settings = config.get("settings", {})
    
    print(f"当前设置:")
    print(f"  - 默认循环次数: {settings.get('default_cycles', 5)}")
    print(f"  - 默认无头模式: {settings.get('default_headless', False)}")
    print(f"  - 默认点赞功能: {settings.get('default_like', True)}")
    print(f"  - 滚动延迟: {settings.get('scroll_delay_min', 1)}-{settings.get('scroll_delay_max', 3)}秒")
    print(f"  - 循环间隔: {settings.get('cycle_delay_min', 5)}-{settings.get('cycle_delay_max', 10)}秒")
    print()

    # 更新设置
    try:
        cycles = input(f"默认循环次数 (当前: {settings.get('default_cycles', 5)}): ").strip()
        if cycles:
            settings["default_cycles"] = int(cycles)

        headless = input(f"默认无头模式 (y/n, 当前: {'y' if settings.get('default_headless', False) else 'n'}): ").strip().lower()
        if headless:
            settings["default_headless"] = headless in ['y', 'yes']

        like_enabled = input(f"默认点赞功能 (y/n, 当前: {'y' if settings.get('default_like', True) else 'n'}): ").strip().lower()
        if like_enabled:
            settings["default_like"] = like_enabled in ['y', 'yes']

        config["settings"] = settings
        save_config(config)
        print("✅ 设置保存成功")

    except ValueError:
        print("❌ 输入格式错误")

def main():
    print("=" * 50)
    print("🔧 Discourse网站配置管理器")
    print("=" * 50)
    
    config = load_config()
    
    while True:
        print("\n📋 操作菜单:")
        print("  1. 查看所有网站")
        print("  2. 添加新网站")
        print("  3. 删除网站")
        print("  4. 设置默认网站")
        print("  5. 编辑全局设置")
        print("  0. 退出")
        
        choice = input("\n请选择操作 (0-5): ").strip()
        
        if choice == "1":
            list_sites(config)
        elif choice == "2":
            add_site(config)
        elif choice == "3":
            remove_site(config)
        elif choice == "4":
            set_default_site(config)
        elif choice == "5":
            edit_settings(config)
        elif choice == "0":
            print("👋 再见！")
            break
        else:
            print("❌ 无效选择，请重试")

if __name__ == "__main__":
    main()
