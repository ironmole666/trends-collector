# TrendsCollector

在海外 VPS 上自动采集全球/区域热点的工具。四个数据源稳定运行，每次采集后自动去重存入 SQLite，可按来源生成日报，支持邮件/Telegram 推送。

目标机器：Ubuntu 24.04，动态公网 IP。

## 采集哪些数据

| 来源 | 数据内容 | 说明 |
|---|---|---|
| **Google Trends** | 10 个地区每日热搜（US/JP/KR/GB 等），含搜索量估计 | RSS + Daily JSON API 双重降级，数据中心 IP 可用 |
| **Hacker News** | 首页 30 条最热帖子（标题 + 分数 + 评论数） | Algolia API，**始终稳定** |
| **GitHub** | 5 种语言趋势仓库（按 Star 数排序） | 爬 GitHub Trending 页面，**无需 API Key，无速率限制** |
| **Wikipedia** | 7 种语言每日最佳文章（按浏览量排序） | Wikimedia REST API，**免费，无需注册** |
| Reddit | 6 个子版块热门帖子 | 数据中⼼ IP 一般被 403 封禁，视 VPS 网络情况而定 |
| YouTube | 各地区热门视频 | 可选，需 Google Cloud API Key |

每次采集周期耗时约 15 秒，产出约 350 条数据。

---

## 一、部署前置：获取 QQ 邮箱授权码

如果要用邮件推送，先准备好 QQ 邮箱的 SMTP 授权码。

> **授权码和 QQ 密码不同**，它是 QQ 邮箱专供第三方客户端登录用的独立密码。

**第 1 步**：浏览器打开 QQ 邮箱并登录 → 设置 → 账号

**第 2 步**：找到「POP3/IMAP/SMTP 服务」，点击「IMAP/SMTP 服务」右边的「开启」

**第 3 步**：按提示用绑定手机发送短信到指定号码

**第 4 步**：发送成功后页面会显示一串 **16 位授权码**（格式类似 `abcd1234efgh5678`），复制保存

> 如果忘记了，可在「设置 → 账号」中重新生成，旧的会失效。

---

## 二、部署到 VPS

### 2.1 登录 VPS，拉取代码

```bash
ssh 你的用户名@你的VPS_IP

# 拉取项目
git clone http://8.148.193.129:3000/gitea/trends-collector.git
cd trends-collector
```

### 2.2 执行一键部署

```bash
bash deploy.sh
```

脚本会以 root 权限自动完成：

1. `apt install python3 python3-venv python3-pip curl sqlite3`
2. 复制文件到 `/opt/trends-collector/`
3. 创建 Python venv，安装 `trends_collector` 包 + 依赖
4. 创建 `trends-collector` 系统用户
5. 安装 systemd timer（每 30 分钟执行一次，带 120 秒随机偏移）

### 2.3 验证部署

```bash
systemctl status trends-collector.timer
```

输出应包含 `Active: active (waiting)`。

### 2.4 更新代码

```bash
cd ~/trends-collector
git pull
bash deploy.sh          # 重新部署，自动覆盖旧文件
```

> 如果只是改了 `config.yaml`，不需要重跑 `deploy.sh`，直接 `sudo systemctl start trends-collector.service` 即可。

---

## 三、配置邮件推送（以 QQ 邮箱为例）

### 3.1 编辑配置文件

```bash
sudo nano /opt/trends-collector/config.yaml
```

找到并修改：

```yaml
notifications:
  email:
    enabled: true                       # false → true
    smtp_host: "smtp.qq.com"
    smtp_port: 465
    smtp_user: "你的QQ号@qq.com"
    smtp_password: ""                   # 留空，下一步配置
    smtp_use_tls: false                 # QQ 邮箱 465 端口走 SSL，false
    from_addr: "你的QQ号@qq.com"
    to_addrs:
      - "你的QQ号@qq.com"
```

