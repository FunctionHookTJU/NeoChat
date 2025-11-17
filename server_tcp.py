"""
NeoChat TCP 服务端
使用原始 TCP Socket，适配内网穿透 TCP 隧道
"""

import asyncio
import json
from datetime import datetime
import signal
import sys
import platform
import socket
import os
import time
import threading

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

class TCPChatServer:
    def __init__(self, host='0.0.0.0', port=9999):
        self.host = host
        self.port = port
        self.clients = {}  # {writer: username}
        self.client_info = {}  # {writer: {address, connect_time}}
        self.ip_to_writer = {}  # {ip_address: writer} 根据IP防止重复连接
        self.messages = []  # 消息历史
        self.message_count = 0
        self.start_time = datetime.now()
        self.is_running = True
        
        # 日志相关
        self.log_dir = 'chat_logs'
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 启动定时日志保存和内存清理线程（每3小时）
        self.periodic_task_thread = threading.Thread(target=self._periodic_save_and_clear, daemon=True)
        self.periodic_task_thread.start()
        
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
    
    def _save_logs_to_file(self):
        """保存对话和用户访问情况到日志文件"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(self.log_dir, f'chat_log_{timestamp}.json')
            
            # 收集在线用户信息
            online_users = []
            session_info = []
            for writer, username in list(self.clients.items()):
                online_users.append(username)
                info = self.client_info.get(writer, {})
                session_info.append({
                    'username': username,
                    'address': info.get('address', 'Unknown'),
                    'connect_time': info.get('connect_time', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
                    'online_duration': (datetime.now() - info.get('connect_time', datetime.now())).total_seconds()
                })
            
            log_data = {
                'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'server_start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_messages': len(self.messages),
                'message_count': self.message_count,
                'current_online_users': len(self.clients),
                'online_users': online_users,
                'messages': self.messages.copy(),
                'session_info': session_info
            }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            self.log(f"✓ 日志已保存: {log_file} | 消息数: {len(self.messages)} | 在线用户: {len(self.clients)}", 'SUCCESS')
            return True
        except Exception as e:
            self.log(f"保存日志失败: {e}", 'ERROR')
            return False
    
    def _clear_memory(self):
        """清除内存中的消息历史"""
        try:
            old_message_count = len(self.messages)
            self.messages.clear()
            self.message_count = 0
            self.log(f"✓ 内存已清理: 清除了 {old_message_count} 条消息", 'SUCCESS')
            return True
        except Exception as e:
            self.log(f"清理内存失败: {e}", 'ERROR')
            return False
    
    def _periodic_save_and_clear(self):
        """定期（每3小时）保存日志并清理内存"""
        interval = 3 * 60 * 60  # 3小时（秒）
        
        while self.is_running:
            try:
                # 等待3小时
                time.sleep(interval)
                
                if not self.is_running:
                    break
                
                self.log("开始执行定期日志保存和内存清理...", 'SYSTEM')
                
                # 1. 保存日志
                if self._save_logs_to_file():
                    # 2. 清理内存
                    self._clear_memory()
                    self.log("定期任务完成", 'SUCCESS')
                else:
                    self.log("定期任务失败：日志保存失败", 'ERROR')
                    
            except Exception as e:
                self.log(f"定期任务错误: {e}", 'ERROR')
    
    async def handle_client(self, reader, writer):
        """处理单个客户端连接"""
        username = None
        addr = writer.get_extra_info('peername')
        client_address = f"{addr[0]}:{addr[1]}" if addr else "Unknown"
        client_ip = addr[0] if addr else "Unknown"
        
        try:
            # 检查是否已有此IP的连接
            if client_ip in self.ip_to_writer:
                old_writer = self.ip_to_writer[client_ip]
                if old_writer in self.clients:
                    old_username = self.clients[old_writer]
                    self.log(f"检测到重复连接，关闭旧连接: {old_username} ({client_ip})", 'WARNING')
                    
                    # 关闭旧连接
                    try:
                        old_writer.close()
                        await old_writer.wait_closed()
                    except:
                        pass
                    
                    # 清理旧连接的数据
                    if old_writer in self.clients:
                        del self.clients[old_writer]
                    if old_writer in self.client_info:
                        del self.client_info[old_writer]
            
            # 记录连接信息
            self.client_info[writer] = {
                'address': client_address,
                'connect_time': datetime.now(),
                'ip': client_ip
            }
            self.ip_to_writer[client_ip] = writer
            
            self.log(f"新连接来自 {client_address}", 'INFO')
            
            # 接收用户名（设置超时）
            try:
                data = await asyncio.wait_for(reader.readline(), timeout=30.0)
                username = data.decode('utf-8').strip()
                
                # 过滤无效的用户名（HTTP 请求等）
                if not username or username.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HEAD ', 'OPTIONS ', 'PATCH ', 'HTTP/')):
                    self.log(f"客户端 {client_address} 发送了无效的用户名或 HTTP 请求", 'WARNING')
                    writer.close()
                    await writer.wait_closed()
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
                writer.close()
                await writer.wait_closed()
                return
            
            # 添加到客户端列表
            self.clients[writer] = username
            self.client_info[writer]['username'] = username
            
            self.log(f"✓ {username} ({client_address}) 加入聊天室 | 在线人数: {len(self.clients)}", 'SUCCESS')
            
            # 广播加入消息
            join_msg = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"{username} 加入了聊天室"
            }
            self.messages.append(join_msg)  # 保存到历史
            await self.broadcast(json.dumps(join_msg, ensure_ascii=False) + '\n', exclude=writer)
            
            # 发送欢迎消息
            welcome_msg = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"欢迎来到 NeoChat！当前在线人数: {len(self.clients)}"
            }
            writer.write((json.dumps(welcome_msg, ensure_ascii=False) + '\n').encode('utf-8'))
            await writer.drain()
            
            # 持续接收消息
            while self.is_running:
                data = await reader.readline()
                if not data:
                    break
                
                message = data.decode('utf-8').strip()
                if message:
                    # 过滤 HTTP 协议相关的消息（忽略 HTTP 请求头）
                    # 检查是否是 HTTP 请求行或请求头
                    if (message.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HEAD ', 'OPTIONS ', 'PATCH ', 'TRACE ', 'CONNECT ')) or
                        message.startswith('HTTP/') or
                        ':' in message and message.split(':', 1)[0].strip() in [
                            'Host', 'User-Agent', 'Accept', 'Accept-Encoding', 'Accept-Language',
                            'Connection', 'Content-Type', 'Content-Length', 'Origin', 'Referer',
                            'Cache-Control', 'Pragma', 'Authorization', 'Cookie', 'Set-Cookie',
                            'Access-Control-Request-Method', 'Access-Control-Request-Headers',
                            'X-Forwarded-For', 'X-Forwarded-Proto', 'X-Real-Ip', 'X-Original-Host',
                            'Sec-Fetch-Dest', 'Sec-Fetch-Mode', 'Sec-Fetch-Site', 'Priority',
                            'Upgrade', 'Sec-WebSocket-Key', 'Sec-WebSocket-Version'
                        ]):
                        # 忽略 HTTP 协议消息，不记录不广播
                        continue
                    
                    self.message_count += 1
                    
                    # 检查是否是命令
                    if message.startswith('/'):
                        await self.handle_command(writer, username, message)
                        continue
                    
                    self.log(f"{username}: {message[:50]}{'...' if len(message) > 50 else ''}", 'MESSAGE')
                    
                    # 广播消息
                    broadcast_msg = {
                        'type': 'message',
                        'time': self.get_time(),
                        'username': username,
                        'message': message
                    }
                    self.messages.append(broadcast_msg)  # 保存到历史
                    await self.broadcast(json.dumps(broadcast_msg, ensure_ascii=False) + '\n', exclude=writer)
                    
        except asyncio.CancelledError:
            self.log(f"{username or client_address} 连接被取消", 'INFO')
        except ConnectionResetError:
            self.log(f"{username or client_address} 连接重置", 'WARNING')
        except Exception as e:
            self.log(f"{username or client_address} 发生错误: {type(e).__name__}: {str(e)}", 'ERROR')
        finally:
            # 移除客户端
            if writer in self.clients:
                username = self.clients[writer]
                del self.clients[writer]
                
                if writer in self.client_info:
                    info = self.client_info[writer]
                    duration = (datetime.now() - info['connect_time']).total_seconds()
                    self.log(f"✗ {username} ({client_address}) 离开聊天室 | 在线时长: {duration:.1f}秒 | 剩余: {len(self.clients)}人", 'INFO')
                    
                    # 清理IP映射
                    if 'ip' in info and info['ip'] in self.ip_to_writer:
                        if self.ip_to_writer[info['ip']] == writer:
                            del self.ip_to_writer[info['ip']]
                    
                    del self.client_info[writer]
                
                # 广播离开消息
                leave_msg = {
                    'type': 'system',
                    'time': self.get_time(),
                    'message': f"{username} 离开了聊天室"
                }
                self.messages.append(leave_msg)  # 保存到历史
                await self.broadcast(json.dumps(leave_msg, ensure_ascii=False) + '\n')
            
            # 关闭连接
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def handle_command(self, writer, username, command):
        """处理客户端命令"""
        parts = command.split()
        cmd = parts[0].lower()
        
        response = None
        
        if cmd == '/help':
            response = {
                'type': 'system',
                'time': self.get_time(),
                'message': '可用命令: /help, /online, /ping, /stats, /savelog'
            }
        
        elif cmd == '/online':
            users = ', '.join(self.clients.values())
            response = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"在线用户 ({len(self.clients)}): {users}"
            }
        
        elif cmd == '/ping':
            response = {
                'type': 'system',
                'time': self.get_time(),
                'message': 'Pong! 服务器运行正常'
            }
        
        elif cmd == '/stats':
            uptime = (datetime.now() - self.start_time).total_seconds()
            response = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"服务器统计: 运行时长 {uptime:.0f}秒, 消息总数 {self.message_count}, 在线人数 {len(self.clients)}"
            }
        
        elif cmd == '/savelog':
            if self._save_logs_to_file():
                response = {
                    'type': 'system',
                    'time': self.get_time(),
                    'message': '日志已手动保存'
                }
            else:
                response = {
                    'type': 'system',
                    'time': self.get_time(),
                    'message': '日志保存失败'
                }
        
        else:
            response = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"未知命令: {cmd}，输入 /help 查看帮助"
            }
        
        if response:
            writer.write((json.dumps(response, ensure_ascii=False) + '\n').encode('utf-8'))
            await writer.drain()
            self.log(f"{username} 执行命令: {command}", 'SYSTEM')
    
    async def broadcast(self, message, exclude=None):
        """向所有客户端广播消息"""
        if not self.clients:
            return
        
        failed_clients = []
        
        for writer in list(self.clients.keys()):
            if writer != exclude:
                try:
                    writer.write(message.encode('utf-8'))
                    await writer.drain()
                except Exception as e:
                    failed_clients.append(writer)
                    self.log(f"向 {self.clients.get(writer, 'Unknown')} 发送消息失败: {e}", 'WARNING')
        
        # 清理失败的连接
        for writer in failed_clients:
            if writer in self.clients:
                del self.clients[writer]
            if writer in self.client_info:
                del self.client_info[writer]
    
    async def send_server_message(self):
        """允许服务器发送消息的输入循环"""
        print()
        self.log("服务器控制台已就绪", 'SYSTEM')
        self.log("输入消息发送给所有客户端", 'SYSTEM')
        self.log("命令: 'quit'=退出, 'stats'=统计, 'list'=在线用户, 'savelog'=保存日志", 'SYSTEM')
        print("─" * 60)
        
        loop = asyncio.get_event_loop()
        
        while self.is_running:
            try:
                message = await loop.run_in_executor(None, input, f"{Colors.GREEN}Server>{Colors.ENDC} ")
                message = message.strip()
                
                if not message:
                    continue
                
                if message.lower() in ('quit', 'exit', 'stop'):
                    self.log("正在关闭服务器...", 'WARNING')
                    self.is_running = False
                    
                    shutdown_msg = {
                        'type': 'system',
                        'time': self.get_time(),
                        'message': '服务器即将关闭'
                    }
                    await self.broadcast(json.dumps(shutdown_msg, ensure_ascii=False) + '\n')
                    
                    for writer in list(self.clients.keys()):
                        try:
                            writer.close()
                            await writer.wait_closed()
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
                        for writer, username in self.clients.items():
                            info = self.client_info.get(writer, {})
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
                
                elif message.lower() == 'savelog':
                    if self._save_logs_to_file():
                        self.log("日志已手动保存", 'SUCCESS')
                    else:
                        self.log("日志保存失败", 'ERROR')
                
                else:
                    broadcast_msg = {
                        'type': 'message',
                        'time': self.get_time(),
                        'username': 'Server',
                        'message': message
                    }
                    self.messages.append(broadcast_msg)  # 保存到历史
                    await self.broadcast(json.dumps(broadcast_msg, ensure_ascii=False) + '\n')
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
        print(f"{Colors.BOLD}{Colors.CYAN}      NeoChat TCP 服务器{Colors.ENDC}")
        print("═" * 60)
        print(f"{Colors.GREEN}✓{Colors.ENDC} 服务器已启动")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 监听地址: {Colors.BOLD}{self.host}:{self.port}{Colors.ENDC}")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 协议类型: {Colors.BOLD}TCP Socket{Colors.ENDC}")
        
        if self.host == '0.0.0.0':
            local_ip = self.get_local_ip()
            print(f"{Colors.GREEN}✓{Colors.ENDC} 本机访问: {Colors.BOLD}localhost:{self.port}{Colors.ENDC}")
            print(f"{Colors.GREEN}✓{Colors.ENDC} 局域网访问: {Colors.BOLD}{local_ip}:{self.port}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}✓{Colors.ENDC} Python 版本: {platform.python_version()}")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 操作系统: {platform.system()} {platform.release()}")
        print("─" * 60)
        print(f"{Colors.YELLOW}📝{Colors.ENDC} 使用 TCP 客户端连接")
        print(f"{Colors.YELLOW}💡{Colors.ENDC} 支持内网穿透 TCP 隧道")
        print("═" * 60)
    
    async def start(self):
        """启动服务器"""
        try:
            self.print_banner()
            
            server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port
            )
            
            self.log("TCP 服务器已就绪，等待连接...", 'SUCCESS')
            
            async with server:
                # 启动服务器消息输入
                await self.send_server_message()
                
        except OSError as e:
            if e.errno == 10048:
                self.log(f"端口 {self.port} 已被占用！", 'ERROR')
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
    
    port = 9999
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"{Colors.RED}错误: 无效的端口号{Colors.ENDC}")
            sys.exit(1)
    
    server = TCPChatServer(port=port)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[服务器] 已关闭{Colors.ENDC}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}再见！{Colors.ENDC}")
