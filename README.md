# TrendsCollector

在海外 VPS 上自动采集全球/区域热点的工具。采集源全部对海外网络可用，不依赖中国大陆服务。

目标机器：Ubuntu 24.04，动态公网 IP。

## 采集哪些数据

| 来源 | 数据内容 | 是否需要注册 |
|---|---|---|
| Google Trends RSS | 各国每日热搜词（US/JP/KR/GB 等 10 个地区） | 不需要 |
| Reddit | r/all、r/worldnews 等热门帖子（含标题、分数、评论数） | 不需要 |
| Hacker News | 首页热门帖子 | 不需要 |
| GitHub | 各语言趋势仓库（按 Star 增速排序） | 不需要（有速率限制） |
| YouTube | 各地区热门视频 | 需要免费 API Key（可选） |

每次采集后自动去重存入 SQLite，可通过邮件或 Telegram 收到摘要推送。

---

## 一、部署前置：获取 QQ 邮箱授权码

如果要用邮件推送，先准备好 QQ 邮箱的 SMTP 授权码。步骤：

> **授权码和 QQ 密码不同**，它是 QQ 邮箱专供第三方客户端登录用的独立密码。

**第 1 步**：浏览器打开 QQ 邮箱并登录

**第 2 步**：点击顶部「设置」→「账号」

**第 3 步**：往下翻到「POP3/IMAP/SMTP 服务」这一行

**第 4 步**：点击「IMAP/SMTP 服务」右边的「开启」

**第 5 步**：按提示用绑定手机发送短信到指定号码

**第 6 步**：发送成功后页面会显示一串**16 位授权码**（格式类似 `abcd1234efgh5678`）

**第 7 步**：复制并保存在一个安全的地方（后面配置时需要，不会再显示第二次）

> 如果忘记了，可以在 QQ 邮箱「设置 → 账号」中重新生成授权码，旧的会失效。

---

## 二、部署到 VPS

### 2.1 把项目传到 VPS

在你的本地电脑上（macOS/Linux），打开终端：

```bash
# 进入项目目录
cd /Users/hero/Documents/Python\ Projects/trends-collector

# 上传到 VPS（把 1.2.3.4 替换成你的 VPS IP）
scp -r . ubuntu@1.2.3.4:~/trends-collector
```

> Windows 用户：用 WinSCP 或直接通过 SSH 执行 `git clone`（见末尾附录）。

### 2.2 SSH 登录 VPS

```bash
ssh ubuntu@1.2.3.4
```

### 2.3 执行一键部署脚本

```bash
cd ~/trends-collector
bash deploy.sh
```

脚本会自动做以下事情（全程约 30 秒）：

1. `apt-get install python3 python3-venv python3-pip curl sqlite3` — 安装系统依赖
2. `mkdir -p /opt/trends-collector` — 创建安装目录
3. `cp -r src/ config.yaml requirements.txt` — 复制项目文件到 `/opt/trends-collector`
4. `python3 -m venv /opt/trends-collector/venv` — 创建 Python 虚拟环境
5. `pip install -r requirements.txt` — 安装 Python 依赖
6. 创建 `trends-collector` 系统用户（无登录权限，仅用于运行服务）
7. 创建并启用 **systemd timer**，每 30 分钟自动执行一次采集

> 脚本会自动 sudo 提权，直接 `bash deploy.sh` 即可，不需要先 `sudo`。

### 2.4 验证部署结果

```bash
# 检查 timer 状态
systemctl status trends-collector.timer

# 应该看到类似输出：
# ● trends-collector.timer - Run TrendsCollector every 30 minutes
#    Loaded: loaded (/etc/systemd/system/trends-collector.timer; enabled; vendor preset: enabled)
#    Active: active (waiting)
```

---

## 三、配置邮件推送（以 QQ 邮箱为例）

部署完成后，配置邮箱信息并填入授权码：

### 3.1 编辑配置文件

```bash
sudo nano /opt/trends-collector/config.yaml
```

找到 `notifications.email` 这一段，改成你的 QQ 邮箱信息：

```yaml
notifications:
  email:
    enabled: true                              # 改为 true 启用
    smtp_host: "smtp.qq.com"                   # QQ 邮箱 SMTP 服务器，不要改
    smtp_port: 465                             # QQ 邮箱用 465 端口 SSL
    smtp_user: "你的QQ号@qq.com"               # 替换成你的完整 QQ 邮箱
    smtp_password: ""                          # 留空，见下面 3.2
    smtp_use_tls: false                        # 465 端口走 SSL，所以 false
    from_addr: "你的QQ号@qq.com"               # 替换成你的 QQ 邮箱
    to_addrs:
      - "你的QQ号@qq.com"                       # 替换成你的 QQ 邮箱（可以发给自己）
```

