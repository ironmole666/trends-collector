# VPS B 操作速查备忘手册

当前运行状态的一页纸速查。

---

## 服务架构

```
VPS B（NAT 动态 IP）
    ├── 采集服务     → systemd oneshot，每 6 小时触发
    ├── 邮件推送     → Resend API（HTTPS 443），不依赖 SMTP
    ├── 日报文件     → /opt/trends-collector/logs/report_*.txt
    └── 数据存储     → SQLite /opt/trends-collector/data/trends.db
```

---

## 日常操作

### 查看状态

```bash
# 定时器下次执行时间
systemctl list-timers trends-collector.timer --no-pager

# 最近一次采集日志
sudo tail -10 /opt/trends-collector/logs/collector.log

# 最新日报
sudo cat /opt/trends-collector/logs/$(ls -t /opt/trends-collector/logs/report_*.txt | head -1 | xargs basename)

# 各来源数据量
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) AS count FROM trends GROUP BY source ORDER BY count DESC;"
```

### 手动触发一次采集

```bash
sudo systemctl start trends-collector.service
sleep 5
sudo tail -5 /opt/trends-collector/logs/collector.log
```

### 修改采集间隔

```bash
echo '[Timer]
OnCalendar=
OnCalendar=X:00:00' | sudo tee /etc/systemd/system/trends-collector.timer.d/override.conf
```

常用 X 值：

| 间隔 | X |
|---|---|
| 每 2 小时 | `0/2` |
| 每 6 小时 | `0/6` |
| 每天早 8 点 | `*-*-* 08:00:00` |

改完后：

```bash
sudo systemctl daemon-reload
sudo systemctl restart trends-collector.timer
```

### 暂停/恢复采集

```bash
sudo systemctl stop trends-collector.timer      # 暂停
sudo systemctl start trends-collector.timer     # 恢复
```

---

## 更新代码

```bash
cd ~/test/trends-collector
git pull
sudo rm -rf /opt/trends-collector/src
sudo cp -r ~/test/trends-collector/src /opt/trends-collector/src
sudo /opt/trends-collector/venv/bin/pip install --quiet --force-reinstall -e /opt/trends-collector
sudo systemctl start trends-collector.service
sleep 4
sudo tail -5 /opt/trends-collector/logs/collector.log
```

---

## 邮件配置

### Resend API Key（环境变量，安全）

```bash
echo '[Service]
Environment=SENDGRID_API_KEY=re_你的APIKey' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
sudo systemctl daemon-reload
```

### 切换邮件服务商

编辑 `/opt/trends-collector/config.yaml`，改 `provider` 值：

```yaml
http_email:
    enabled: true
    provider: "resend"       # sendgrid / resend / mailjet
    api_key: ""
    from_addr: "trends@你的域名"
    to_addrs:
      - "youknowwho_1024@qq.com"
```

### 测试邮件

```bash
sudo systemctl start trends-collector.service
sleep 5
sudo tail -5 /opt/trends-collector/logs/collector.log
# 看到 "Email sent via resend API" 即成功
```

---

## 采集源配置

编辑 `/opt/trends-collector/config.yaml`。

### Google Trends 关注哪些国家

```yaml
google_trends:
    enabled: true
    regions:
      - US      # 🇺🇸 美国
      - JP      # 🇯🇵 日本
      - GB      # 🇬🇧 英国
      - DE      # 🇩🇪 德国
```

### Wikipedia 关注哪些语言

```yaml
wikipedia:
    enabled: true
    languages:
      - en      # 英文
      - ja      # 日文
      - zh      # 中文
      - de      # 德文
```

### 改完后不需要重启 daemon

```bash
sudo systemctl start trends-collector.service
```

会自动使用新配置。

---

## 日报与数据

### 最新日报

```bash
sudo cat /opt/trends-collector/logs/$(ls -t /opt/trends-collector/logs/report_*.txt | head -1 | xargs basename)
```

### 手动生成日报

```bash
sudo /opt/trends-collector/venv/bin/python -m trends_collector --report
```

### SQLite 查询

```bash
# 所有来源统计
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, COUNT(*) FROM trends GROUP BY source ORDER BY COUNT(*) DESC;"

# 最近 24 小时数据量
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT COUNT(*) FROM trends WHERE collected_at > datetime('now', '-1 day');"

# 查看最新的 20 条数据
sudo sqlite3 /opt/trends-collector/data/trends.db \
  "SELECT source, substr(title,1,40), collected_at FROM trends ORDER BY collected_at DESC LIMIT 20;"
```

### 数据备份

```bash
sudo cp /opt/trends-collector/data/trends.db ~/trends.db.backup.$(date +%Y%m%d)
```

---

## 日志文件

| 文件 | 用途 |
|---|---|
| `/opt/trends-collector/logs/collector.log` | 采集运行日志 |
| `/opt/trends-collector/logs/report_*.txt` | 每次采集的日报 |
| `/opt/trends-collector/logs/stdout.log` | systemd stdout |
| `/opt/trends-collector/logs/stderr.log` | systemd stderr |

---

## 文件路径速查

| 用途 | 路径 |
|---|---|
| 项目代码 | `~/test/trends-collector/` |
| 安装目录 | `/opt/trends-collector/` |
| Python 虚拟环境 | `/opt/trends-collector/venv/` |
| 配置文件 | `/opt/trends-collector/config.yaml` |
| SQLite 数据库 | `/opt/trends-collector/data/trends.db` |
| 采集日志 | `/opt/trends-collector/logs/collector.log` |
| 日报文件 | `/opt/trends-collector/logs/report_*.txt` |
| 密钥环境变量 | `/etc/systemd/system/trends-collector.service.d/override.conf` |
| 采集间隔配置 | `/etc/systemd/system/trends-collector.timer.d/override.conf` |

---

## Git 操作

```bash
# 拉取最新代码
git pull

# 查看改了什么
git status

# 查看最近提交
git log --oneline -5

# 查看一次提交改了什么文件
git show --stat 提交ID
```

---

## 迁移到新 VPS

1. 新 VPS 上 `git clone` + `bash deploy.sh`
2. 配 API Key：`echo '...' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf`
3. 配 config.yaml（添加 `http_email` 和关注的地区）
4. 可选：迁移数据库

详见 README 第十五章。
