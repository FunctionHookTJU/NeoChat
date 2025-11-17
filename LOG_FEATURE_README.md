# NeoChat 定时日志保存功能说明

## 📋 功能概述

为 `server_https.py` 和 `server_tcp.py` 添加了定时日志保存和内存清理功能。

### ⏰ 定时任务
- **间隔时间**: 每 3 小时自动执行
- **执行内容**: 
  1. 保存对话和用户访问情况到 JSON 文件
  2. 清除内存中的消息历史

### 📁 日志文件

**保存位置**: `chat_logs/`  
**文件命名**: `chat_log_YYYYMMDD_HHMMSS.json` (HTTP) 或 `chat_log_tcp_YYYYMMDD_HHMMSS.json` (TCP)

**日志内容**:
```json
{
  "save_time": "保存时间",
  "server_start_time": "服务器启动时间",
  "total_messages": "消息总数",
  "message_count": "消息计数",
  "current_online_users": "当前在线用户数",
  "online_users": ["用户列表"],
  "messages": [
    {
      "type": "system/message",
      "time": "时间",
      "username": "用户名",
      "message": "消息内容"
    }
  ],
  "session_info": [
    {
      "session_id": "会话ID (仅HTTP)",
      "username": "用户名",
      "address": "IP地址:端口 (仅TCP)",
      "last_active": "最后活动时间 (仅HTTP)",
      "connect_time": "连接时间 (仅TCP)",
      "online_duration": "在线时长秒数 (仅TCP)"
    }
  ]
}
```

## 🚀 使用方法

### 1. HTTP 服务器

#### 启动服务器（生产环境 - 3小时间隔）
```bash
python server_https.py [端口]
```

#### 启动测试版（30秒间隔）
```bash
python server_https_test.py
```

#### 服务器控制台命令
- `savelog` - 手动保存日志
- `stats` - 查看统计信息
- `list` - 查看在线用户
- `quit` - 退出服务器

#### 客户端命令
在聊天框中输入：
- `/savelog` - 触发日志保存
- `/help` - 查看所有命令
- `/online` - 查看在线用户
- `/ping` - 测试连接
- `/stats` - 查看统计

### 2. TCP 服务器

#### 启动服务器（生产环境 - 3小时间隔）
```bash
python server_tcp.py [端口]
```

#### 启动测试版（30秒间隔）
```bash
python server_tcp_test.py
```

#### 服务器控制台命令
- `savelog` - 手动保存日志
- `stats` - 查看统计信息
- `list` - 查看在线用户详情（含IP和在线时长）
- `quit` - 退出服务器

#### 客户端命令
发送消息：
- `/savelog` - 触发日志保存
- `/help` - 查看所有命令
- `/online` - 查看在线用户
- `/ping` - 测试连接
- `/stats` - 查看统计

## 🧪 快速测试

### 测试 HTTP 服务器
1. 启动测试服务器（30秒间隔）：
   ```bash
   python server_https_test.py
   ```

2. 打开 `client_beta.html`，连接到 `localhost:9998`

3. 发送几条消息

4. 等待 30 秒，查看控制台输出和 `chat_logs/` 目录

### 测试 TCP 服务器
1. 启动测试服务器（30秒间隔）：
   ```bash
   python server_tcp_test.py
   ```

2. 使用 TCP 客户端连接到 `localhost:9998`

3. 发送几条消息

4. 等待 30 秒，查看控制台输出和 `chat_logs/` 目录

## 📊 日志示例

查看生成的日志文件：
```bash
# Windows
type chat_logs\chat_log_20250117_135000.json

# Linux/Mac
cat chat_logs/chat_log_20250117_135000.json
```

## 🔧 自定义间隔时间

如需修改定时任务间隔，编辑服务器文件中的 `_periodic_save_and_clear` 方法：

```python
def _periodic_save_and_clear(self):
    interval = 3 * 60 * 60  # 修改这里：秒数
    # 例如：
    # 1 小时: interval = 1 * 60 * 60
    # 30 分钟: interval = 30 * 60
    # 测试用 10 秒: interval = 10
```

## ⚠️ 注意事项

1. **内存清理**: 定时任务会清除内存中的所有历史消息，但不影响当前在线用户
2. **日志累积**: 日志文件不会自动删除，需要定期手动清理
3. **磁盘空间**: 长时间运行请注意监控 `chat_logs/` 目录大小
4. **时区**: 日志时间使用系统本地时间

## 🛠️ 故障排查

### 日志保存失败
- 检查 `chat_logs/` 目录是否有写入权限
- 确认磁盘空间充足
- 查看服务器控制台的错误信息

### 定时任务不执行
- 确认服务器持续运行超过设定的间隔时间
- 检查控制台是否有错误日志
- 使用测试版（30秒间隔）快速验证

### 日志文件过大
- 考虑缩短定时间隔（如1小时）
- 实施日志轮转策略
- 定期归档或删除旧日志

## 🌍 跨平台兼容性

此功能在以下平台测试通过：
- ✅ Windows 10/11
- ✅ Linux (Ubuntu, Debian, CentOS)
- ✅ macOS (10.14+)

使用标准库模块，无需额外依赖。

## 📝 版本历史

- **v1.0** (2025-01-17): 初始版本
  - 添加 3 小时定时保存
  - 支持手动保存命令
  - 生成 JSON 格式日志
  - 自动内存清理
