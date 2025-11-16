"""
NeoChat TCP 客户端（命令行版本）
用于测试 TCP 服务器
"""

import asyncio
import json
import sys

class TCPChatClient:
    def __init__(self, host, port, username):
        self.host = host
        self.port = port
        self.username = username
        self.reader = None
        self.writer = None
        self.running = True
    
    async def connect(self):
        """连接到服务器"""
        try:
            print(f"正在连接到 {self.host}:{self.port}...")
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            print(f"✓ 已连接到服务器")
            
            # 发送用户名
            self.writer.write((self.username + '\n').encode('utf-8'))
            await self.writer.drain()
            print(f"✓ 已发送用户名: {self.username}")
            
            return True
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    async def receive_messages(self):
        """接收服务器消息"""
        try:
            while self.running:
                data = await self.reader.readline()
                if not data:
                    print("\n✗ 服务器断开连接")
                    self.running = False
                    break
                
                try:
                    msg = json.loads(data.decode('utf-8'))
                    
                    if msg['type'] == 'system':
                        print(f"\n[系统 {msg['time']}] {msg['message']}")
                    elif msg['type'] == 'message':
                        print(f"\n[{msg['time']}] {msg['username']}: {msg['message']}")
                    
                    # 重新显示输入提示
                    print(f"{self.username}> ", end='', flush=True)
                    
                except json.JSONDecodeError:
                    pass
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"\n✗ 接收消息错误: {e}")
            self.running = False
    
    async def send_messages(self):
        """发送消息"""
        loop = asyncio.get_event_loop()
        
        try:
            while self.running:
                message = await loop.run_in_executor(None, input, f"{self.username}> ")
                message = message.strip()
                
                if not message:
                    continue
                
                if message.lower() in ('quit', 'exit'):
                    print("正在退出...")
                    self.running = False
                    break
                
                self.writer.write((message + '\n').encode('utf-8'))
                await self.writer.drain()
                
        except EOFError:
            self.running = False
        except Exception as e:
            print(f"\n✗ 发送消息错误: {e}")
            self.running = False
    
    async def run(self):
        """运行客户端"""
        if not await self.connect():
            return
        
        print("\n" + "=" * 60)
        print("已加入聊天室！输入消息开始聊天，输入 'quit' 退出")
        print("支持命令: /help, /online, /ping, /stats")
        print("=" * 60 + "\n")
        
        # 同时运行接收和发送任务
        receive_task = asyncio.create_task(self.receive_messages())
        send_task = asyncio.create_task(self.send_messages())
        
        await asyncio.gather(receive_task, send_task, return_exceptions=True)
        
        # 关闭连接
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        
        print("\n已断开连接")

async def main():
    """主函数"""
    print("=" * 60)
    print("      NeoChat TCP 客户端")
    print("=" * 60)
    
    # 获取连接信息
    host = input("服务器地址 (例如: localhost 或 111.161.121.11): ").strip() or "localhost"
    port = input("服务器端口 (默认: 9999): ").strip() or "9999"
    username = input("你的用户名: ").strip()
    
    if not username:
        print("✗ 用户名不能为空")
        return
    
    try:
        port = int(port)
    except ValueError:
        print("✗ 端口号无效")
        return
    
    client = TCPChatClient(host, port, username)
    await client.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n再见！")
