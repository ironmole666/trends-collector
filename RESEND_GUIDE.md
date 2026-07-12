# Resend 使用指南

通过 Resend HTTP API 发送邮件，用于 NAT VPS（SMTP 端口被封）的替代方案。

---

## 什么是 Resend

[Resend](https://resend.com) 是一家邮件发送服务商，提供 HTTP API 接口来发送电子邮件。对比传统 SMTP：

| | SMTP（QQ 邮箱） | Resend API |
|---|---|---|
| 端口 | 465 / 587 | **443**（HTTPS） |
| NAT VPS 兼容性 | ❌ 多数被封 | ✅ 通 |
| 需要域名 | ❌ | ✅（验证域名所有权） |
| 免费额度 | 无限制（QQ 免费） | **100 封/天** |
| 注册难度 | 容易 | 需要审核 |

Resend 的 API 走标准的 HTTPS（443 端口），所以即使 VPS 被封了 SMTP 端口，只要还能上网就能发邮件。

---

## 注册 Resend

### 第 1 步：打开注册页面

浏览器访问 https://resend.com/signup

填写：
- 邮箱地址（任意邮箱，不一定是发信用的）
- 密码
- 用户名

### 第 2 步：验证邮箱

Resend 会发一封确认邮件到你注册的邮箱，点击里面的验证链接。

### 第 3 步：添加域名

登录后左侧菜单 → **Domains** → **Add Domain**

输入你在本指南后面购买的域名（如 `alien-game.net`）

Resend 会给出几条 DNS 记录需要添加：

| 类型 | 内容示例 |
|---|---|
| **TXT** | `resend=...`（验证域名所有权） |
| **MX** | `feedback-smtp...`（邮件路由） |
| **TXT** | `v=spf1 include:...`（SPF 防伪造） |
| **CNAME** | `resend._domainkey...`（DKIM 签名） |

> 你需要在你的域名注册商（如 NameSilo、Cloudflare 等）的 DNS 管理页面添加这些记录。添加后等待几分钟到几小时生效。

### 第 4 步：创建 API Key

左侧菜单 → **API Keys** → **Create API Key**

- 权限选 **Full Access**
- 复制生成的 Key（以 `re_` 开头）

---

## 域名购买（如果没有域名）

### 推荐注册商

| 注册商 | 最便宜域名 | 说明 |
|---|---|---|
| [NameSilo](https://namesilo.com) | `.xyz` ~$0.99/年 | 价格透明，WHOIS 隐私免费 |
| [Cloudflare Registrar](https://cloudflare.com/products/registrar/) | 按进价 | 不赚差价，需用 Cloudflare DNS |
| [Namecheap](https://namecheap.com) | `.xyz` ~$1.18/年 | 有时首年优惠 |

### 购买步骤

以 NameSilo 为例：

1. 打开 https://namesilo.com
2. 搜索框输入想要的域名（如 `abc123.xyz`）
3. 选一个便宜的加入购物车
4. 结账（支持支付宝 Alipay）
5. 付款后在 **Manager → My Domains** 可以看到你的域名

### DNS 配置

如果让 Resend 帮你托管发信 DNS（推荐），通常在域名注册商的管理面板中找到 DNS 设置：

1. 在 NameSilo → 你的域名 → **DNS Templates** → **Add/Edit DNS Records**
2. 添加 Resend 给出的 TXT、MX、CNAME 记录
3. 等待 DNS 生效（几秒到几小时不等）

---

## 验证域名是否配置正确

在 Resend 的 Domains 页面，点击域名旁的 **Verify** 按钮。状态变为 **Verified** 后就可以使用了。

如果一直验证不通过，检查：
1. DNS 记录是否拼写正确（TXT 内容、CNAME 目标）
2. 是否等了足够时间（DNS 传播最长 24 小时）
3. 用 `dig` 命令检查：

```bash
# 在你的 VPS B 上验证 DNS
dig txt alien-game.net +short | grep resend
dig mx alien-game.net +short
```

---

## 在项目中配置

### 第 1 步：写入 API Key

Key 通过系统环境变量传入，不写进代码或配置文件：

```bash
echo '[Service]
Environment=SENDGRID_API_KEY=re_你的APIKey' | sudo tee /etc/systemd/system/trends-collector.service.d/override.conf
sudo systemctl daemon-reload
```

### 第 2 步：修改配置

编辑 `/opt/trends-collector/config.yaml`，找到 `http_email`：

```yaml
  http_email:
    enabled: true
    provider: "resend"
    api_key: ""                      # 留空，走环境变量
    from_addr: "trends@你的域名"     # 在 Resend 验证过的域名
    to_addrs:
      - "youknowwho_1024@qq.com"     # 你的 QQ 邮箱收件
```

### 第 3 步：测试发送

```bash
sudo systemctl start trends-collector.service
sleep 5
sudo tail -5 /opt/trends-collector/logs/collector.log
```

看到 `Email sent via resend API` 即成功。

---

## 为什么环境变量叫 SENDGRID_API_KEY

代码初始化时统一读取环境变量 `SENDGRID_API_KEY` 作为 HTTP 邮件 API 的 Key。无论是 SendGrid、Resend 还是其他服务商，都用这个变量名。可以理解为 `HTTP_EMAIL_API_KEY` 的别名。

---

## 日常管理

### 查看剩余额度

Resend 免费版每天 100 封。查看用量：

左侧菜单 → **Activity** → 可以看到发送统计

### 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| `Email sent via resend API` | ✅ 正常 | 去 QQ 邮箱收件箱查看 |
| `HTTP email API error: HTTP 4xx` | API Key 或域名验证问题 | 检查 override.conf 里的 Key |
| `HTTP email API request failed` | 网络不通 | VPS 能不能访问 `api.resend.com`？ |

### 升级额度

如果一天 100 封不够（目前每 6 小时一封，每天 4 封，远低于限额），可以在 Resend 后台购买付费套餐：

- **Pro** ~$20/月：50,000 封/天
- 按需付费：$0.001/封（超出免费额度后）

---

## 备选邮件服务商

如果 Resend 将来不可用，可以切换到其他 HTTP 邮件 API：

| 服务商 | 免费额度 | 代码中 provider | 域名要求 |
|---|---|---|---|
| [Resend](https://resend.com) | 100 封/天 | `resend` | ✅ |
| [SendGrid](https://sendgrid.com) | 100 封/天 | `sendgrid` | ✅ |
| [Mailjet](https://www.mailjet.com) | 200 封/天 | 需新增 provider | ✅ |
| [Mailgun](https://www.mailgun.com) | 100 封/天 | 需新增 provider | ✅ |

切换只需改 config.yaml 中的 `provider` 值和 `from_addr`，然后更新 API Key。

添加新的 provider 需要修改代码 `src/trends_collector/notifier.py` 中的 `_PROVIDERS` 字典，按 `sendgrid` 和 `resend` 的模板添加即可。

---

## 原理解析

### Resend 为什么能在被封了 SMTP 端口的 VPS 上工作

```
VPS B（NAT）
    │
    ├─ 465/587 → 运营商封锁  ❌
    │
    └─ 443 (HTTPS) → 运营商开放 ✅
         │
         └─ api.resend.com:443
              │  POST /emails
              │  {"from": "...", "to": "...", "subject": "...", "text": "..."}
              │  Authorization: Bearer re_xxx
              │
              ▼
           Resend 服务器
              │
              └─ SMTP → QQ 邮箱收件箱
```

Resend 在云端帮你处理了 SMTP 的复杂部分。你的 VPS 只需要通过 HTTPS 把邮件内容发过去，后续投递由 Resend 完成。

### 为什么需要一个域名

Resend 需要验证你拥有这个域名，才能用该域名作为发件人。这样收件方（QQ 邮箱）可以验证邮件确实来自该域名，有效防止伪造和垃圾邮件。这是行业标准做法（SPF/DKIM/DMARC）。