> **Ctrl+O 保存，Ctrl+X 退出**（nano 编辑器快捷键）。

### 3.2 配置授权码（两种方式二选一）

**方式 A：通过 systemd override 文件（推荐，安全）**

```bash
sudo systemctl edit trends-collector.service
```

这会打开一个空白编辑器，填入：

```ini
[Service]
Environment=EMAIL_SMTP_PASSWORD=你的16位授权码
```

> 把 `你的16位授权码` 替换成第一步获取的 QQ 邮箱授权码。

保存退出后执行：

```bash
sudo systemctl daemon-reload
```

**方式 B：直接写入 config.yaml（不推荐，密码明文）**

```yaml
smtp_password: "abcd1234efgh5678"    # 这里填你的16位授权码
```

> 方式 A 更安全。授权码保存在 `/etc/systemd/system/trends-collector.service.d/override.conf` 中，只有 root 能读。

### 3.3 手动触发一次采集，测试邮件推送

```bash
# 手动执行一次采集
sudo systemctl start trends-collector.service

# 查看实时日志，确认邮件发送成功
journalctl -u trends-collector.service -f --since "1 min ago"
```

正常日志输出结尾应该类似：

```
[2026-07-11 22:50:00] [INFO] trends_collector.main: === Collection started [IP: 1.2.3.4] ===
[2026-07-11 22:50:15] [INFO] trends_collector.collectors: [google_trends] collected 20, new 20
[2026-07-11 22:50:16] [INFO] trends_collector.collectors: [reddit] collected 25, new 25
[2026-07-11 22:50:17] [INFO] trends_collector.collectors: [hackernews] collected 30, new 30
[2026-07-11 22:50:20] [INFO] trends_collector.collectors: [github] collected 10, new 10
[2026-07-11 22:50:20] [INFO] trends_collector.main: === Collection done: 85 items, 85 new ===
[2026-07-11 22:50:22] [INFO] trends_collector.notifier: Email sent to ['你的QQ号@qq.com'] via smtp.qq.com:465
```

**看到 `Email sent` 这行表示邮件推送成功**，去 QQ 邮箱收件箱查看。

### 3.4 邮件发不出去？检查这几项

| 错误日志 | 原因 | 解决 |
|---|---|---|
| `Email auth failed` | 授权码错误 | 重新生成授权码，检查 `EMAIL_SMTP_PASSWORD` |
| `Email server disconnected` | 端口/协议不对 | QQ 邮箱必须端口 465 + `smtp_use_tls: false`（走 SSL，不是 STARTTLS） |
| `Email recipients refused` | 收件人地址不对 | 检查 `to_addrs` 中的邮箱地址 |
| 连接超时 | VPS 连不上 smtp.qq.com | 检查 VPS 是否在中国境外并被屏蔽（海外 VPS 通常没问题） |

---

## 四、采集频率与数据查看

### 4.1 默认采集频率

- 每 **30 分钟** 自动执行一次
- 每次执行时有一个 **120 秒以内的随机偏移**，避免请求节奏过于规律
- 数据保留 **30 天**，超过的自动删除

### 4.2 修改采集频率

```bash
# 编辑 timer 文件
sudo nano /etc/systemd/system/trends-collector.timer
```

修改 `OnCalendar`：

```ini
[Timer]
OnCalendar=*:0/15        # 改成每 15 分钟一次
OnCalendar=*:0,30        # 改成每 30 分钟一次（整点和半点）
OnCalendar=daily          # 改成每天一次
OnCalendar=*-*-* 06:00:00 # 改成每天早上 6 点一次
```

改完后重载：

```bash
sudo systemctl daemon-reload
sudo systemctl restart trends-collector.timer
```

### 4.3 查看采集的数据

```bash
# 查询各来源采集总量
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) AS count FROM trends GROUP BY source ORDER BY count DESC;"

# 查看最近 10 条采集记录
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, title, score, collected_at FROM trends ORDER BY collected_at DESC LIMIT 10;"

# 查看最高分的前 20 条
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, title, score, url FROM trends ORDER BY score DESC LIMIT 20;"
```

### 4.4 生成日报

```bash
cd /opt/trends-collector
sudo ./venv/bin/python -m trends_collector --report
```

输出示例：

```
============================================================
📊 热点采集日报 [2026-07-11 22:48]
============================================================

📈 各来源统计（24h）：
  reddit                    :   50 条
  hackernews                :   30 条
  google_trends             :   20 条
  github                    :   10 条

🔥 热门内容 TOP 20：
  1. [reddit] (score: 52341)
       Some trending post title here...
       https://reddit.com/r/all/comments/xxx
```

---

## 五、日常运维命令

