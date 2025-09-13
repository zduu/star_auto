# Discourse 自动化（极简版）

该项目提供一个极简的单文件自动化脚本 `start.py`，可用于在基于 Discourse 的网站上随机浏览帖子或直接打开某个帖子进行“阅读 + 点赞”。另附 `fix_startup_issue.py` 用于故障排查。

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```bash
python start.py
```

首次运行：如果检测到未登录，脚本会提示你在弹出的浏览器中手动登录。登录一次后会保持浏览器会话（由系统管理的默认用户数据），之后可直接运行。

## 配置网站

支持两种方式：

- 交互式配置（推荐）
  ```bash
  python start.py --configure
  ```
  - 按提示输入网站主页（如 `https://shuiyuan.sjtu.edu.cn`）、默认循环次数、默认无头模式、默认点赞等。
  - 保存到 `settings.json`（已加入 `.gitignore`）。

- 命令行参数（一次性覆盖）
  - 基本参数：
    - `--base-url`：网站主页 URL（随机浏览模式使用）
    - `--mode {random,direct}`：运行模式（随机/直接链接）
    - `--url`：直接链接模式需要传入的帖子链接
    - `--cycles`：随机浏览模式循环次数
    - `--headless` / `--no-headless`：是否无头
    - `--like` / `--no-like`：是否点赞

  - 示例：
    ```bash
    # 随机浏览 3 次（无头 + 点赞），指定站点
    python start.py --base-url https://shuiyuan.sjtu.edu.cn --mode random --cycles 3 --headless --like

    # 直接链接浏览（有头 + 不点赞）
    python start.py --mode direct --url "https://shuiyuan.sjtu.edu.cn/t/topic/12345" --no-like
    ```

注意：未通过命令行传入的参数，脚本会基于 `settings.json` 或默认值进行交互式补充。

## 故障排查

如果浏览器启动失败或脚本卡住，可运行：

```bash
python fix_startup_issue.py
```

该脚本会清理缓存、尝试终止残留进程，并测试 Chrome/Chromedriver 的启动能力。

## 依赖

- `selenium`：Web 自动化
- `undetected-chromedriver`：对抗 Cloudflare 等检测
- `webdriver-manager`：自动管理 Chromedriver
- `psutil`（可选）：用于问题排查脚本更精准地结束进程

## 目录结构

- `start.py`：主脚本，单文件实现
- `fix_startup_issue.py`：故障排查脚本
- `settings.json`：本地配置（自动创建，已忽略）

## 许可

仅作为个人自动化与学习用途，请遵守目标网站的使用条款，合理使用。

