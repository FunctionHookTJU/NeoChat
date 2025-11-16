"""
WebSocket to TCP 桥接服务器
允许浏览器客户端通过 WebSocket 连接到 TCP 服务器
支持配置文件或命令行参数指定目标服务器
"""

import asyncio
import websockets
import json
import logging
import sys
import os

class WSToTCPBridge:
    def __init__(self, ws_host='0.0.0.0', ws_port=8080, tcp_host='127.0.0.1', tcp_port=9999):
        self.ws_host = ws_host
        self.ws_port = ws_port
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        
        # 禁用日志噪音
        logging.getLogger('websockets.server').setLevel(logging.WARNING)
        logging.getLogger('websockets.protocol').setLevel(logging.WARNING)
    
    async def handle_websocket(self, websocket):
        """处理 WebSocket 客户端连接"""
        tcp_reader = None
        tcp_writer = None
        
        try:
            # 连接到 TCP 服务器
            print(f"[WebSocket] 新连接，正在连接到 TCP 服务器...")
            tcp_reader, tcp_writer = await asyncio.open_connection(self.tcp_host, self.tcp_port)
            print(f"[TCP] 已连接到 {self.tcp_host}:{self.tcp_port}")
            
            # 转发 WebSocket -> TCP 和 TCP -> WebSocket
            ws_to_tcp = asyncio.create_task(self.forward_ws_to_tcp(websocket, tcp_writer))
            tcp_to_ws = asyncio.create_task(self.forward_tcp_to_ws(tcp_reader, websocket))
            
            await asyncio.gather(ws_to_tcp, tcp_to_ws, return_exceptions=True)
            
        except Exception as e:
            print(f"[错误] 桥接错误: {e}")
        finally:
            if tcp_writer:
                tcp_writer.close()
                await tcp_writer.wait_closed()
            print(f"[断开] 连接已关闭")
    
    async def forward_ws_to_tcp(self, websocket, tcp_writer):
        """转发 WebSocket 消息到 TCP"""
        try:
            async for message in websocket:
                tcp_writer.write((message + '\n').encode('utf-8'))
                await tcp_writer.drain()
        except:
            pass
    
    async def forward_tcp_to_ws(self, tcp_reader, websocket):
        """转发 TCP 消息到 WebSocket"""
        try:
            while True:
                data = await tcp_reader.readline()
                if not data:
                    break
                await websocket.send(data.decode('utf-8').strip())
        except:
            pass
    
    async def start(self):
        """启动桥接服务器"""
        print("=" * 60)
        print("WebSocket-to-TCP 桥接服务器")
        print("=" * 60)
        print(f"WebSocket 监听: {self.ws_host}:{self.ws_port}")
        print(f"TCP 目标服务器: {self.tcp_host}:{self.tcp_port}")
        print("=" * 60)
        
        async with websockets.serve(self.handle_websocket, self.ws_host, self.ws_port):
            print("✓ 桥接服务器已启动")
            print("✓ 浏览器客户端请连接: ws://localhost:8080")
            print("=" * 60)
            await asyncio.Future()  # 永久运行

def load_config():
    """加载配置文件"""
    config_file = 'bridge_config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                print(f"✓ 已加载配置文件: {config_file}")
                return config
        except Exception as e:
            print(f"⚠ 配置文件加载失败: {e}")
    return {}

def save_default_config():
    """保存默认配置文件"""
    config = {
        "tcp_host": "127.0.0.1",
        "tcp_port": 9999,
        "ws_host": "0.0.0.0",
        "ws_port": 8080,
        "comment": "修改 tcp_host 和 tcp_port 以连接到内网穿透地址"
    }
    
    try:
        with open('bridge_config.json', 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        print("✓ 已创建默认配置文件: bridge_config.json")
        return True
    except Exception as e:
        print(f"✗ 创建配置文件失败: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("NeoChat 桥接服务器配置")
    print("=" * 60)
    
    # 检查是否有配置文件
    if not os.path.exists('bridge_config.json'):
        print("\n未找到配置文件，正在创建...")
        save_default_config()
        print("\n" + "=" * 60)
        print("配置向导")
        print("=" * 60)
        
        choice = input("\n选择 TCP 服务器类型:\n1. 本地服务器 (127.0.0.1:9999)\n2. 内网穿透服务器 (需要输入地址)\n请选择 [1/2]: ").strip()
        
        if choice == '2':
            tcp_host = input("请输入内网穿透地址 (例如: 111.161.121.11): ").strip()
            tcp_port = input("请输入端口 (例如: 57424): ").strip()
            
            try:
                tcp_port = int(tcp_port)
                config = {
                    "tcp_host": tcp_host,
                    "tcp_port": tcp_port,
                    "ws_host": "0.0.0.0",
                    "ws_port": 8080,
                    "comment": "桥接到内网穿透服务器"
                }
                with open('bridge_config.json', 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                print(f"✓ 配置已保存: {tcp_host}:{tcp_port}")
            except:
                print("✗ 配置无效，使用默认配置")
        else:
            print("✓ 使用本地服务器配置")
    
    # 加载配置
    config = load_config()
    
    # 命令行参数优先
    tcp_host = config.get('tcp_host', '127.0.0.1')
    tcp_port = config.get('tcp_port', 9999)
    ws_host = config.get('ws_host', '0.0.0.0')
    ws_port = config.get('ws_port', 8080)
    
    # 支持命令行参数
    if len(sys.argv) >= 3:
        tcp_host = sys.argv[1]
        try:
            tcp_port = int(sys.argv[2])
            print(f"✓ 使用命令行参数: {tcp_host}:{tcp_port}")
        except:
            print("✗ 命令行参数无效，使用配置文件")
    
    bridge = WSToTCPBridge(
        ws_host=ws_host,
        ws_port=ws_port,
        tcp_host=tcp_host,
        tcp_port=tcp_port
    )
    
    try:
        asyncio.run(bridge.start())
    except KeyboardInterrupt:
        print("\n桥接服务器已关闭")
