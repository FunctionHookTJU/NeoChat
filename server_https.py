"""
NeoChat HTTPS 服务端
使用 HTTPS 协议，支持 GET/POST 请求，适配各类 HTTPS 客户端
"""

import asyncio
import json
from datetime import datetime
import signal
import sys
import platform
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import threading
import urllib.parse
import ssl
import os
import time

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

class HTTPChatServer:
    def __init__(self, host='0.0.0.0', port=9999, use_ssl=False, certfile=None, keyfile=None):
        self.host = host
        self.port = port
        self.use_ssl = use_ssl
        self.certfile = certfile
        self.keyfile = keyfile
        self.clients = {}  # {session_id: username}
        self.username_to_session = {}  # {username: session_id} 用户名到会话的映射
        self.client_activity = {}  # {session_id: last_active_time}
        self.messages = []  # 消息历史
        self.message_count = 0
        self.start_time = datetime.now()
        self.is_running = True
        self.session_counter = 0
        self.lock = threading.Lock()
        self.session_timeout = 300  # 5分钟无活动则超时
        
        # 日志相关
        self.log_dir = 'chat_logs'
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
        # 启动会话清理线程
        self.cleanup_thread = threading.Thread(target=self._cleanup_inactive_sessions, daemon=True)
        self.cleanup_thread.start()
        
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
    
    def _cleanup_inactive_sessions(self):
        """清理不活跃的会话"""
        while self.is_running:
            try:
                threading.Event().wait(60)  # 每分钟检查一次
                
                with self.lock:
                    now = datetime.now()
                    inactive_sessions = []
                    
                    for session_id, last_active in list(self.client_activity.items()):
                        if (now - last_active).total_seconds() > self.session_timeout:
                            inactive_sessions.append(session_id)
                    
                    for session_id in inactive_sessions:
                        if session_id in self.clients:
                            username = self.clients[session_id]
                            del self.clients[session_id]
                            del self.client_activity[session_id]
                            
                            # 清理用户名映射
                            if username in self.username_to_session and self.username_to_session[username] == session_id:
                                del self.username_to_session[username]
                            
                            leave_msg = {
                                'type': 'system',
                                'time': self.get_time(),
                                'message': f"{username} 连接超时，已离开聊天室"
                            }
                            self.messages.append(leave_msg)
                            self.log(f"✗ {username} 会话超时 | 剩余: {len(self.clients)}人", 'WARNING')
                            
            except Exception as e:
                self.log(f"会话清理错误: {e}", 'ERROR')
    
    def _save_logs_to_file(self):
        """保存对话和用户访问情况到日志文件"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(self.log_dir, f'chat_log_{timestamp}.json')
            
            with self.lock:
                log_data = {
                    'save_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'server_start_time': self.start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'total_messages': len(self.messages),
                    'message_count': self.message_count,
                    'current_online_users': len(self.clients),
                    'online_users': list(self.clients.values()),
                    'messages': self.messages.copy(),
                    'session_info': [
                        {
                            'session_id': sid,
                            'username': uname,
                            'last_active': self.client_activity.get(sid, datetime.now()).strftime('%Y-%m-%d %H:%M:%S')
                        }
                        for sid, uname in self.clients.items()
                    ]
                }
            
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            
            self.log(f"✓ 日志已保存: {log_file} | 消息数: {len(self.messages)} | 在线用户: {len(self.clients)}", 'SUCCESS')
            return True
        except Exception as e:
            self.log(f"保存日志失败: {e}", 'ERROR')
            return False
    
    def _clear_memory(self):
        """清除内存中的消息历史和旧的活动记录"""
        try:
            with self.lock:
                old_message_count = len(self.messages)
                self.messages.clear()
                self.message_count = 0
                # 保留当前在线用户的会话，但清空离线用户的记录
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
    
    def update_activity(self, session_id):
        """更新会话活动时间"""
        with self.lock:
            if session_id in self.clients:
                self.client_activity[session_id] = datetime.now()
                return True
            return False
    
    def create_session(self, username):
        """创建新会话"""
        with self.lock:
            # 检查用户是否已经在线
            if username in self.username_to_session:
                old_session_id = self.username_to_session[username]
                # 如果旧会话还在，先清理它
                if old_session_id in self.clients:
                    self.log(f"用户 {username} 重新登录，清理旧会话", 'WARNING')
                    del self.clients[old_session_id]
                    if old_session_id in self.client_activity:
                        del self.client_activity[old_session_id]
            
            # 创建新会话
            self.session_counter += 1
            session_id = f"session_{self.session_counter}_{datetime.now().timestamp()}"
            
            # 检查用户名是否需要去重（只在多个不同用户同时在线时）
            existing_names = set(self.clients.values())
            original_username = username
            if username in existing_names:
                counter = 1
                while username in existing_names:
                    username = f"{original_username}_{counter}"
                    counter += 1
                self.log(f"用户名 {original_username} 已存在，自动改为 {username}", 'WARNING')
            
            # 保存会话信息
            self.clients[session_id] = username
            self.username_to_session[username] = session_id
            self.client_activity[session_id] = datetime.now()
            
            # 添加系统消息
            join_msg = {
                'type': 'system',
                'time': self.get_time(),
                'message': f"{username} 加入了聊天室"
            }
            self.messages.append(join_msg)
            
            self.log(f"✓ {username} 加入聊天室 | 会话: {session_id} | 在线人数: {len(self.clients)}", 'SUCCESS')
            
            return session_id, username
    
    def remove_session(self, session_id):
        """移除会话"""
        with self.lock:
            if session_id in self.clients:
                username = self.clients[session_id]
                del self.clients[session_id]
                
                # 清理用户名映射
                if username in self.username_to_session and self.username_to_session[username] == session_id:
                    del self.username_to_session[username]
                
                if session_id in self.client_activity:
                    del self.client_activity[session_id]
                
                # 添加系统消息
                leave_msg = {
                    'type': 'system',
                    'time': self.get_time(),
                    'message': f"{username} 离开了聊天室"
                }
                self.messages.append(leave_msg)
                
                self.log(f"✗ {username} 离开聊天室 | 剩余: {len(self.clients)}人", 'INFO')
                return True
            return False
    
    def send_message(self, session_id, message):
        """发送消息"""
        with self.lock:
            if session_id not in self.clients:
                return {'error': '无效的会话ID，可能已超时'}
            
            # 更新活动时间
            self.client_activity[session_id] = datetime.now()
            
            username = self.clients[session_id]
            
            # 检查是否是命令
            if message.startswith('/'):
                return self.handle_command(username, message)
            
            self.message_count += 1
            
            msg = {
                'type': 'message',
                'time': self.get_time(),
                'username': username,
                'message': message
            }
            self.messages.append(msg)
            
            self.log(f"{username}: {message[:50]}{'...' if len(message) > 50 else ''}", 'MESSAGE')
            
            return {'success': True, 'message': msg}
    
    def handle_command(self, username, command):
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
            self.messages.append(response)
            self.log(f"{username} 执行命令: {command}", 'SYSTEM')
        
        return {'success': True, 'message': response}
    
    def get_messages(self, since=0):
        """获取消息（从指定索引开始）"""
        with self.lock:
            return self.messages[since:]
    
    def print_banner(self):
        """打印服务器启动横幅"""
        print("\n" + "═" * 60)
        print(f"{Colors.BOLD}{Colors.CYAN}      NeoChat HTTP 服务器{Colors.ENDC}")
        print("═" * 60)
        print(f"{Colors.GREEN}✓{Colors.ENDC} 服务器已启动")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 监听地址: {Colors.BOLD}{self.host}:{self.port}{Colors.ENDC}")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 协议类型: {Colors.BOLD}HTTP/1.1{Colors.ENDC}")
        
        if self.host == '0.0.0.0':
            local_ip = self.get_local_ip()
            print(f"{Colors.GREEN}✓{Colors.ENDC} 本机访问: {Colors.BOLD}http://localhost:{self.port}{Colors.ENDC}")
            print(f"{Colors.GREEN}✓{Colors.ENDC} 局域网访问: {Colors.BOLD}http://{local_ip}:{self.port}{Colors.ENDC}")
        
        print(f"{Colors.GREEN}✓{Colors.ENDC} Python 版本: {platform.python_version()}")
        print(f"{Colors.GREEN}✓{Colors.ENDC} 操作系统: {platform.system()} {platform.release()}")
        print("─" * 60)
        print(f"{Colors.YELLOW}📝{Colors.ENDC} API 端点:")
        print(f"  • POST /join?username=xxx - 加入聊天")
        print(f"  • POST /message - 发送消息")
        print(f"  • GET /messages?since=0 - 获取消息")
        print(f"  • POST /leave - 离开聊天")
        print(f"{Colors.YELLOW}💡{Colors.ENDC} 支持内网穿透 HTTP 隧道")
        print("═" * 60)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器"""
    pass

