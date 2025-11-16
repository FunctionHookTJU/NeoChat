"""
NeoChat WebSocket 服务端 (增强版)
支持 Web 客户端连接，提供详细的日志和错误处理
"""

import asyncio
import websockets
from datetime import datetime
import signal
import sys
import platform
import socket
from http import HTTPStatus
import logging

class Colors:
    """终端颜色代码"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ChatServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.clients = {}  # {websocket: username}
        self.client_info = {}  # {websocket: {address, connect_time}}
        self.message_count = 0
        self.start_time = datetime.now()
        self.is_running = True
        
    def log(self, message, level='INFO'):
        """格式化日志输出"""
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        colors = {
            'INFO': Colors.CYAN,
            'SUCCESS': Colors.GREEN,
            'WARNING': Colors.YELLOW,
            'ERROR': Colors.RED,
            'MESSAGE': Colors.BLUE,
            'SYSTEM': Colors.HEADER
        }
        
        color = colors.get(level, Colors.ENDC)
        print(f"{color}[{timestamp}] [{level}]{Colors.ENDC} {message}")
    
    def get_time(self):
        """获取当前时间字符串"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def get_local_ip(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    async def handle_client(self, websocket):
        """处理单个客户端连接"""
        username = None
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if websocket.remote_address else "Unknown"
        
        try:
            # 记录连接信息
            self.client_info[websocket] = {
                'address': client_address,
                'connect_time': datetime.now()
            }
            
            self.log(f"新连接来自 {client_address}", 'INFO')
            
            # 接收用户名（设置超时）
            try:
                username = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                username = username.strip()
                
                if not username:
                    self.log(f"客户端 {client_address} 未提供用户名", 'WARNING')
                    await websocket.close()
                    return
                
                # 检查用户名是否已存在
                existing_names = list(self.clients.values())
                if username in existing_names:
                    original_username = username
                    counter = 1
                    while username in existing_names:
                        username = f"{original_username}_{counter}"
                        counter += 1
                    self.log(f"用户名 {original_username} 已存在，自动改为 {username}", 'WARNING')
                
            except asyncio.TimeoutError:
                self.log(f"客户端 {client_address} 连接超时（未发送用户名）", 'WARNING')
                await websocket.close()
                return
            
            # 添加到客户端列表
            self.clients[websocket] = username
            self.client_info[websocket]['username'] = username
            
            self.log(f"✓ {username} ({client_address}) 加入聊天室 | 在线人数: {len(self.clients)}", 'SUCCESS')
            
            # 广播加入消息
            join_msg = f"[系统 {self.get_time()}] {username} 加入了聊天室"
            await self.broadcast(join_msg, exclude=websocket)
            
            # 发送欢迎消息
            welcome_msg = f"[系统 {self.get_time()}] 欢迎来到 NeoChat！当前在线人数: {len(self.clients)}"
            await websocket.send(welcome_msg)
            
            # 持续接收消息
            async for message in websocket:
                message = message.strip()
                if message:
                    self.message_count += 1
                    
                    # 检查是否是命令
                    if message.startswith('/'):
                        await self.handle_command(websocket, username, message)
                        continue
                    
                    self.log(f"{username}: {message[:50]}{'...' if len(message) > 50 else ''}", 'MESSAGE')
                    
                    # 广播消息
                    broadcast_msg = f"[{self.get_time()}] {username}: {message}"
                    await self.broadcast(broadcast_msg, exclude=websocket)
                    
        except websockets.exceptions.ConnectionClosedOK:
            self.log(f"{username or client_address} 正常断开连接", 'INFO')
        except websockets.exceptions.ConnectionClosedError as e:
            self.log(f"{username or client_address} 连接异常关闭 (代码: {e.code})", 'WARNING')
        except Exception as e:
            self.log(f"{username or client_address} 发生错误: {type(e).__name__}: {str(e)}", 'ERROR')
        finally:
            # 移除客户端
            if websocket in self.clients:
                username = self.clients[websocket]
                del self.clients[websocket]
                
                if websocket in self.client_info:
                    info = self.client_info[websocket]
                    duration = (datetime.now() - info['connect_time']).total_seconds()
                    self.log(f"✗ {username} ({client_address}) 离开聊天室 | 在线时长: {duration:.1f}秒 | 剩余: {len(self.clients)}人", 'INFO')
                    del self.client_info[websocket]
                
                # 广播离开消息
                leave_msg = f"[系统 {self.get_time()}] {username} 离开了聊天室"
                await self.broadcast(leave_msg)
    
    async def handle_command(self, websocket, username, command):
        """处理客户端命令"""
        parts = command.split()
        cmd = parts[0].lower()
        
        if cmd == '/help':
            help_msg = f"[系统 {self.get_time()}] 可用命令: /help, /online, /ping, /stats"
            await websocket.send(help_msg)
        
        elif cmd == '/online':
            users = ', '.join(self.clients.values())
            online_msg = f"[系统 {self.get_time()}] 在线用户 ({len(self.clients)}): {users}"
            await websocket.send(online_msg)
        
        elif cmd == '/ping':
            pong_msg = f"[系统 {self.get_time()}] Pong! 服务器运行正常"
            await websocket.send(pong_msg)
        
        elif cmd == '/stats':
            uptime = (datetime.now() - self.start_time).total_seconds()
            stats_msg = (f"[系统 {self.get_time()}] 服务器统计: "
                        f"运行时长 {uptime:.0f}秒, "
                        f"消息总数 {self.message_count}, "
                        f"在线人数 {len(self.clients)}")
            await websocket.send(stats_msg)
        
        else:
            unknown_msg = f"[系统 {self.get_time()}] 未知命令: {cmd}，输入 /help 查看帮助"
            await websocket.send(unknown_msg)
        
        self.log(f"{username} 执行命令: {command}", 'SYSTEM')
    
    async def broadcast(self, message, exclude=None):
        """向所有客户端广播消息"""
        if not self.clients:
            return
        
        # 创建发送任务
        tasks = []
        failed_clients = []
        
        for client in list(self.clients.keys()):
            if client != exclude:
                try:
                    tasks.append(client.send(message))
                except Exception as e:
                    failed_clients.append(client)
                    self.log(f"向 {self.clients.get(client, 'Unknown')} 发送消息失败: {e}", 'WARNING')
        
        # 并发发送
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 检查发送结果
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.log(f"广播消息时出错: {result}", 'WARNING')
        
        # 清理失败的连接
        for client in failed_clients:
            if client in self.clients:
                del self.clients[client]
            if client in self.client_info:
                del self.client_info[client]
    
    async def send_server_message(self):
        """允许服务器发送消息的输入循环"""
        print()
        self.log("服务器控制台已就绪", 'SYSTEM')
        self.log("输入消息发送给所有客户端", 'SYSTEM')
        self.log("命令: 'quit'=退出, 'stats'=统计, 'list'=在线用户", 'SYSTEM')
        print("─" * 60)
        
        loop = asyncio.get_event_loop()
        
        while self.is_running:
            try:
                # 在异步环境中读取输入
                message = await loop.run_in_executor(None, input, f"{Colors.GREEN}Server>{Colors.ENDC} ")
                message = message.strip()
                
                if not message:
                    continue
                
                # 处理服务器命令
                if message.lower() in ('quit', 'exit', 'stop'):
                    self.log("正在关闭服务器...", 'WARNING')
                    self.is_running = False
                    
                    # 通知所有客户端
                    shutdown_msg = f"[系统 {self.get_time()}] 服务器即将关闭"
                    await self.broadcast(shutdown_msg)
                    
                    # 关闭所有连接
                    for client in list(self.clients.keys()):
                        try:
                            await client.close()
                        except:
                            pass
                    
                    break
                
                elif message.lower() == 'stats':
                    uptime = (datetime.now() - self.start_time).total_seconds()
                    print()
                    self.log(f"运行时长: {uptime:.0f} 秒", 'SYSTEM')
                    self.log(f"在线人数: {len(self.clients)}", 'SYSTEM')
                    self.log(f"消息总数: {self.message_count}", 'SYSTEM')
                    print()
                
                elif message.lower() == 'list':
                    if self.clients:
                        print()
                        self.log(f"在线用户 ({len(self.clients)}):", 'SYSTEM')
                        for ws, username in self.clients.items():
                            info = self.client_info.get(ws, {})
                            address = info.get('address', 'Unknown')
                            connect_time = info.get('connect_time')
                            if connect_time:
                                duration = (datetime.now() - connect_time).total_seconds()
                                print(f"  • {username} ({address}) - 在线 {duration:.0f}秒")
                            else:
                                print(f"  • {username} ({address})")
                        print()
                    else:
                        self.log("当前无在线用户", 'INFO')
                
                else:
                    # 发送服务器消息
                    broadcast_msg = f"[{self.get_time()}] Server: {message}"
                    await self.broadcast(broadcast_msg)
                    self.log(f"已广播: {message}", 'SUCCESS')
                    self.message_count += 1
                    
            except EOFError:
                self.log("检测到输入结束", 'WARNING')
                break
            except Exception as e:
                self.log(f"输入循环错误: {e}", 'ERROR')
                break
    
    def print_banner(self):
        """打印服务器启动横幅"""
        print("\n" + "═" * 60)
        print(f"{Colors.BOLD}{Colors.CYAN}      NeoChat WebSocket 服务器 (增强版){Colors.ENDC}")
        print("═" * 60)
        print(f"{Colors.GREEN}✓{Colors.ENDC} 服务器已启动")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 监听地址: {Colors.BOLD}{self.host}:{self.port}{Colors.ENDC}")
        
        if self.host == '0.0.0.0':
            local_ip = self.get_local_ip()
            print(f"{Colors.GREEN}✓{Colors.ENDC} 本机访问: {Colors.BOLD}ws://localhost:{self.port}{Colors.ENDC}")
            print(f"{Colors.GREEN}✓{Colors.ENDC} 局域网访问: {Colors.BOLD}ws://{local_ip}:{self.port}{Colors.ENDC}")
        else:
            print(f"{Colors.GREEN}✓{Colors.ENDC} 访问地址: {Colors.BOLD}ws://{self.host}:{self.port}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}✓{Colors.ENDC} Python 版本: {platform.python_version()}")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 操作系统: {platform.system()} {platform.release()}")
        print("─" * 60)
        print(f"{Colors.YELLOW}📝{Colors.ENDC} 在浏览器中打开 {Colors.BOLD}client.html{Colors.ENDC} 开始聊天")
        print(f"{Colors.YELLOW}💡{Colors.ENDC} 提示: 客户端可以使用命令 /help, /online, /ping, /stats")
        print("═" * 60)
    
    async def start(self):
        """启动服务器"""
        try:
            # 禁用 websockets 库的错误日志（健康检查会产生大量噪音）
            logging.getLogger('websockets.server').setLevel(logging.CRITICAL)
            logging.getLogger('websockets.protocol').setLevel(logging.CRITICAL)
            
            self.print_banner()
            
            # 启动 WebSocket 服务器
            async with websockets.serve(
                self.handle_client, 
                self.host, 
                self.port,
                ping_interval=30,  # 每30秒发送一次ping
                ping_timeout=10,   # ping超时10秒
                max_size=1024 * 1024,  # 最大消息大小 1MB
                compression=None   # 禁用压缩以提高性能
            ):
                self.log("WebSocket 服务器已就绪，等待连接...", 'SUCCESS')
                self.log("已启用健康检查容错（忽略空连接）", 'INFO')
                
                # 启动服务器消息输入
                await self.send_server_message()
                
        except OSError as e:
            if e.errno == 10048:  # Windows: 端口已被占用
                self.log(f"端口 {self.port} 已被占用！请尝试:", 'ERROR')
                print(f"  1. 关闭其他使用该端口的程序")
                print(f"  2. 更改服务器端口号")
                print(f"  3. 使用命令查看占用: netstat -ano | findstr {self.port}")
            else:
                self.log(f"服务器启动失败: {e}", 'ERROR')
        except Exception as e:
            self.log(f"服务器错误: {type(e).__name__}: {e}", 'ERROR')

def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    print(f"\n{Colors.YELLOW}[系统] 收到中断信号{Colors.ENDC}")
    sys.exit(0)

async def main():
    """主函数"""
    signal.signal(signal.SIGINT, signal_handler)
    
    # 可以通过命令行参数指定端口
    port = 9999
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"{Colors.RED}错误: 无效的端口号{Colors.ENDC}")
            sys.exit(1)
    
    server = ChatServer(port=port)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[服务器] 已关闭{Colors.ENDC}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}再见！{Colors.ENDC}")