### 3.2 配置授权码（推荐用环境变量）

```bash
sudo systemctl edit trends-collector.service
```

填入：

```ini
[Service]
Environment=EMAIL_SMTP_PASSWORD=你的16位授权码
```

保存后：

```bash
sudo systemctl daemon-reload
```

### 3.3 测试邮件推送

```bash
sudo systemctl start trends-collector.service
journalctl -u trends-collector.service -f --since "1 min ago"
```

看到 `Email sent to [...] via smtp.qq.com:465` 即成功。

### 3.4 故障排查

| 错误日志 | 原因 | 解决 |
|---|---|---|
| `Email auth failed` | 授权码错误 | 重新生成，检查 `EMAIL_SMTP_PASSWORD` |
| `Email server disconnected` | 端口/协议不对 | QQ 邮箱必须 465 端口 + `smtp_use_tls: false` |
| 连接超时 | 连不上 smtp.qq.com | 海外 VPS 一般没问题 |

---

## 四、采集频率与数据查看

### 4.1 默认配置

- 每 **30 分钟** 自动执行一次采集
- 每次随机偏移 0~120 秒
- 数据保留 **30 天**，超期自动删除
- 日报文件保存在 `/opt/trends-collector/logs/report_*.txt`

### 4.2 修改采集频率

```bash
sudo systemctl edit trends-collector.timer
```

修改 `OnCalendar` 值：

```ini
[Timer]
OnCalendar=*:0/15        # 每 15 分钟
OnCalendar=*:0,30        # 每 30 分钟（整点和半点）
OnCalendar=daily          # 每天一次
```

然后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart trends-collector.timer
```

### 4.3 查看数据

```bash
# 各来源总量
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) AS count FROM trends GROUP BY source ORDER BY count DESC;"

# 最近 10 条
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, title, score, collected_at FROM trends ORDER BY collected_at DESC LIMIT 10;"

# 生成日报
sudo /opt/trends-collector/venv/bin/python -m trends_collector --report

# 查看最新日报文件
sudo cat /opt/trends-collector/logs/$(ls -t /opt/trends-collector/logs/report_*.txt | head -1)
```

### 4.4 日报示例

```
============================================================
📊 热点采集日报 [2026-07-11 16:33]
============================================================

📈 各源统计（24h）:
  google_trends                 :  100
  wikipedia                     :  119
  github                        :  102
  hackernews                    :   31

🔥 [Google Trends] TOP 10:
   1. [ 1M+ ]  some trending keyword
   2. [ 500K+ ] another trending keyword
       ...

🔥 [Wikipedia 最佳文章] TOP 10:
   1. (score: 523,412) Article title
       https://en.wikipedia.org/wiki/...

🔥 [GitHub 趋势仓库] TOP 10:
   1. (score: 1,234) [user/repo] repo description
       https://github.com/user/repo

🔥 [Hacker News] TOP 10:
   1. (score: 1,343) Story title
       https://news.ycombinator.com/item?id=...
```

---

## 五、日常运维命令

| 操作 | 命令 |
|---|---|
| 手动执行一次采集 | `sudo systemctl start trends-collector.service` |
| 查看最近日志 | `journalctl -u trends-collector.service -f --since "5 min ago"` |
| 检查 timer 状态 | `systemctl status trends-collector.timer` |
| 查看下轮执行时间 | `systemctl list-timers trends-collector.timer` |
| 暂停采集 | `sudo systemctl stop trends-collector.timer` |
| 恢复采集 | `sudo systemctl start trends-collector.timer` |
| 生成日报 | `sudo /opt/trends-collector/venv/bin/python -m trends_collector --report` |
| 查看 DB 大小 | `ls -lh /opt/trends-collector/data/trends.db` |

---

## 六、可选：配置 Telegram 推送

```bash
# 1. 在 Telegram 中 @BotFather 创建 bot，获取 token
# 2. 向 bot 发一条消息，访问 https://api.telegram.org/bot<token>/getUpdates 获取 chat_id

