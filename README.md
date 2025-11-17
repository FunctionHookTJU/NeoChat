# NeoChat - 现代化聊天系统

一个功能丰富、界面精美的跨平台聊天系统，支持 TCP、HTTP、WebSocket 多种协议，提供图形界面和 Web 客户端。

## ✨ 功能特点

### 🖥️ 多协议支持
- **TCP Socket** - 高性能原始 TCP 连接
- **HTTP/HTTPS** - RESTful API 接口
- **WebSocket** - 实时双向通信

### 🎨 多样化客户端
- **GUI 客户端** - 基于 Tkinter 的精美图形界面，支持 QQ 风格聊天气泡
- **Web 客户端** - 基于浏览器的 HTML5 客户端
- **跨平台支持** - Windows、Linux、macOS 全平台兼容

### 🚀 高级特性
- ✅ 多用户同时在线
- ✅ 实时消息转发
- ✅ IP 地址去重（防止重复连接）
- ✅ 消息历史记录
- ✅ 定期日志保存（每 3 小时自动保存并清理内存）
- ✅ 系统消息通知（用户加入/离开）
- ✅ 支持内网穿透
- ✅ 圆角 UI 设计
- ✅ 鼠标滚轮支持
- ✅ 会话管理
- ✅ 用户名去重

## 📦 项目结构

```
NeoChat/
├── 服务端程序
│   ├── server_tcp.py          # TCP 服务端（推荐用于 GUI 客户端）
│   ├── server_https.py        # HTTP/HTTPS 服务端（支持 Web 客户端）
│   └── server_ws.py           # WebSocket 服务端
│
├── 客户端程序
│   ├── client_gui.py          # GUI 图形界面客户端（推荐）
│   ├── client_beta.html       # Web 浏览器客户端（HTTP）
│   └── client.html            # Web 浏览器客户端（WebSocket）
│
├── 工具程序
│   ├── bridge_server.py       # TCP-WebSocket 桥接服务器
│   └── start_all_tcp.bat      # Windows 一键启动脚本
│
├── 文档
│   ├── README.md              # 本文件
│   ├── TCP_README.md          # TCP 服务器详细文档
│   ├── LOG_FEATURE_README.md  # 日志功能说明
│   └── GUI_CLIENT_README.md   # GUI 客户端使用文档
│
└── 配置与构建
    ├── bridge_config.json     # 桥接服务器配置
    ├── *.spec                 # PyInstaller 打包配置
    └── chat_logs/             # 聊天日志目录（自动生成）
```

## 🚀 快速开始

### 方式一：GUI 客户端（推荐）

**1. 启动 TCP 服务器：**
```bash
python server_tcp.py
# 或指定端口
python server_tcp.py 9999
```

**2. 启动 GUI 客户端：**
```bash
python client_gui.py
```

**3. 在 GUI 界面中输入：**
- 用户名：任意名称
- 服务器地址：`localhost`（本地）或服务器 IP
- 端口：`9999`（默认）

**4. 点击"连接"按钮开始聊天！**

### 方式二：Web 客户端

**1. 启动 HTTP 服务器：**
```bash
python server_https.py
```

**2. 在浏览器中打开：**
```
file:///G:/c_PROJECT/NeoChat/client_beta.html
```

**3. 输入服务器地址（如 `localhost:9999`）连接**

### 方式三：使用打包的可执行文件

**打包 GUI 客户端：**
```bash
pyinstaller -F -w client_gui.py
```

生成的 `dist/client_gui.exe` 可以直接运行，无需 Python 环境。

## 🎨 GUI 客户端特性

### 精美的界面设计
- 🎨 QQ 风格聊天气泡（左对齐/右对齐）
- 🔘 圆角按钮和输入框
- 🎨 现代化配色方案（紫蓝主题）
- 📱 响应式布局

### 强大的功能
- ⌨️ **Enter** 发送消息，**Shift+Enter** 换行
- 🖱️ 鼠标滚轮浏览历史消息
- 🔙 返回按钮重新选择服务器
- ⏱️ 实时显示消息时间
- 👤 用户名彩色标识
- 💬 消息气泡自适应大小

### 连接管理
- ✅ 连接状态实时反馈
- ⚡ 超时检测（5秒）
- 🔄 支持重新连接
- ❌ 智能错误提示

## 📝 服务器功能

### TCP 服务器（server_tcp.py）

**特性：**
- 高性能异步 I/O
- IP 地址防重复连接
- 用户名自动去重
- HTTP 请求过滤（防止内网穿透工具的干扰）
- 命令支持：`/help`、`/online`、`/ping`、`/stats`

**服务器控制台命令：**
- `stats` - 查看服务器统计信息
- `list` - 查看在线用户列表
- `savelog` - 手动保存日志
- `quit` - 关闭服务器
- 直接输入消息 - 服务器广播