def create_handler(chat_server):
    """创建请求处理器"""
    
    class ChatHTTPRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            """禁用默认日志 - 防止HTTP请求头被记录为聊天消息"""
            pass
        
        def log_request(self, code='-', size='-'):
            """禁用请求日志"""
            pass
        
        def send_json_response(self, data, status=200):
            """发送 JSON 响应"""
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        
        def do_OPTIONS(self):
            """处理 CORS 预检请求"""
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
        
        def do_GET(self):
            """处理 GET 请求"""
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query = urllib.parse.parse_qs(parsed_path.query)
            
            if path == '/':
                # 主页
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.end_headers()
                html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>NeoChat HTTP Server</title>
                </head>
                <body>
                    <h1>🚀 NeoChat HTTP 服务器</h1>
                    <p>服务器运行中</p>
                    <h2>API 端点:</h2>
                    <ul>
                        <li>POST /join?username=xxx - 加入聊天</li>
                        <li>POST /message - 发送消息 (JSON: {session_id, message})</li>
                        <li>GET /messages?since=0 - 获取消息</li>
                        <li>POST /leave - 离开聊天 (JSON: {session_id})</li>
                    </ul>
                </body>
                </html>
                """
                self.wfile.write(html.encode('utf-8'))
            
            elif path == '/messages':
                # 获取消息（同时作为心跳）
                since = int(query.get('since', ['0'])[0])
                session_id = query.get('session_id', [''])[0]
                
                # 验证会话并更新活动时间
                if session_id and not chat_server.update_activity(session_id):
                    self.send_json_response({
                        'error': '会话已失效，请重新登录',
                        'session_expired': True
                    }, 401)
                    return
                
                messages = chat_server.get_messages(since)
                self.send_json_response({
                    'success': True,
                    'messages': messages,
                    'total': len(chat_server.messages)
                })
            
            else:
                self.send_json_response({'error': '未找到端点'}, 404)
        
        def do_POST(self):
            """处理 POST 请求"""
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path
            query = urllib.parse.parse_qs(parsed_path.query)
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
            
            try:
                data = json.loads(body) if body else {}
            except:
                data = {}
            
            if path == '/join':
                # 加入聊天
                username = query.get('username', [''])[0] or data.get('username', 'Anonymous')
                session_id, username = chat_server.create_session(username)
                self.send_json_response({
                    'success': True,
                    'session_id': session_id,
                    'username': username,
                    'online_count': len(chat_server.clients)
                })
            
            elif path == '/message':
                # 发送消息
                session_id = data.get('session_id', '')
                message = data.get('message', '')
                
                if not session_id or not message:
                    self.send_json_response({'error': '缺少参数'}, 400)
                    return
                
                result = chat_server.send_message(session_id, message)
                self.send_json_response(result)
            
            elif path == '/leave':
                # 离开聊天
                session_id = data.get('session_id', '')
                if session_id:
                    chat_server.remove_session(session_id)
                    self.send_json_response({'success': True})
                else:
                    self.send_json_response({'error': '缺少会话ID'}, 400)
            
            else:
                self.send_json_response({'error': '未找到端点'}, 404)
    
    return ChatHTTPRequestHandler

def server_console(chat_server):
    """服务器控制台"""
    print()
    chat_server.log("服务器控制台已就绪", 'SYSTEM')
    chat_server.log("命令: 'stats'=统计, 'list'=在线用户, 'savelog'=保存日志, 'quit'=退出", 'SYSTEM')
    print("─" * 60)
    
    while chat_server.is_running:
        try:
            message = input(f"{Colors.GREEN}Server>{Colors.ENDC} ")
            message = message.strip()
            
            if not message:
                continue
            
            if message.lower() in ('quit', 'exit', 'stop'):
                chat_server.log("正在关闭服务器...", 'WARNING')
                chat_server.is_running = False
                sys.exit(0)
            
            elif message.lower() == 'stats':
                uptime = (datetime.now() - chat_server.start_time).total_seconds()
                print()
                chat_server.log(f"运行时长: {uptime:.0f} 秒", 'SYSTEM')
                chat_server.log(f"在线人数: {len(chat_server.clients)}", 'SYSTEM')
                chat_server.log(f"消息总数: {chat_server.message_count}", 'SYSTEM')
                print()
            
            elif message.lower() == 'list':
                if chat_server.clients:
                    print()
                    chat_server.log(f"在线用户 ({len(chat_server.clients)}):", 'SYSTEM')
                    for session_id, username in chat_server.clients.items():
                        print(f"  • {username} ({session_id})")
                    print()
                else:
                    chat_server.log("当前无在线用户", 'INFO')
            
            elif message.lower() == 'savelog':
                if chat_server._save_logs_to_file():
                    chat_server.log("日志已手动保存", 'SUCCESS')
                else:
                    chat_server.log("日志保存失败", 'ERROR')
            
            else:
                # 服务器广播消息
                with chat_server.lock:
                    broadcast_msg = {
                        'type': 'message',
                        'time': chat_server.get_time(),
                        'username': 'Server',
                        'message': message
                    }
                    chat_server.messages.append(broadcast_msg)
                    chat_server.log(f"已广播: {message}", 'SUCCESS')
                    chat_server.message_count += 1
                    
        except (EOFError, KeyboardInterrupt):
            chat_server.log("\n正在关闭服务器...", 'WARNING')
            chat_server.is_running = False
            sys.exit(0)
        except Exception as e:
            chat_server.log(f"控制台错误: {e}", 'ERROR')

def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    print(f"\n{Colors.YELLOW}[系统] 收到中断信号{Colors.ENDC}")
    sys.exit(0)

def main():
    """主函数"""
    signal.signal(signal.SIGINT, signal_handler)
    
    port = 9999
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"{Colors.RED}错误: 无效的端口号{Colors.ENDC}")
            sys.exit(1)
    
    chat_server = HTTPChatServer(port=port)
    chat_server.print_banner()
    
    handler = create_handler(chat_server)
    httpd = ThreadedHTTPServer((chat_server.host, chat_server.port), handler)
    
    chat_server.log("HTTP 服务器已就绪，等待连接...", 'SUCCESS')
    
    # 在单独线程中运行服务器
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    
    try:
        server_console(chat_server)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[服务器] 已关闭{Colors.ENDC}")
    finally:
        httpd.shutdown()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}再见！{Colors.ENDC}")