| 操作 | 命令 |
|---|---|
| 手动执行一次采集 | `sudo systemctl start trends-collector.service` |
| 查看最近日志 | `journalctl -u trends-collector.service -f --since "5 min ago"` |
| 查看昨天日志 | `journalctl -u trends-collector.service --since yesterday` |
| 检查 timer 状态 | `systemctl status trends-collector.timer` |
| 查看下轮执行时间 | `systemctl list-timers trends-collector.timer` |
| 暂停采集 | `sudo systemctl stop trends-collector.timer` |
| 恢复采集 | `sudo systemctl start trends-collector.timer` |
| 修改配置后 | `sudo systemctl restart trends-collector.service` |
| 查看数据库路径 | `ls -lh /opt/trends-collector/data/trends.db` |
| 查看磁盘占用 | `du -sh /opt/trends-collector/data/` |

---

## 六、可选：配置 Telegram 推送

如果不用邮件，也可以用 Telegram Bot。

### 6.1 创建 Bot

1. 在 Telegram 中搜索 `@BotFather`，发送 `/newbot`
2. 按提示设置 bot 名称和用户名
3. BotFather 会返回 **bot token**（格式如 `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`）

### 6.2 获取 Chat ID

4. 搜索你刚创建的 bot，发送任意消息
5. 访问 `https://api.telegram.org/bot<你的token>/getUpdates`
6. 浏览器返回的 JSON 中找 `chat.id` 字段的值（一般是数字）

### 6.3 配置

```bash
sudo systemctl edit trends-collector.service
```

在打开的编辑器中添加：

```ini
[Service]
Environment=TELEGRAM_BOT_TOKEN=你的bot_token
Environment=TELEGRAM_CHAT_ID=你的chat_id
```

然后修改配置文件：

```bash
sudo nano /opt/trends-collector/config.yaml
```

```yaml
notifications:
  telegram:
    enabled: true    # false 改为 true
    bot_token: ""    # 留空，token 走环境变量
    chat_id: ""      # 留空，chat_id 走环境变量
```

保存后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl start trends-collector.service
journalctl -u trends-collector.service -f --since "1 min ago"
```

---

## 七、可选：配置 YouTube 采集

YouTube 需要 Google Cloud API Key（免费，有每日配额）。

### 7.1 申请 API Key

1. 打开 [Google Cloud Console](https://console.cloud.google.com/)
2. 新建项目（或选已有项目）
3. 左侧菜单 →「API 和服务」→「库」
4. 搜索并启用 **YouTube Data API v3**
5. 左侧菜单 →「凭据」→「创建凭据」→「API 密钥」
6. 复制生成的 API Key

### 7.2 配置

```bash
sudo systemctl edit trends-collector.service
```

添加：

```ini
[Service]
Environment=YOUTUBE_API_KEY=你的API_KEY
```

修改配置文件：

```bash
sudo nano /opt/trends-collector/config.yaml
```

```yaml
collectors:
  youtube:
    enabled: true
    api_key: ""           # 留空，走环境变量
    regions:
      - US
      - JP
      - GB
```

---

## 八、如何加一个新的数据源

继承 `BaseCollector` 写一个类，放到 `src/trends_collector/collectors/` 里：

```python
from .base import BaseCollector

class MyNewSourceCollector(BaseCollector):
    def __init__(self, config):
        super().__init__(config)
        self.source_name = "my_new_source"

    def collect(self) -> list:
        # 你的采集逻辑，返回 list[dict]
        return [self._item(
            title="Something trending",
            url="https://example.com",
            score=100,
        )]
