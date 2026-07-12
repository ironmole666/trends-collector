# TrendsCollector

在海外 VPS 上自动采集全球/区域热点的工具。四个数据源稳定运行，每次采集后自动去重存入 SQLite，按来源生成日报（每个源 TOP 10），邮件推送完整日报。

目标机器：Ubuntu 24.04，动态公网 IP。

## 采集哪些数据

| 来源 | 数据内容 | 说明 |
|---|---|---|
| **Google Trends** | 多国每日热搜（按国家分组展示，可自由增删） | RSS + Daily JSON API，config.yaml 中配置 regions |
| **Hacker News** | 首页 30 条最热帖子（标题 + 分数 + 评论数） | Algolia API，**始终稳定** |
| **GitHub** | 5 种语言趋势仓库（按 Star 数排序） | 爬 GitHub Trending 页面，**无需 API Key，无速率限制** |
| **Wikipedia** | 多语言每日最佳文章（按语言分组展示，可自由增删） | Wikimedia REST API，**免费，无需注册**，config.yaml 中配置 languages |
| Reddit | 6 个子版块热门帖子 | 数据中心 IP 常被 403 封禁，视 VPS 网络而定 |
| YouTube | 各地区热门视频 | 可选，需 Google Cloud API Key |

每次采集周期耗时约 15 秒，产出约 350 条数据。

---

## 一、部署前置：获取 QQ 邮箱授权码

> **授权码和 QQ 密码不同**，它是 QQ 邮箱专供第三方客户端登录用的独立密码。

1. 浏览器打开 QQ 邮箱并登录 → 设置 → 账号
2. 找到「POP3/IMAP/SMTP 服务」，点击「开启」
3. 按提示用绑定手机发送短信
4. 页面显示 **16 位授权码**（格式 `abcd1234efgh5678`），复制保存

> 如果忘记了，可在「设置 → 账号」中重新生成。

---

## 二、部署到 VPS

### 拉取代码

```bash
ssh 你的用户名@你的VPS_IP
git clone http://8.148.193.129:3000/gitea/trends-collector.git
cd trends-collector
```

### 一键部署

```bash
bash deploy.sh
```

脚本自动完成：
1. `apt install python3 python3-venv python3-pip curl sqlite3`
2. 复制文件到 `/opt/trends-collector/`
3. 创建 Python venv，安装 `trends_collector` 包 + 依赖
4. 创建 `trends-collector` 系统用户
5. 安装 systemd timer（每 30 分钟执行一次，带 120 秒随机偏移）

### 验证

```bash
systemctl status trends-collector.timer
# → Active: active (waiting)
```

### 更新代码

```bash
cd ~/trends-collector
git pull
bash deploy.sh
```

> 只改 `config.yaml` 的话无需重跑 `deploy.sh`，直接 `sudo systemctl start trends-collector.service` 即可。

---

## 三、配置要关注的地区与语言

### 3.1 Google Trends 关注哪些国家

```bash
sudo vim /opt/trends-collector/config.yaml
```

找到 `google_trends.regions`，增删国家代码：

```yaml
collectors:
  google_trends:
    enabled: true
    regions:
      - US      # 🇺🇸 美国
      - JP      # 🇯🇵 日本
      - CN      # 🇨🇳 中国（海外 IP 返回空数据）
      - TW      # 🇹🇼 台湾
      - VN      # 🇻🇳 越南
      - SG      # 🇸🇬 新加坡
      - GB      # 🇬🇧 英国
      - DE      # 🇩🇪 德国
      - TH      # 🇹🇭 泰国
      - AU      # 🇦🇺 澳大利亚
      - IN      # 🇮🇳 印度
      - IT      # 🇮🇹 意大利
      - KR      # 🇰🇷 韩国
```

