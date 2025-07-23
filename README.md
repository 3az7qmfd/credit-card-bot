# 💳 智能信用卡管理机器人

基于 Telegram 的智能信用卡管理系统，采用 Apple 设计理念，提供极简而强大的信用卡管理体验。

## ✨ 项目优势

- **智能推荐** - 基于免息期自动推荐最优消费卡片
- **分币种推荐** - 人民币和外币消费分别优化
- **可交互日历** - 点击查看详细还款信息
- **年费管理** - 自动提醒和豁免状态跟踪
- **数据安全** - 仅存储卡片后四位，保护隐私

## 🚀 核心功能

```
/addcard   - 添加新卡片
/editcard  - 编辑卡片信息
/delcard   - 删除卡片
/cards     - 卡片组合概览
/ask       - 智能消费建议
/calendar  - 还款日历视图
/checkfees - 手动年费检查
```

## 📦 部署方式

### 🔧 Telegram 机器人设置

#### 1. 创建机器人
1. 在 Telegram 中找到 [@BotFather](https://t.me/botfather)
2. 发送 `/newbot` 创建新机器人
3. 按提示设置机器人名称和用户名
4. 获取 Bot Token 并保存

#### 2. 获取用户ID
1. 在 Telegram 中找到 [@userinfobot](https://t.me/userinfobot)
2. 发送任意消息获取您的用户ID
3. 记录用户ID用于配置


### 🐳 Docker Compose 部署
创建 `compose.yml` 文件：

```yaml
services:
  card-bot:
    image: ghcr.io/3az7qmfd/credit-card-bot:latest
    volumes:
      - ./data:/app/data
    restart: always
    environment:
      - ADMIN_USER_ID= #你的管理员ID
      - TELEGRAM_BOT_TOKEN= #你的 Bot Token
      - TZ=Asia/Shanghai
```

启动服务：
```bash

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

## 🔒 安全特性

- **单用户设计** - 仅指定管理员可使用
- **最小化数据** - 仅存储必要的卡片信息
- **本地存储** - 数据不上传第三方服务
- **操作确认** - 重要操作需要确认

---

**🌟 如果这个项目对您有帮助，请给个 Star！**
