#!/usr/bin/env python3
"""
Discourse网站自动化脚本
支持多网站配置、手动登录后保存状态、随机浏览帖子并点赞
支持有头/无头模式切换
"""

import os
import time
import random
import logging
import json
import signal
import sys
import atexit
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc
from platform_utils import get_platform_utils

class DiscourseAutomation:
    def __init__(self, site_config=None, headless=False, enable_like=True):
        self.driver = None
        self.wait = None
        self.headless = headless
        self.enable_like = enable_like  # 点赞开关
        self.clicked_positions = set()  # 记录已点击过的按钮位置
        self._cleanup_registered = False

        # 初始化平台工具
        self.platform_utils = get_platform_utils()

        # 注册清理函数
        self._register_cleanup_handlers()

        # 默认网站配置
        self.default_sites = {
            "shuiyuan": {
                "name": "上海交大水源社区",
                "base_url": "https://shuiyuan.sjtu.edu.cn",
                "login_url": "https://jaccount.sjtu.edu.cn",
                "like_selectors": [
                    ".like-button",
                    ".post-controls .like",
                    ".actions .like",
                    "button[title*='like']",
                    "button[title*='赞']",
                    ".widget-button.like",
                    ".post-action-like"
                ],
                "topic_selectors": [
                    "a.title",
                    ".topic-list-item a.title",
                    ".topic-list tbody tr .main-link a",
                    ".topic-list .topic-list-data a",
                    "tr.topic-list-item .main-link a"
                ],
                "user_data_dir": "chrome_user_data_shuiyuan"
            }
        }

        # 设置当前网站配置
        if site_config:
            self.site_config = site_config
        else:
            self.site_config = self.default_sites["shuiyuan"]

        self.base_url = self.site_config["base_url"]
        self.login_url = self.site_config.get("login_url", "")

        # 设置日志（使用平台工具）
        site_name = self.site_config.get("name", "discourse")
        log_filename = self.platform_utils.get_log_filename(site_name)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _register_cleanup_handlers(self):
        """注册清理处理函数"""
        if not self._cleanup_registered:
            # 注册程序退出时的清理函数
            atexit.register(self._emergency_cleanup)

            # 注册信号处理函数
            try:
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
                if hasattr(signal, 'SIGBREAK'):  # Windows
                    signal.signal(signal.SIGBREAK, self._signal_handler)
            except Exception as e:
                self.logger.debug(f"注册信号处理器失败: {e}")

            self._cleanup_registered = True

    def _signal_handler(self, signum, frame):
        """信号处理函数"""
        self.logger.info(f"接收到信号 {signum}，正在清理资源...")
        try:
            self.cleanup()
        except Exception as e:
            self.logger.error(f"信号处理清理失败: {e}")
        finally:
            # 确保程序退出
            import os
            os._exit(0)

    def _emergency_cleanup(self):
        """紧急清理函数"""
        try:
            if self.driver:
                self.driver.quit()
        except:
            pass

    def find_fixed_chromedriver(self):
        """查找修复脚本安装的ChromeDriver"""
        try:
            wdm_cache_dir = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "chromedriver", "win64")
            if not os.path.exists(wdm_cache_dir):
                return None

            # 查找最新版本的ChromeDriver
            versions = []
            for version_dir in os.listdir(wdm_cache_dir):
                version_path = os.path.join(wdm_cache_dir, version_dir)
                if os.path.isdir(version_path):
                    # 查找chromedriver.exe
                    for root, dirs, files in os.walk(version_path):
                        for file in files:
                            if file == 'chromedriver.exe':
                                exe_path = os.path.join(root, file)
                                if os.path.exists(exe_path):
                                    versions.append((version_dir, exe_path))
                                    break

            if versions:
                # 按版本号排序，使用最新的
                versions.sort(key=lambda x: x[0], reverse=True)
                return versions[0][1]

        except Exception as e:
            self.logger.debug(f"查找修复的ChromeDriver失败: {e}")

        return None

    def setup_driver(self):
        """设置Chrome浏览器驱动，使用undetected_chromedriver绕过Cloudflare验证"""
        # 使用平台工具获取用户数据目录
        site_name = self.site_config.get("name", "discourse")
        user_data_dir = self.platform_utils.get_user_data_dir(site_name)

        self.logger.info(f"用户数据目录: {user_data_dir}")
        self.logger.info("使用undetected_chromedriver绕过Cloudflare验证")

        # 准备undetected_chromedriver的选项
        uc_options = uc.ChromeOptions()

        # 基础选项
        uc_options.add_argument("--no-sandbox")
        uc_options.add_argument("--disable-dev-shm-usage")

        # 设置用户数据目录
        uc_options.add_argument(f"--user-data-dir={user_data_dir}")
        self.logger.info(f"用户数据目录: {user_data_dir}")

        # 有头/无头模式设置
        if self.headless:
            # 无头模式的特殊配置，专门对抗Cloudflare
            uc_options.add_argument("--headless=new")  # 使用新的无头模式
            uc_options.add_argument("--disable-gpu")
            uc_options.add_argument("--window-size=1920,1080")
            uc_options.add_argument("--disable-web-security")
            uc_options.add_argument("--allow-running-insecure-content")
            uc_options.add_argument("--disable-features=VizDisplayCompositor")
            # 模拟真实浏览器的用户代理
            uc_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            # 添加更多反检测选项
            uc_options.add_argument("--disable-blink-features=AutomationControlled")
            uc_options.add_argument("--disable-dev-shm-usage")
            uc_options.add_argument("--no-first-run")
            uc_options.add_argument("--no-default-browser-check")
            uc_options.add_argument("--disable-default-apps")
            self.logger.info("启动无头模式（Cloudflare优化）")
        else:
            self.logger.info("启动有头模式")

        # 最小化的Chrome选项，避免与undetected_chromedriver冲突
        uc_options.add_argument("--disable-blink-features=AutomationControlled")
        uc_options.add_argument("--disable-extensions")
        uc_options.add_argument("--disable-plugins")

        # 注意：undetected_chromedriver会自动处理反检测选项，不需要手动设置
        # 避免添加可能导致冲突的平台特定选项

        # 禁用图片加载以提高速度（可选）
        # uc_options.add_argument("--disable-images")

        try:
            # 检查是否有自定义Chrome路径
            chrome_path = self.platform_utils.get_chrome_executable_path()
            if chrome_path:
                uc_options.binary_location = chrome_path
                self.logger.info(f"使用Chrome路径: {chrome_path}")

            # 使用undetected_chromedriver创建浏览器实例
            try:
                self.logger.info("正在启动undetected_chromedriver...")

                # 简化的启动配置
                self.driver = uc.Chrome(
                    options=uc_options,
                    version_main=None,  # 自动检测Chrome版本
                    driver_executable_path=None,  # 自动下载ChromeDriver
                    browser_executable_path=chrome_path if chrome_path else None,
                    use_subprocess=False,  # 避免子进程问题
                    log_level=3  # 减少日志输出
                )

                self.logger.info("使用undetected_chromedriver成功创建浏览器实例")

            except Exception as driver_error:
                self.logger.warning(f"undetected_chromedriver启动失败: {driver_error}")
                self.logger.info("尝试使用传统方式启动...")

                # 回退到传统的webdriver方式
                fixed_driver_path = self.find_fixed_chromedriver()
                if fixed_driver_path:
                    self.logger.info(f"使用修复的ChromeDriver: {fixed_driver_path}")
                    service = Service(fixed_driver_path)
                    # 转换uc_options为普通的Options
                    chrome_options = Options()
                    for arg in uc_options.arguments:
                        chrome_options.add_argument(arg)
                    for key, value in uc_options.experimental_options.items():
                        chrome_options.add_experimental_option(key, value)
                    if hasattr(uc_options, 'binary_location') and uc_options.binary_location:
                        chrome_options.binary_location = uc_options.binary_location
                    self.driver = webdriver.Chrome(service=service, options=chrome_options)
                else:
                    raise driver_error

            self.wait = WebDriverWait(self.driver, 10)
            mode_text = "无头模式" if self.headless else "有头模式"
            system_info = self.platform_utils.get_system_info()
            self.logger.info(f"Chrome浏览器启动成功 ({mode_text}) - {system_info['system'].title()}")

        except Exception as e:
            self.logger.error(f"启动浏览器失败: {e}")
            self.logger.error("请确保已安装Chrome浏览器和undetected-chromedriver包")
            raise
    
    def check_login_status(self):
        """检查是否已经登录"""
        try:
            self.driver.get(self.base_url)
            time.sleep(3)
            
            # 检查是否存在登录按钮或用户头像
            try:
                # 查找登录相关元素
                login_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    "a[href*='login'], .login-button, .header-buttons .login-button")
                
                if login_elements:
                    self.logger.info("未检测到登录状态")
                    return False
                
                # 查找用户相关元素
                user_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                    ".current-user, .user-menu, .header-dropdown-toggle, .user-activity-link")
                
                if user_elements:
                    self.logger.info("检测到已登录状态")
                    return True
                    
            except NoSuchElementException:
                pass
            
            # 检查当前URL是否被重定向到登录页面
            current_url = self.driver.current_url
            if "jaccount.sjtu.edu.cn" in current_url:
                self.logger.info("页面重定向到登录页面，需要登录")
                return False
                
            self.logger.info("登录状态检查完成")
            return True
            
        except Exception as e:
            self.logger.error(f"检查登录状态时出错: {e}")
            return False
    
    def manual_login(self):
        """等待用户手动登录"""
        self.logger.info("请在浏览器中手动完成登录...")
        self.logger.info("登录完成后，程序将自动继续执行")
        
        # 等待用户手动登录，检查是否返回到主页
        max_wait_time = 300  # 最多等待5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            try:
                current_url = self.driver.current_url
                
                # 如果回到了主页且不在登录页面
                if (self.base_url in current_url and 
                    "jaccount.sjtu.edu.cn" not in current_url):
                    
                    # 再次检查登录状态
                    time.sleep(2)
                    if self.check_login_status():
                        self.logger.info("登录成功！")
                        return True
                
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"等待登录时出错: {e}")
                time.sleep(2)
        
        self.logger.error("登录超时，请重试")
        return False
    
    def get_random_topic(self):
        """从主页随机选择一个帖子"""
        try:
            self.driver.get(self.base_url)

            # 无头模式需要更长的等待时间和Cloudflare处理
            wait_time = 15 if self.headless else 3
            self.logger.info(f"等待页面加载 {wait_time} 秒...")
            time.sleep(wait_time)

            # 等待页面完全加载
            try:
                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

                # 无头模式下的Cloudflare处理
                if self.headless:
                    # 检查是否遇到Cloudflare
                    page_title = self.driver.title
                    page_source = self.driver.page_source.lower()

                    if ("请稍候" in page_title or "just a moment" in page_source or
                        "checking your browser" in page_source or "cloudflare" in page_source):

                        self.logger.warning("检测到Cloudflare验证页面，尝试等待通过...")

                        # 等待Cloudflare验证完成
                        for attempt in range(6):  # 最多等待30秒
                            time.sleep(5)
                            new_title = self.driver.title
                            new_source = self.driver.page_source.lower()

                            if ("请稍候" not in new_title and "just a moment" not in new_source and
                                "checking your browser" not in new_source):
                                self.logger.info(f"Cloudflare验证通过，耗时 {(attempt + 1) * 5} 秒")
                                break

                            self.logger.info(f"等待Cloudflare验证... ({attempt + 1}/6)")
                        else:
                            self.logger.warning("Cloudflare验证超时，继续尝试...")

                    # 等待JavaScript执行完成
                    self.logger.info("等待JavaScript执行完成...")
                    time.sleep(5)

                    # 检查页面是否真正加载完成
                    for i in range(3):
                        ready_state = self.driver.execute_script("return document.readyState")
                        if ready_state == "complete":
                            break
                        self.logger.info(f"页面状态: {ready_state}, 继续等待...")
                        time.sleep(2)

                    # 滚动页面触发懒加载
                    self.driver.execute_script("window.scrollTo(0, 500);")
                    time.sleep(2)
                    self.driver.execute_script("window.scrollTo(0, 0);")
                    time.sleep(2)

            except Exception as e:
                self.logger.warning(f"页面加载检查失败: {e}，继续尝试...")

            # 使用配置的帖子选择器
            topic_selectors = self.site_config.get("topic_selectors", [
                "a.title",
                ".topic-list-item a.title",
                ".topic-list tbody tr .main-link a"
            ])

            topics = []
            # 尝试多次查找，给动态内容更多时间加载
            for attempt in range(3):
                for selector in topic_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            topics.extend(elements)
                            self.logger.info(f"使用选择器 '{selector}' 找到 {len(elements)} 个帖子")
                            break
                    except Exception as e:
                        self.logger.debug(f"选择器 '{selector}' 查找失败: {e}")
                        continue

                if topics:
                    break

                # 如果没找到，等待一下再试
                if attempt < 2:
                    self.logger.info(f"第 {attempt + 1} 次尝试未找到帖子，等待2秒后重试...")
                    time.sleep(2)

            if not topics:
                self.logger.warning("未找到帖子链接")
                # 输出详细调试信息
                if self.headless:
                    try:
                        # 获取页面基本信息
                        current_url = self.driver.current_url
                        page_title = self.driver.title
                        page_source = self.driver.page_source

                        self.logger.info(f"当前URL: {current_url}")
                        self.logger.info(f"页面标题: {page_title}")
                        self.logger.info(f"页面源码长度: {len(page_source)} 字符")

                        # 检查是否有Cloudflare或其他拦截
                        if "cloudflare" in page_source.lower():
                            self.logger.warning("检测到Cloudflare页面")
                        if "just a moment" in page_source.lower():
                            self.logger.warning("检测到'Just a moment'页面")
                        if "checking your browser" in page_source.lower():
                            self.logger.warning("检测到浏览器检查页面")

                        # 输出页面源码片段
                        page_snippet = page_source[:2000]
                        self.logger.debug(f"页面源码片段: {page_snippet}")

                        # 检查是否有任何链接
                        all_links = self.driver.find_elements(By.TAG_NAME, "a")
                        self.logger.info(f"页面中总共有 {len(all_links)} 个链接")

                        # 显示前几个链接的信息
                        for i, link in enumerate(all_links[:5]):
                            try:
                                href = link.get_attribute('href') or ''
                                text = link.text.strip()[:50]
                                class_name = link.get_attribute('class') or ''
                                self.logger.debug(f"链接 {i+1}: href='{href[:50]}', text='{text}', class='{class_name}'")
                            except:
                                continue

                    except Exception as debug_error:
                        self.logger.error(f"调试信息获取失败: {debug_error}")

                return None

            # 过滤掉无效的帖子链接
            valid_topics = []
            for topic in topics:
                try:
                    title = topic.text.strip()
                    href = topic.get_attribute('href')
                    if title and href and self.base_url in href:
                        valid_topics.append(topic)
                except:
                    continue

            if not valid_topics:
                self.logger.warning("未找到有效的帖子链接")
                return None

            # 随机选择一个帖子
            selected_topic = random.choice(valid_topics)
            topic_title = selected_topic.text.strip()

            self.logger.info(f"选择帖子: {topic_title}")
            return selected_topic

        except Exception as e:
            self.logger.error(f"获取随机帖子时出错: {e}")
            return None
    
    def like_visible_posts(self):
        """对当前可见区域的所有帖子进行点赞 - 改进版本"""
        if not self.enable_like:
            return 0

        try:
            liked_count = 0
            skipped_count = 0

            # 使用配置的点赞选择器
            like_selectors = self.site_config.get("like_selectors", [
                ".like-button",
                ".post-controls .like",
                ".actions .like",
                "button[title*='like']",
                "button[title*='赞']"
            ])

            self.logger.debug(f"使用点赞选择器: {like_selectors}")

            # 收集所有可能的点赞按钮
            all_like_buttons = []
            for selector in like_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if buttons:
                        self.logger.debug(f"选择器 '{selector}' 找到 {len(buttons)} 个按钮")
                        all_like_buttons.extend(buttons)
                except Exception as e:
                    self.logger.debug(f"选择器 '{selector}' 查找失败: {e}")
                    continue

            if not all_like_buttons:
                self.logger.debug("未找到任何点赞按钮")
                # 输出页面中的一些按钮信息用于调试
                try:
                    all_buttons = self.driver.find_elements(By.TAG_NAME, "button")
                    self.logger.debug(f"页面中共有 {len(all_buttons)} 个按钮")
                    for i, btn in enumerate(all_buttons[:5]):  # 只显示前5个
                        try:
                            btn_class = btn.get_attribute("class") or ""
                            btn_title = btn.get_attribute("title") or ""
                            btn_text = btn.text.strip()[:20]  # 只显示前20个字符
                            self.logger.debug(f"按钮 {i+1}: class='{btn_class}', title='{btn_title}', text='{btn_text}'")
                        except:
                            continue
                except:
                    pass
                return 0

            # 过滤出当前可见且可点击的按钮
            visible_buttons = []
            for btn in all_like_buttons:
                try:
                    if (btn.is_displayed() and btn.is_enabled() and
                        self.is_element_in_viewport(btn)):

                        # 基于位置生成唯一标识，避免重复点击
                        btn_rect = btn.rect
                        position_key = f"{int(btn_rect['x'])}_{int(btn_rect['y'])}"

                        if position_key not in self.clicked_positions:
                            visible_buttons.append((btn, position_key))
                        else:
                            skipped_count += 1

                except Exception:
                    continue

            self.logger.info(f"发现 {len(visible_buttons)} 个新的可见点赞按钮")

            # 对每个按钮进行简单的点赞尝试
            for i, (like_button, position_key) in enumerate(visible_buttons):
                try:
                    # 简单检查：只检查最明显的已点赞标识
                    if self.is_obviously_liked(like_button):
                        skipped_count += 1
                        self.clicked_positions.add(position_key)
                        self.logger.debug(f"跳过明显已点赞的帖子 ({i+1}/{len(visible_buttons)})")
                        continue

                    # 滚动到按钮位置
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", like_button)
                    time.sleep(0.5)

                    # 尝试点击
                    try:
                        like_button.click()
                        liked_count += 1
                        self.clicked_positions.add(position_key)
                        self.logger.info(f"点赞尝试 ({i+1}/{len(visible_buttons)})")
                        time.sleep(random.uniform(1, 1.5))

                    except ElementClickInterceptedException:
                        # JavaScript备用方案
                        self.driver.execute_script("arguments[0].click();", like_button)
                        liked_count += 1
                        self.clicked_positions.add(position_key)
                        self.logger.info(f"JS点赞尝试 ({i+1}/{len(visible_buttons)})")
                        time.sleep(random.uniform(1, 1.5))

                except Exception as e:
                    self.logger.warning(f"点赞第{i+1}个按钮时出错: {e}")
                    continue

            if liked_count > 0 or skipped_count > 0:
                self.logger.info(f"本次点赞尝试 {liked_count} 个，跳过 {skipped_count} 个")

            return liked_count

        except Exception as e:
            self.logger.error(f"批量点赞时出错: {e}")
            return 0

    def is_obviously_liked(self, like_button):
        """简单检查是否明显已点赞 - 只检查最明显的标识"""
        try:
            # 检查class中是否包含liked（最常见的标识）
            button_class = like_button.get_attribute("class") or ""
            if "liked" in button_class.lower():
                return True

            # 检查title中是否包含"取消"或"unlike"
            button_title = like_button.get_attribute("title") or ""
            if ("unlike" in button_title.lower() or
                "取消" in button_title or
                "已赞" in button_title):
                return True

            # 检查aria-pressed属性
            aria_pressed = like_button.get_attribute("aria-pressed")
            if aria_pressed == "true":
                return True

            return False

        except Exception:
            return False  # 如果检查出错，默认为未点赞



    def is_element_in_viewport(self, element):
        """检查元素是否在当前视窗内"""
        try:
            # 获取元素位置和视窗信息
            element_rect = element.rect
            viewport_height = self.driver.execute_script("return window.innerHeight")
            scroll_top = self.driver.execute_script("return window.pageYOffset")

            element_top = element_rect['y']
            element_bottom = element_top + element_rect['height']
            viewport_top = scroll_top
            viewport_bottom = scroll_top + viewport_height

            # 检查元素是否在视窗内（至少部分可见）
            return (element_bottom > viewport_top and element_top < viewport_bottom)
        except Exception:
            return False

    def wait_for_dynamic_loading(self, timeout=10):
        """等待动态内容加载完成"""
        start_time = time.time()
        last_height = self.driver.execute_script("return document.body.scrollHeight")

        while time.time() - start_time < timeout:
            time.sleep(1)
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height != last_height:
                self.logger.debug(f"检测到内容加载: {last_height}px -> {new_height}px")
                last_height = new_height
                start_time = time.time()  # 重置计时器

        return last_height

    def scroll_and_read_replies(self):
        """滚动浏览所有回复，并在滚动过程中进行点赞"""
        try:
            self.logger.info("开始浏览回复...")

            # 滚动到页面顶部
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)

            # 获取页面初始高度和视窗高度
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")

            self.logger.info(f"页面初始高度: {last_height}px, 视窗高度: {viewport_height}px")

            # 先对顶部可见的帖子进行点赞
            if self.enable_like:
                self.like_visible_posts()

            # 改进的滚动逻辑
            scroll_step = max(600, viewport_height // 3)  # 减小滚动步长，确保不会跳过太多内容
            total_liked = 0
            scroll_count = 0
            no_change_count = 0  # 连续无变化的次数
            last_scroll_position = 0
            stable_height_count = 0  # 页面高度稳定的次数

            while True:
                # 获取当前滚动位置和页面高度
                current_scroll_position = self.driver.execute_script("return window.pageYOffset")
                current_height = self.driver.execute_script("return document.body.scrollHeight")

                # 向下滚动
                self.driver.execute_script(f"window.scrollBy(0, {scroll_step});")
                scroll_count += 1

                # 等待页面稳定
                time.sleep(random.uniform(1.5, 2.5))

                # 获取新的滚动位置和页面高度
                new_scroll_position = self.driver.execute_script("return window.pageYOffset")
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                current_bottom = new_scroll_position + viewport_height

                self.logger.debug(f"滚动 {scroll_count}: 位置 {new_scroll_position}px, 页面高度 {new_height}px, 底部位置 {current_bottom}px")

                # 检查是否接近底部，如果是则等待动态加载
                distance_to_bottom = new_height - current_bottom
                if distance_to_bottom < viewport_height * 2:  # 距离底部不到2个屏幕高度
                    self.logger.info(f"接近底部，等待动态加载... (距离底部: {distance_to_bottom}px)")
                    loaded_height = self.wait_for_dynamic_loading(timeout=8)
                    if loaded_height > new_height:
                        new_height = loaded_height
                        self.logger.info(f"动态加载完成，新页面高度: {new_height}px")

                # 每次滚动后对新出现的帖子进行点赞
                if self.enable_like:
                    liked_this_scroll = self.like_visible_posts()
                    total_liked += liked_this_scroll

                    if liked_this_scroll > 0:
                        # 如果有点赞，稍微多等一会儿
                        time.sleep(random.uniform(1, 2))

                # 模拟真实阅读停留
                time.sleep(random.uniform(1, 2))

                # 检查是否真的滚动了
                if new_scroll_position == last_scroll_position:
                    no_change_count += 1
                    self.logger.debug(f"滚动位置无变化，连续次数: {no_change_count}")
                else:
                    no_change_count = 0
                    last_scroll_position = new_scroll_position

                # 检查页面高度是否稳定
                if new_height == last_height:
                    stable_height_count += 1
                else:
                    stable_height_count = 0
                    last_height = new_height
                    self.logger.info(f"页面高度变化: {last_height}px -> {new_height}px")

                # 更严格的底部检测逻辑
                really_at_bottom = (
                    current_bottom >= new_height - 20 and  # 距离底部很近
                    stable_height_count >= 3 and  # 页面高度已经稳定
                    no_change_count >= 2  # 滚动位置也稳定
                )

                if really_at_bottom:
                    self.logger.info(f"确认到达页面底部 (位置: {new_scroll_position}px, 页面高度: {new_height}px)")
                    self.logger.info(f"页面高度稳定次数: {stable_height_count}, 滚动位置稳定次数: {no_change_count}")
                    break

                # 如果连续多次滚动位置都没有变化，但页面高度还在变化，继续等待
                if no_change_count >= 5 and stable_height_count < 2:
                    self.logger.info("滚动位置无变化但页面可能还在加载，继续等待...")
                    time.sleep(3)
                    continue

                # 如果连续多次滚动位置都没有变化且页面高度稳定，可能真的到底了
                if no_change_count >= 5 and stable_height_count >= 3:
                    self.logger.info(f"连续{no_change_count}次滚动位置无变化且页面高度稳定，确认到达底部")
                    break

                # 防止无限滚动，但增加更大的限制
                if scroll_count > 500:  # 大幅增加到500次，适应超长帖子
                    self.logger.warning(f"达到最大滚动次数({scroll_count})，停止滚动")
                    break

            # 最后再次尝试滚动到底部并等待加载
            self.logger.info("执行最终底部检查...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            final_loaded_height = self.wait_for_dynamic_loading(timeout=5)

            # 在底部再次检查是否有遗漏的点赞
            if self.enable_like:
                final_liked = self.like_visible_posts()
                total_liked += final_liked

            # 在底部停留一会儿
            time.sleep(random.uniform(2, 4))

            final_height = self.driver.execute_script("return document.body.scrollHeight")
            final_position = self.driver.execute_script("return window.pageYOffset")

            if self.enable_like:
                self.logger.info(f"浏览完成，总共滚动 {scroll_count} 次，点赞 {total_liked} 个帖子")
            else:
                self.logger.info(f"浏览完成，总共滚动 {scroll_count} 次（点赞功能已关闭）")

            self.logger.info(f"最终页面高度: {final_height}px, 最终滚动位置: {final_position}px")

            return True

        except Exception as e:
            self.logger.error(f"浏览回复时出错: {e}")
            return False

    def browse_topic(self, topic_element):
        """浏览单个帖子"""
        try:
            # 点击进入帖子
            topic_element.click()
            time.sleep(3)

            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # 清理上一个帖子的点击位置记录
            self.clicked_positions.clear()
            self.logger.debug("已清理上一个帖子的点击记录")

            # 滚动浏览所有回复（包含点赞逻辑）
            self.scroll_and_read_replies()

            self.logger.info("帖子浏览完成")
            return True

        except Exception as e:
            self.logger.error(f"浏览帖子时出错: {e}")
            return False

    def browse_direct_link(self, url):
        """直接浏览指定链接的帖子"""
        try:
            self.logger.info(f"开始浏览指定链接: {url}")

            # 直接访问指定链接
            self.driver.get(url)
            time.sleep(3)

            # 等待页面加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            # 清理点击位置记录
            self.clicked_positions.clear()
            self.logger.debug("已清理点击记录")

            # 滚动浏览所有回复（包含点赞逻辑）
            self.scroll_and_read_replies()

            self.logger.info("指定链接浏览完成")
            return True

        except Exception as e:
            self.logger.error(f"浏览指定链接时出错: {e}")
            return False

    def run_direct_link_mode(self, url):
        """运行直接链接模式"""
        try:
            self.setup_driver()

            # 检查登录状态
            if not self.check_login_status():
                if not self.manual_login():
                    self.logger.error("登录失败，程序退出")
                    return

            like_status = "启用" if self.enable_like else "禁用"
            self.logger.info(f"开始直接链接模式浏览，点赞功能：{like_status}")
            self.logger.info(f"目标链接: {url}")

            # 直接浏览指定链接
            if self.browse_direct_link(url):
                self.logger.info("直接链接模式浏览完成")
            else:
                self.logger.warning("直接链接模式浏览出现问题")

        except Exception as e:
            self.logger.error(f"直接链接模式运行出错: {e}")
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("浏览器已关闭")

    def run_automation(self, cycles=5):
        """运行自动化流程"""
        try:
            self.setup_driver()

            # 检查登录状态
            if not self.check_login_status():
                if not self.manual_login():
                    self.logger.error("登录失败，程序退出")
                    return

            like_status = "启用" if self.enable_like else "禁用"
            self.logger.info(f"开始自动化浏览，计划执行 {cycles} 个循环，点赞功能：{like_status}")

            for cycle in range(cycles):
                self.logger.info(f"开始第 {cycle + 1} 个循环")

                try:
                    # 获取随机帖子
                    topic = self.get_random_topic()
                    if not topic:
                        self.logger.warning("未能获取帖子，跳过此循环")
                        continue

                    # 浏览帖子
                    if self.browse_topic(topic):
                        self.logger.info(f"第 {cycle + 1} 个循环完成")
                    else:
                        self.logger.warning(f"第 {cycle + 1} 个循环出现问题")

                    # 循环间隔
                    if cycle < cycles - 1:
                        wait_time = random.uniform(5, 10)
                        self.logger.info(f"等待 {wait_time:.1f} 秒后开始下一个循环")
                        time.sleep(wait_time)

                except Exception as e:
                    self.logger.error(f"第 {cycle + 1} 个循环出错: {e}")
                    continue

            self.logger.info("自动化流程完成")

        except KeyboardInterrupt:
            self.logger.info("用户中断程序")
        except Exception as e:
            self.logger.error(f"程序运行出错: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        if self.driver:
            try:
                self.logger.info("正在关闭浏览器...")

                # 首先尝试正常关闭
                self.driver.quit()
                self.logger.info("浏览器已正常关闭")

            except Exception as e:
                self.logger.warning(f"正常关闭浏览器失败: {e}")

                # 尝试强制关闭
                try:
                    self.logger.info("尝试强制关闭浏览器...")

                    # 关闭所有窗口
                    for handle in self.driver.window_handles:
                        self.driver.switch_to.window(handle)
                        self.driver.close()

                    # 退出驱动
                    self.driver.quit()

                except Exception as force_error:
                    self.logger.warning(f"强制关闭也失败: {force_error}")

                    # 最后尝试终止进程
                    try:
                        if hasattr(self.driver, 'service') and hasattr(self.driver.service, 'process'):
                            if self.driver.service.process:
                                self.driver.service.process.terminate()
                                self.logger.info("已终止浏览器进程")
                    except Exception as proc_error:
                        self.logger.warning(f"终止进程失败: {proc_error}")

                        # 最终手段：使用系统命令杀死Chrome进程
                        try:
                            import subprocess
                            import platform

                            system = platform.system().lower()
                            if system == "windows":
                                subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],
                                             capture_output=True, check=False)
                                self.logger.info("已使用taskkill终止Chrome进程")

                        except Exception as sys_error:
                            self.logger.warning(f"系统命令终止失败: {sys_error}")

            finally:
                self.driver = None
                self.logger.info("浏览器清理完成")

def main():
    """主函数"""
    print("Discourse网站自动化脚本")
    print("=" * 50)

    try:
        cycles = input("请输入要执行的循环次数 (默认5次): ").strip()
        cycles = int(cycles) if cycles else 5
    except ValueError:
        cycles = 5

    # 询问是否使用无头模式
    headless_input = input("是否使用无头模式？(y/n，默认n): ").strip().lower()
    headless = headless_input in ['y', 'yes']

    # 询问是否启用点赞功能
    like_input = input("是否启用点赞功能？(y/n，默认y): ").strip().lower()
    enable_like = like_input != 'n' and like_input != 'no'

    automation = DiscourseAutomation(headless=headless, enable_like=enable_like)
    automation.run_automation(cycles)

if __name__ == "__main__":
    main()
