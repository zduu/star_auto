#!/usr/bin/env python3
"""
修复启动卡住问题的脚本
"""

import os
import shutil
import subprocess
import time

def cleanup_undetected_chromedriver():
    """清理undetected_chromedriver缓存"""
    print("🧹 清理undetected_chromedriver缓存...")
    
    try:
        # 清理用户目录下的undetected_chromedriver缓存
        uc_cache_dir = os.path.join(os.path.expanduser("~"), "appdata", "roaming", "undetected_chromedriver")
        if os.path.exists(uc_cache_dir):
            shutil.rmtree(uc_cache_dir)
            print(f"✅ 已清理: {uc_cache_dir}")
        
        # 清理临时目录
        temp_dirs = [
            os.path.join(os.environ.get('TEMP', ''), 'scoped_dir*'),
            os.path.join(os.environ.get('TEMP', ''), 'chrome_*'),
        ]
        
        import glob
        for pattern in temp_dirs:
            for path in glob.glob(pattern):
                try:
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                        print(f"✅ 已清理临时目录: {path}")
                except:
                    pass
        
        print("✅ undetected_chromedriver缓存清理完成")
        return True
        
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        return False

def kill_chrome_processes():
    """终止Chrome进程"""
    print("🔄 终止Chrome进程...")
    
    try:
        # 终止Chrome进程
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                      capture_output=True, check=False)
        
        # 终止ChromeDriver进程
        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                      capture_output=True, check=False)
        
        print("✅ Chrome进程已终止")
        return True
        
    except Exception as e:
        print(f"❌ 终止进程失败: {e}")
        return False

def test_simple_chrome():
    """测试简单的Chrome启动"""
    print("🧪 测试简单Chrome启动...")
    
    try:
        import undetected_chromedriver as uc
        
        # 最简单的配置
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-extensions")
        
        print("正在创建Chrome实例...")
        driver = uc.Chrome(
            options=options, 
            use_subprocess=False, 
            log_level=3,
            version_main=None
        )
        
        print("✅ Chrome启动成功")
        
        # 简单测试
        driver.get("https://httpbin.org/user-agent")
        print(f"页面标题: {driver.title}")
        
        driver.quit()
        print("✅ 测试完成")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🔧 修复启动卡住问题")
    print("=" * 60)
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
        print("python start.py")
    else:
        print("\n⚠️  仍有问题，尝试以下解决方案:")
        print("1. 重启计算机")
        print("2. 以管理员身份运行")
        print("3. 使用传统webdriver模式")

if __name__ == "__main__":
    main()