> 完整列表参考 [ISO 3166-1 国家代码](https://en.wikipedia.org/wiki/ISO_3166-1)。
> 俄语 PT 等欢迎加 if 大家都不懂。改完保存，`sudo systemctl start trends-collector.service` 即可生效，无需重跑 deploy。

### 3.2 Wikipedia 关注哪些语言

```yaml
collectors:
  wikipedia:
    enabled: true
    languages:
      - en      # 英文
      - ja      # 日文
      - zh      # 中文（海外 IP 可能被限）
      - vi      # 越南文
      - de      # 德文
      - th      # 泰文
      - it      # 意大利文
```

> 完整语言列表参考 [Wikimedia 项目列表](https://meta.wikimedia.org/wiki/List_of_Wikipedias)。

### 3.3 修改后生效

```bash
sudo systemctl start trends-collector.service
sleep 3
sudo tail -5 /opt/trends-collector/logs/collector.log
```

看看对应地区采集到了几条数据。新增的国家/地区会自动出现在日报中，无需其他配置。

---

## 四、配置邮件推送（以 QQ 邮箱为例）

### 3.1 编辑配置文件

```bash
sudo vim /opt/trends-collector/config.yaml
```

```yaml
notifications:
  email:
    enabled: true
    smtp_host: "smtp.qq.com"
    smtp_port: 465
    smtp_user: "你的QQ号@qq.com"
    smtp_password: ""            # 留空
    smtp_use_tls: false          # QQ 邮箱 465 端口走 SSL，false
    from_addr: "你的QQ号@qq.com"
    to_addrs:
      - "你的QQ号@qq.com"
```

> 不会用 nano？`Ctrl+O` 保存，`Ctrl+X` 退出。或者用 `sudo vim`。

### 3.2 配置授权码（无编辑器方案）

以下命令全程用 `echo + tee` 写入，不需要 nano/vim：

```bash
# 创建目录
sudo mkdir -p /etc/systemd/system/trends-collector.service.d

# 写入授权码（把 你的授权码 换成真正的 16 位码）
echo '[Service]
Environment=EMAIL_SMTP_PASSWORD=你的授权码' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
```

### 3.3 测试

```bash
sudo systemctl daemon-reload
sudo systemctl start trends-collector.service
sleep 3
sudo tail -5 /opt/trends-collector/logs/collector.log
```

看到 `Email sent to` 即成功。邮件内容为**完整的日报**（每个数据源 TOP 10，含标题、分数、链接），去 QQ 邮箱收件箱查看。

### 3.4 故障排查

| 日志 | 原因 | 解决 |
|---|---|---|
| `Email auth failed` | 授权码错误 | 重新生成，检查 `override.conf` |
| `Email server disconnected` | 端口/协议不对 | QQ 邮箱必须 465 + `smtp_use_tls: false` |
| 连接超时 | VPS 连不上 smtp.qq.com | 海外 VPS 通常没问题 |

### 3.5 修改授权码

如果想换授权码，重新执行 3.2 的命令覆盖文件即可：

```bash
echo '[Service]
Environment=EMAIL_SMTP_PASSWORD=新授权码' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
sudo systemctl daemon-reload
```

---

## 五、邮件收到的是什么内容

邮件里是**完整的日报文本**，例如：

```
============================================================
📊 热点采集日报 [2026-07-11 16:33]
============================================================

📈 各源统计（24h）:
  Google Trends     :  100
  Wikipedia         :  119
  GitHub            :  102
  Hacker News       :   31

🔥 [Google Trends - 🇺🇸 美国] TOP 10:
   1. 某热搜词
       https://trends.google.com/...

🔥 [Google Trends - 🇯🇵 日本] TOP 10:
   1. 日本热搜词

🔥 [Wikipedia - 🇬🇧 英文] TOP 10:
   1. Article title
       https://en.wikipedia.org/wiki/...

🔥 [Wikipedia - 🇯🇵 日文] TOP 10:
   1. 記事タイトル

🔥 [GitHub 趋势仓库] TOP 10:
   1. [user/repo] repo description
       https://github.com/user/repo

🔥 [Hacker News 前页] TOP 10:
   1. Story title
       https://news.ycombinator.com/item?id=...
```

Telegram 由于字符限制，发送的是短摘要。

---

## 六、采集频率

### 默认

- **每 30 分钟** 自动执行一次
- 每次随机偏移 0~120 秒
- 数据保留 **30 天**，超期自动删除

### 修改频率（无编辑器方案）

```bash
# 创建目录
sudo mkdir -p /etc/systemd/system/trends-collector.timer.d

# 写入新的时间规则（用一个空 OnCalendar= 先清掉默认的 30 分钟）
echo '[Timer]
OnCalendar=
OnCalendar=0/2:00:00
Persistent=true
RandomizedDelaySec=120' | sudo tee /etc/systemd/system/trends-collector.timer.d/override.conf

# 重新加载
sudo systemctl daemon-reload
sudo systemctl restart trends-collector.timer
```

**`OnCalendar` 语法说明：**
- `*:0/N` = 每小时的第 0 分钟起，每 N 分钟一次（N 必须 ≤ 59）
- `0/N:00:00` = 每 N 小时一次（N 任意）
- `daily` = 每天零点一次
- `*-*-* 06:00:00` = 每天早上 6:00

**常用值：**

| 你想要的效果 | 正确写法 | 说明 |
|---|---|---|
| **每 30 分钟** | `*:0/30` | 分钟字段：`起始/步长` |
| **每 1 小时** | `*:00` | 每个整点 |
| **每 2 小时** | `0/2:00:00` | **小时字段**：`起始/步长` |
| **每 6 小时** | `0/6:00:00` | 每天 0/6/12/18 点 |
| **每天零点** | `daily` | 简写 |
| **每天早上 6:00** | `*-*-* 06:00:00` | 完整格式 |

> ⚠️ 常见错误：想改小时间隔却在分钟字段用 `/`（如 `*:0/120`），
> 分钟不能大于 59，systemd 会忽略无效值，退回默认 30 分钟。

查看当前设置：

```bash
systemctl list-timers trends-collector.timer
# 显示下一轮执行时间
```

---

## 七、查看数据

```bash
# 各来源总量
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) AS count FROM trends GROUP BY source ORDER BY count DESC;"

# 最近 10 条
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, title, score, collected_at FROM trends ORDER BY collected_at DESC LIMIT 10;"

# 手动生成日报并打印
sudo /opt/trends-collector/venv/bin/python -m trends_collector --report

# 查看最新日报文件
sudo ls -t /opt/trends-collector/logs/report_*.txt | head -1 | xargs sudo cat
```

---

## 八、日常运维命令

| 操作 | 命令 |
|---|---|
| 手动执行一次采集 | `sudo systemctl start trends-collector.service` |
| 查看最近日志 | `sudo tail -20 /opt/trends-collector/logs/collector.log` |
| 查看采集日报 | `sudo cat /opt/trends-collector/logs/report_*.txt \| tail -30` |
| 查看下轮采集时间 | `systemctl list-timers trends-collector.timer` |
| 暂停采集 | `sudo systemctl stop trends-collector.timer` |
| 恢复采集 | `sudo systemctl start trends-collector.timer` |
| 修改配置后生效 | `sudo systemctl daemon-reload && sudo systemctl start trends-collector.service` |
| 查看数据库大小 | `ls -lh /opt/trends-collector/data/trends.db` |

---

## 九、配置 Telegram 推送

```bash
# 1. Telegram 中 @BotFather 创建 bot，获取 token
# 2. 向 bot 发一条消息，访问 https://api.telegram.org/bot<token>/getUpdates 获取 chat_id

# 3. 写入 token 和 chat_id（无编辑器）
sudo mkdir -p /etc/systemd/system/trends-collector.service.d
echo '[Service]
Environment=TELEGRAM_BOT_TOKEN=你的bot_token
Environment=TELEGRAM_CHAT_ID=你的chat_id' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
```

> 注意：如果之前已经为邮箱创建了 `override.conf`，`tee` 会覆盖整个文件。请把邮箱和 Telegram 的配置合并到同一个 `[Service]` 块下。

完整示范（同时配置邮箱 + Telegram）：

```bash
echo '[Service]
Environment=EMAIL_SMTP_PASSWORD=你的16位授权码
Environment=TELEGRAM_BOT_TOKEN=你的bot_token
Environment=TELEGRAM_CHAT_ID=你的chat_id' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
```

修改 `config.yaml` 启用 Telegram：

```yaml
notifications:
  telegram:
    enabled: true
    bot_token: ""        # 留空，走环境变量
    chat_id: ""          # 留空，走环境变量
```

生效：

```bash
sudo systemctl daemon-reload
sudo systemctl start trends-collector.service
```

---

## 十、配置 YouTube 采集（可选）

需要 Google Cloud API Key：[启用 YouTube Data API v3](https://console.cloud.google.com/) 并创建密钥。

```bash
# 写入 API Key（可选，加在 override.conf 中）
echo '[Service]
Environment=YOUTUBE_API_KEY=你的API_KEY' | sudo tee -a /etc/systemd/system/trends-collector.service.d/override.conf
sudo systemctl daemon-reload
```

> `tee -a` 是追加写入，不会覆盖已有的配置。

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

## 十一、数据源说明

| 源 | 可用性 | 原理 |
|---|---|---|
| **Google Trends** | 多数 IP 可用，含降级链 | RSS → Daily JSON API → Realtime JSON API |
| **Reddit** | 数据中心 IP 常被 403 封禁 | 浏览器 UA，仍取决于 IP 段 |
| **Hacker News** | **始终可用** | Algolia API |
| **GitHub** | **始终可用**，无速率限制 | 爬 `github.com/trending` HTML，3 种解析 + Search API 兜底 |
| **Wikipedia** | **始终可用** | Wikimedia REST API（需正确 User-Agent） |
| **YouTube** | 需 API Key，免费配额 | Google API |

如果 Reddit 对你很重要，换一个家宽 IP 段的 VPS 即可恢复。

---

## 十二、进阶：采集中国大陆热点（微博/百度/知乎）

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

`scripts/china_relay_collector.py` 和 `trends-collector-receiver.service` 文件内有完整的配置说明。

---

## 十三、配置文件路径速查

| 用途 | 文件路径 | 编辑方式 |
|---|---|---|
| 采集源配置（地区、开关等） | `/opt/trends-collector/config.yaml` | `sudo nano ...` 或 `sudo vim ...` |
| 授权码、API Key 等密钥 | `/etc/systemd/system/trends-collector.service.d/override.conf` | `echo ... \| sudo tee ...` |
| 采集频率 | `/etc/systemd/system/trends-collector.timer.d/override.conf` | `echo ... \| sudo tee ...` |
| 采集日志 | `/opt/trends-collector/logs/collector.log` | `sudo tail -20` |
| 日报文件 | `/opt/trends-collector/logs/report_*.txt` | `sudo cat` |
| SQLite 数据库 | `/opt/trends-collector/data/trends.db` | `sudo sqlite3` |

---

## 十四、项目结构

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

---

## 十五、迁移到新 VPS

将采集服务从一台 VPS 迁移到另一台的标准流程。

### 第 1 步：停掉旧 VPS

```bash
ssh 旧VPS的IP

# 停用定时器
sudo systemctl stop trends-collector.timer
sudo systemctl disable trends-collector.timer

# 可选：备份数据库（如果要保留历史数据）
cp /opt/trends-collector/data/trends.db ~/trends.db.backup
```

### 第 2 步：在新 VPS 上部署

```bash
ssh 新VPS的IP

# 拉取代码
git clone http://8.148.193.129:3000/gitea/trends-collector.git
cd trends-collector

# 一键部署
bash deploy.sh
```

### 第 3 步：配置密钥（邮箱授权码等）

```bash
# 创建 override 目录（如果不存在）
sudo mkdir -p /etc/systemd/system/trends-collector.service.d

# 写入邮箱授权码
echo '[Service]
Environment=EMAIL_SMTP_PASSWORD=你的QQ邮箱授权码' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf

# 如果有 Telegram 或 YouTube，加在同一行：
echo '[Service]
Environment=EMAIL_SMTP_PASSWORD=你的授权码
Environment=TELEGRAM_BOT_TOKEN=你的token
Environment=TELEGRAM_CHAT_ID=你的chat_id' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf

sudo systemctl daemon-reload
```

### 第 4 步：配置关注的地区（如需）

```bash
sudo nano /opt/trends-collector/config.yaml
```

参照第三章修改 `google_trends.regions` 和 `wikipedia.languages`。

### 第 5 步：测试运行

```bash
sudo systemctl start trends-collector.service
sleep 4
sudo tail -10 /opt/trends-collector/logs/collector.log
```

确认输出包含 `Email sent to`（邮件推送成功）并且有多个来源采集到数据。

### 第 6 步：检查定时器

```bash
systemctl status trends-collector.timer
systemctl list-timers trends-collector.timer
```

确认 `Active: active (waiting)`，下一轮执行时间正确。

### 第 7 步（可选）：迁移历史数据

如果旧 VPS 上积累的数据想要保留：

```bash
# 在旧 VPS 上，把备份传过来
scp ~/trends.db.backup 新VPS的IP:/tmp/

# 在新 VPS 上，替换数据库
sudo systemctl stop trends-collector.service
sudo cp /tmp/trends.db.backup /opt/trends-collector/data/trends.db
sudo chown trends-collector:trends-collector /opt/trends-collector/data/trends.db
sudo systemctl start trends-collector.service
```

### 验证迁移完成

```bash
# 查看日报，确认数据正常
sudo /opt/trends-collector/venv/bin/python -m trends_collector --report

# 查看最新日报文件
sudo cat /opt/trends-collector/logs/report_$(ls -t /opt/trends-collector/logs/report_*.txt | head -1 | xargs basename)
```

> 以后所有 `git pull` 和代码更新都在新 VPS 上操作。旧 VPS 上的定时器已停，不会再发邮件。