```

然后在 `main.py` 的 `build_collectors()` 函数中加上对应的初始化逻辑即可。

---

## 附录 A：通过 Git 部署（替代 scp）

```bash
# 在 VPS 上直接 clone
git clone https://github.com/你的用户名/trends-collector.git
cd trends-collector
bash deploy.sh
```

> 如果这是私有仓库，先在 [GitHub Settings → Developer settings → Personal access tokens](https://github.com/settings/tokens) 生成一个 token，clone 时作为密码使用。

## 附录 B：项目文件结构

```
trends-collector/
├── src/trends_collector/          # Python 包 (约 1000 行)
│   ├── main.py                    # 程序入口
│   ├── config.py                  # 配置文件加载器
│   ├── storage.py                 # SQLite 数据存储
│   ├── notifier.py                # 邮件 + Telegram 通知
│   ├── report.py                  # 日报生成
│   └── collectors/                # 各数据源采集器
│       ├── base.py                # 采集器基类
│       ├── google_trends.py       # Google Trends RSS
│       ├── reddit.py              # Reddit
│       ├── hackernews.py          # Hacker News
│       ├── github.py              # GitHub
│       └── youtube.py             # YouTube (可选)
├── config.yaml                    # 配置文件
├── requirements.txt               # Python 依赖
├── deploy.sh                      # 一键部署脚本
├── Makefile                       # 本地开发命令
├── README.md                      # 本文件
└── scripts/                       # 原始参考脚本（保留不动）
```

## 九、进阶：采集中国大陆热点（微博/百度/知乎）

> 如果你的目标是**同时采集国内和海外热点**，需要增加一台能访问国内网络的机器作为中继。单靠海外 VPS 无法采集国内平台。

### 整体架构

```
┌──────────────────────┐        HTTP POST          ┌──────────────────────┐
│  国内机器（轻量）        │  ──── /collect ──────→  │  海外 VPS（主节点）    │
│  - 微博热搜              │                          │  - SQLite 存储        │
│  - 百度热搜              │  推送结果                 │  - 邮件/Telegram通知  │
│  - 知乎热搜              │  ←──────────────────    │  - 日报生成           │
│  每30分钟 crontab 执行    │                          │  - 全球热点采集       │
└──────────────────────┘                          └──────────────────────┘
```

国内机器不需要固定 IP，不需要高配置，甚至不需要 24 小时在线。你可以用：
- 国内轻量云服务器（如腾讯云轻量 24 元/月）
- 家里的 NAS 或树莓派
- 办公电脑挂 crontab

### 第 1 步：在海外 VPS 上启动接收服务

```bash
# 1) 配置共享密钥
sudo nano /opt/trends-collector/config.yaml
```

在文件末尾添加：

```yaml
relay:
  push_key: "your-random-secret-here"   # 改成一段随机字符串，不要和任何人共享
```

```bash
# 2) 安装 receiver systemd 服务
sudo cp ~/trends-collector/trends-collector-receiver.service /etc/systemd/system/
sudo systemctl edit trends-collector-receiver.service
```

在打开的编辑器中添加：

```ini
[Service]
Environment=RELAY_PUSH_KEY=your-random-secret-here    # 和上面的 push_key 一致
```

```bash
# 3) 启动接收服务（监听 8765 端口）
sudo systemctl daemon-reload
sudo systemctl enable trends-collector-receiver.service
sudo systemctl start trends-collector-receiver.service

# 4) 验证
systemctl status trends-collector-receiver.service
# 应该看到 listening on 0.0.0.0:8765
```

### 第 2 步：配置防火墙开放端口（如果 VPS 有防火墙）

```bash
sudo ufw allow 8765/tcp
```

> 如果用了云服务商的安全组（如 AWS Security Group、阿里云安全组），也需要在控制台放行 8765 端口。

### 第 3 步：在国内机器上部署采集脚本

把 `scripts/china_relay_collector.py` 传到国内机器上，编辑开头的配置：

```python
PUSH_URL = "http://你的海外VPS公网IP:8765/collect"
PUSH_KEY = "your-random-secret-here"   # 和海外 VPS 上配置的密钥一致
```

在国内机器上测试运行：

```bash
pip install requests lxml
python3 china_relay_collector.py
```

如果正常，会输出：

```
[Weibo] collected 20 items
[Baidu] collected 30 items
[Zhihu] collected 20 items
Collected 60 items from China sources
Push result: 200 {"received": 60, "saved": 55}
```

### 第 4 步：设置定时任务

在国内机器上：

```bash
crontab -e
```

添加一行（每 30 分钟执行一次）：

```cron
*/30 * * * * cd /path/to/script && python3 china_relay_collector.py >> /tmp/relay.log 2>&1
```

### 查看汇总数据

采集完成后，在海外 VPS 上查询会发现数据来源中多出了 `weibo`、`baidu`、`zhihu`：

```bash
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) FROM trends GROUP BY source ORDER BY COUNT(*) DESC;"
```

邮件推送也会一并汇总国内和海外的数据，无需额外配置。

### 安全注意事项

- 国内→海外推送使用 HTTP，如果担心流量被中间人篡改，可以把海外 VPS 的 receiver 放在 Nginx 反代后面启用 HTTPS，或者改用 SSH 隧道转发端口
- `PUSH_KEY` 是唯一鉴权手段，建议用 `openssl rand -hex 32` 生成一个足够长的随机串
- receiver 默认监听 `0.0.0.0`，建议在防火墙层面限制只允许国内机器的 IP 访问 8765 端口

### china_relay_collector.py 内容说明

这个脚本已经在 `scripts/` 目录下，采集范围：

| 平台 | 采集方式 | 字段 |
|---|---|---|
| 微博热搜 | 微博官方 Ajax 接口（`weibo.com/ajax/side/hotSearch`） | 标题 + 热度分 |
| 百度热搜 | 解析百度热搜榜 HTML | 标题 |
| 知乎热搜 | 知乎官方 API（`zhihu.com/api/v3/feed/topstory/hot-lists`） | 标题 + 关注数 |

脚本内置了标题级去重（同一热搜在不同平台可能出现两次），推送前自动去重减小网络开销。