**运行：**
```bash
python server_tcp.py [端口号]
```

### HTTP 服务器（server_https.py）

**API 端点：**
- `POST /join?username=xxx` - 加入聊天室
- `POST /message` - 发送消息
- `GET /messages?since=0` - 获取消息历史
- `POST /leave` - 离开聊天室

**特性：**
- RESTful API 设计
- CORS 跨域支持
- 会话管理
- 会话超时检测（5分钟）

**运行：**
```bash
python server_https.py [端口号]
```

### 自动日志与内存管理

所有服务器每 3 小时自动：
1. 保存聊天记录到 JSON 文件（`chat_logs/` 目录）
2. 清理内存中的消息历史
3. 保留在线用户状态

**日志格式示例：**
```json
{
  "timestamp": "2025-11-17_19-30-45",
  "server_type": "TCP",
  "total_messages": 150,
  "online_users": 3,
  "messages": [
    {
      "type": "message",
      "time": "2025-11-17 19:25:30",
      "username": "Alice",
      "message": "Hello!"
    }
  ]
}
```

## 🌐 内网穿透配置

### 使用 frp

**1. 配置 frpc.ini：**
```ini
[common]
server_addr = your-frp-server.com
server_port = 7000
token = your_token

[neochat-tcp]
type = tcp
local_ip = 127.0.0.1
local_port = 9999
remote_port = 17201  # 告诉用户使用这个端口
```

**2. 启动服务：**
```bash
# 启动 NeoChat 服务器
python server_tcp.py 9999

# 启动 frp 客户端
./frpc -c frpc.ini
```

**3. 用户连接信息：**
- 服务器地址：`your-frp-server.com`
- 端口：`17201`

### 使用 cpolar

```bash
cpolar tcp 9999
```

复制生成的公网地址给用户即可。

## 🔧 依赖安装

```bash
# 仅标准库，无需额外依赖
python -m pip install --upgrade pip
```

**Python 版本要求：** Python 3.7+

## 📱 平台支持

| 平台 | GUI 客户端 | Web 客户端 | 服务器 |
|------|-----------|-----------|--------|
| Windows | ✅ | ✅ | ✅ |
| Linux | ✅ | ✅ | ✅ |
| macOS | ✅ | ✅ | ✅ |

## 🎯 使用场景

- 💼 **办公室内网聊天** - 快速部署的团队沟通工具
- 🏠 **家庭局域网** - 家人之间的私密聊天
- 🎮 **游戏开发测试** - 游戏内聊天系统原型
- 📚 **教学演示** - 网络编程教学案例
- 🔬 **技术研究** - 学习异步网络编程

## 📸 界面预览

### GUI 客户端
```
┌─────────────────────────────────────────┐
│  🔙 返回    NeoChat 聊天室     👤 User │
├─────────────────────────────────────────┤
│                                         │
│     系统消息（灰色居中气泡）              │
│                                         │
│  Alice  12:30                           │
│  └─ Hello!（白色气泡）                   │
│                                         │
│                         12:31  Bob      │
│                 (绿色气泡) Hi! ─┘       │
│                                         │
├─────────────────────────────────────────┤
│ [输入框...          ] [发送]            │
└─────────────────────────────────────────┘
```

## ⚙️ 高级配置

### 修改默认端口

**服务器：**
```bash
python server_tcp.py 8888
```

**客户端：**
在 GUI 界面输入对应端口号。

### 自定义日志间隔

编辑服务器代码中的间隔时间：
```python
threading.Event().wait(10800)  # 3小时 = 10800秒
```

## 🔍 故障排除

### 连接失败
1. ✅ 检查服务器是否运行
2. ✅ 确认 IP 地址和端口正确
3. ✅ 检查防火墙设置
4. ✅ ping 测试网络连通性

### GUI 客户端无法启动
```bash
# 检查 Python 版本
python --version

# 确保 tkinter 已安装
python -m tkinter
```

### 打包后无法运行
```bash
# 使用 -w 参数隐藏控制台
pyinstaller -F -w client_gui.py

# 如果仍有问题，尝试不隐藏控制台查看错误
pyinstaller -F client_gui.py
```

### 消息显示异常
- 检查是否有 HTTP 代理干扰
- 服务器会自动过滤 HTTP 请求头

## 📝 开发计划

- [ ] 添加消息加密
- [ ] 支持文件传输
- [ ] 表情符号支持
- [ ] 消息撤回功能
- [ ] 聊天室分组
- [ ] 私聊功能
- [ ] 数据库存储
- [ ] 用户认证系统

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 👨‍💻 作者

**FunctionHookTJU**  
GitHub: https://github.com/FunctionHookTJU/NeoChat

---

**享受聊天的乐趣！** 🎉