# 3. 配置
sudo systemctl edit trends-collector.service
```

```ini
[Service]
Environment=TELEGRAM_BOT_TOKEN=你的bot_token
Environment=TELEGRAM_CHAT_ID=你的chat_id
```

```bash
sudo nano /opt/trends-collector/config.yaml
```

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: ""          # 留空，走环境变量
    chat_id: ""            # 留空，走环境变量
```

```bash
sudo systemctl daemon-reload
sudo systemctl start trends-collector.service
```

---

## 七、可选：配置 YouTube 采集

需要 Google Cloud API Key：

1. [Google Cloud Console](https://console.cloud.google.com/) → 启用 YouTube Data API v3 → 创建 API 密钥

```bash
sudo systemctl edit trends-collector.service
```

```ini
[Service]
Environment=YOUTUBE_API_KEY=你的API_KEY
```

修改 `config.yaml`：

```yaml
collectors:
  youtube:
    enabled: true
    api_key: ""      # 留空，走环境变量
    regions:
      - US
      - JP
      - GB
```

---

## 八、数据源说明

| 源 | 可用性 | 原理 |
|---|---|---|
| **Google Trends** | 多数 IP 可用，含降级链 | RSS → Daily JSON API → Realtime JSON API |
| **Reddit** | 数据中心 IP 常被 403 封禁 | 浏览器 UA，仍看 IP 段 |
| **Hacker News** | 始终可用 | Algolia API |
| **GitHub** | 始终可用，无速率限制 | 爬 `github.com/trending` HTML，3 种解析模式 + Search API 兜底 |
| **Wikipedia** | 始终可用 | Wikimedia REST API |
| **YouTube** | 需 API Key，免费配额 | Google API |

如果 Reddit 对你很重要，换一个家宽 IP 段的 VPS 即可恢复。

---

## 九、进阶：采集中国大陆热点（微博/百度/知乎）

需要一台能访问国内网络的机器作为中继。

```
国内机器（跑 china_relay_collector.py）
    │  每 30 分钟采集微博/百度/知乎
    │  HTTP POST → /collect
    ▼
海外 VPS（跑 receiver.py + 主节点）
    │  SQLite 统一入库，日报自动合并
    │  邮件推送同时包含国内外热点
```

详细步骤见 `scripts/china_relay_collector.py` 文件头部注释和 `trends-collector-receiver.service`。

---

## 十、项目结构

```
trends-collector/
├── config.yaml                        # 配置文件
├── pyproject.toml                     # Python 包定义
├── requirements.txt                   # Python 依赖
├── deploy.sh                          # Ubuntu 24.04 一键部署
├── Makefile                           # 本地快捷命令
├── trends-collector-receiver.service   # 国内中继接收服务（可选）
├── scripts/
│   └── china_relay_collector.py       # 国内中继采集脚本
└── src/trends_collector/              # Python 包
    ├── __main__.py                    # python -m trends_collector 入口
    ├── config.py                      # 配置加载器（YAML + 环境变量覆盖）
    ├── main.py                        # 采集编排 + 调度循环
    ├── storage.py                     # SQLite 存储 + 去重 + 自动清理
    ├── notifier.py                    # 邮件 + Telegram 通知
    ├── report.py                      # 日报生成（每个源 TOP 10）
    ├── receiver.py                    # HTTP 接收端（国内中继用）
    └── collectors/
        ├── base.py                    # 采集器抽象基类
        ├── google_trends.py           # Google Trends（RSS + JSON API）
        ├── reddit.py                  # Reddit 热门帖子
        ├── hackernews.py              # Hacker News 首页
        ├── github.py                  # GitHub 趋势仓库
        ├── wikipedia.py               # Wikipedia 每日最佳文章
        └── youtube.py                 # YouTube 热门视频（可选）
```
