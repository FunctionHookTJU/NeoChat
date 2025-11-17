#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NeoChat GUI 客户端
基于 Tkinter 的图形界面 TCP 聊天客户端
"""

import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import json
from datetime import datetime


def draw_rounded_rect(canvas, x1, y1, x2, y2, radius=15, **kwargs):
    """在 Canvas 上绘制圆角矩形"""
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    kwargs.setdefault("outline", "")
    canvas.create_rectangle(x1 + radius, y1, x2 - radius, y2, **kwargs)
    canvas.create_rectangle(x1, y1 + radius, x2, y2 - radius, **kwargs)
    canvas.create_oval(x1, y1, x1 + 2 * radius, y1 + 2 * radius, **kwargs)
    canvas.create_oval(x2 - 2 * radius, y1, x2, y1 + 2 * radius, **kwargs)
    canvas.create_oval(x1, y2 - 2 * radius, x1 + 2 * radius, y2, **kwargs)
    canvas.create_oval(x2 - 2 * radius, y2 - 2 * radius, x2, y2, **kwargs)


class RoundedButton(tk.Canvas):
    """自定义圆角按钮"""

    def __init__(
        self,
        master,
        text,
        command,
        width=120,
        height=40,
        radius=18,
        bg="#667eea",
        fg="white",
        hover_bg="#5568d3",
        disabled_bg="#bfc5f2",
        font=("Microsoft YaHei", 11, "bold"),
    ):
        master_bg = master.cget("bg") if "bg" in master.keys() else "white"
        super().__init__(master, width=width, height=height, bg=master_bg, highlightthickness=0, bd=0)
        self.config(cursor="hand2")
        self.command = command
        self.text = text
        self.font = font
        self.radius = radius
        self.normal_bg = bg
        self.hover_bg = hover_bg
        self.disabled_bg = disabled_bg
        self.current_bg = bg
        self.fg = fg
        self.state = "normal"
        self._draw()
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw(self):
        self.delete("all")
        width = int(float(self["width"]))
        height = int(float(self["height"]))
        draw_rounded_rect(self, 0, 0, width, height, self.radius, fill=self.current_bg)
        self.create_text(
            width / 2,
            height / 2,
            text=self.text,
            font=self.font,
            fill=self.fg,
        )

    def _on_click(self, event):
        if self.state == "normal" and callable(self.command):
            self.command()

    def _on_enter(self, _):
        if self.state == "normal":
            self.current_bg = self.hover_bg
            self._draw()

    def _on_leave(self, _):
        if self.state == "normal":
            self.current_bg = self.normal_bg
            self._draw()

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_state(self, state):
        if state == tk.DISABLED:
            self.state = "disabled"
            self.current_bg = self.disabled_bg
        else:
            self.state = "normal"
            self.current_bg = self.normal_bg
        self._draw()

class ChatClient:
    def __init__(self):
        self.socket = None
        self.connected = False
        self.username = ""
        self.server_address = ""
        self.receive_thread = None
        
    def connect(self, host, port, username):
        """连接到服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)  # 设置5秒超时
            self.socket.connect((host, port))
            
            # 发送用户名
            self.socket.send(f"{username}\n".encode('utf-8'))
            self.username = username
            self.connected = True
            self.socket.settimeout(None)  # 取消超时限制
            return True, "连接成功"
        except socket.timeout:
            return False, "连接超时"
        except ConnectionRefusedError:
            return False, "连接被拒绝，服务器未启动或端口错误"
        except Exception as e:
            return False, str(e)
    
    def disconnect(self):
        """断开连接"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def send_message(self, message):
        """发送消息"""
        if self.connected and self.socket:
            try:
                self.socket.send(f"{message}\n".encode('utf-8'))
                return True
            except:
                self.connected = False
                return False
        return False
    
    def receive_messages(self, callback):
        """接收消息的线程函数"""
        buffer = ""
        while self.connected:
            try:
                data = self.socket.recv(4096).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        callback(line.strip())
                        
            except Exception as e:
                if self.connected:
                    callback(json.dumps({
                        'type': 'system',
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'message': f'连接错误: {e}'
                    }))
                break
        
        self.connected = False
        callback(json.dumps({
            'type': 'system',
            'time': datetime.now().strftime('%H:%M:%S'),
            'message': '已断开与服务器的连接'
        }))


class LoginWindow:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("NeoChat - 登录")
        self.window.geometry("460x360")
        self.window.resizable(False, False)
        
        # 居中窗口
        self.center_window()
        
        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        self.client = None
        self.chat_window = None
        
        self.create_widgets()
        
    def center_window(self):
        """窗口居中"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        """创建登录界面组件"""
        # 标题
        title_frame = tk.Frame(self.window, bg="#667eea", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="🚀 NeoChat",
            font=("Arial", 20, "bold"),
            bg="#667eea",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # 主容器
        main_frame = tk.Frame(self.window, padx=30, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 用户名输入
        username_label = tk.Label(
            main_frame,
            text="用户名:",
            font=("Microsoft YaHei", 10)
        )
        username_label.pack(anchor=tk.W, pady=(10, 5))
        
        self.username_entry = ttk.Entry(main_frame, font=("Microsoft YaHei", 10))
        self.username_entry.pack(fill=tk.X, pady=(0, 15))
        self.username_entry.insert(0, "User_" + str(hash(datetime.now()) % 1000))
        
        # 服务器地址输入
        server_label = tk.Label(
            main_frame,
            text="服务器地址:",
            font=("Microsoft YaHei", 10)
        )
        server_label.pack(anchor=tk.W, pady=(0, 5))
        
        server_frame = tk.Frame(main_frame)
        server_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.host_entry = ttk.Entry(server_frame, font=("Microsoft YaHei", 10), width=20)
        self.host_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.host_entry.insert(0, "122.246.0.254")
        
        colon_label = tk.Label(server_frame, text=":", font=("Microsoft YaHei", 10))
        colon_label.pack(side=tk.LEFT, padx=5)
        
        self.port_entry = ttk.Entry(server_frame, font=("Microsoft YaHei", 10), width=8)
        self.port_entry.pack(side=tk.LEFT)
        self.port_entry.insert(0, "17201")
        
        # 连接按钮（圆角）
        btn_container = tk.Frame(main_frame, bg="white")
        btn_container.pack(fill=tk.X, pady=(10, 0))
        self.connect_btn = RoundedButton(
            btn_container,
            text="连接",
            command=self.connect_to_server,
            width=300,
            height=46,
            radius=22,
        )
        self.connect_btn.pack(pady=5)
        
        # 绑定回车键
        self.username_entry.bind('<Return>', lambda e: self.connect_to_server())
        self.host_entry.bind('<Return>', lambda e: self.connect_to_server())
        self.port_entry.bind('<Return>', lambda e: self.connect_to_server())
        
    def connect_to_server(self):
        """连接到服务器"""
        username = self.username_entry.get().strip()
        host = self.host_entry.get().strip()
        port_str = self.port_entry.get().strip()
        
        # 验证输入
        if not username:
            messagebox.showerror("错误", "请输入用户名！")
            return
        
        if not host:
            messagebox.showerror("错误", "请输入服务器地址！")
            return
        
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError()
        except ValueError:
            messagebox.showerror("错误", "端口号必须是 1-65535 之间的数字！")
            return
        
        # 禁用连接按钮
        self.connect_btn.set_state(tk.DISABLED)
        self.connect_btn.set_text("连接中...")
        self.window.update()
        
        # 创建客户端并连接
        self.client = ChatClient()
        result = self.client.connect(host, port, username)
        
        if isinstance(result, tuple) and result[0] is True:
            # 连接成功，打开聊天窗口
            self.window.withdraw()  # 隐藏登录窗口
            self.chat_window = ChatWindow(self.client, self.window)
            self.chat_window.run()
        else:
            # 连接失败
            error_msg = result[1] if isinstance(result, tuple) else str(result)
            messagebox.showerror("连接失败", f"无法连接到服务器:\n{error_msg}")
            self.connect_btn.set_state(tk.NORMAL)
            self.connect_btn.set_text("连接")
    
    def run(self):
        """运行登录窗口"""
        self.window.mainloop()


class ChatWindow:
    def __init__(self, client, login_window):
        self.client = client
        self.login_window = login_window
        
        self.window = tk.Toplevel()
        self.window.title(f"NeoChat - {client.username}")
        self.window.geometry("880x720")
        
        # 居中窗口
        self.center_window()
        
        # 设置关闭事件
        self.window.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.create_widgets()
        
        # 启动接收消息线程
        self.client.receive_thread = threading.Thread(
            target=self.client.receive_messages,
            args=(self.on_message_received,),
            daemon=True
        )
        self.client.receive_thread.start()
        
    def center_window(self):
        """窗口居中"""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_widgets(self):
        """创建聊天界面组件"""
        # 顶部标题栏
        header_frame = tk.Frame(self.window, bg="#667eea", height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        self.back_btn = RoundedButton(
            header_frame,
            text="返回",
            command=self.go_back,
            width=78,
            height=34,
            radius=17,
            bg="#ffffff",
            fg="#3847a6",
            hover_bg="#e0e7ff",
            font=("Microsoft YaHei", 10, "bold"),
        )
        self.back_btn.pack(side=tk.LEFT, padx=(15, 5))

        title_label = tk.Label(
            header_frame,
            text=f"NeoChat 聊天室",
            font=("Microsoft YaHei", 14, "bold"),
            bg="#667eea",
            fg="white"
        )
        title_label.pack(side=tk.LEFT, padx=10, pady=10)
        
        user_label = tk.Label(
            header_frame,
            text=f"👤 {self.client.username}",
            font=("Microsoft YaHei", 10),
            bg="#667eea",
            fg="white"
        )
        user_label.pack(side=tk.RIGHT, padx=20, pady=10)
        
        # 消息显示区域（使用Canvas实现气泡效果）
        message_frame = tk.Frame(self.window, bg="#f0f2f5")
        message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 创建Canvas和滚动条
        canvas_frame = tk.Frame(message_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.message_canvas = tk.Canvas(
            canvas_frame,
            bg="#f0f2f5",
            highlightthickness=0
        )
        scrollbar = tk.Scrollbar(canvas_frame, command=self.message_canvas.yview)
        self.scrollable_frame = tk.Frame(self.message_canvas, bg="#f0f2f5")
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.message_canvas.configure(scrollregion=self.message_canvas.bbox("all"))
        )
        
        self.canvas_window = self.message_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.message_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.message_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定Canvas大小变化
        self.message_canvas.bind('<Configure>', self._on_canvas_configure)
        
        # 输入区域
        input_frame = tk.Frame(self.window, bg="white", height=100)
        input_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        input_frame.pack_propagate(False)
        
        # 输入框
        input_container = tk.Frame(input_frame, bg="white")
        input_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.message_entry = tk.Text(
            input_container,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            height=3,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=1,
            highlightbackground="#cccccc",
            highlightcolor="#667eea"
        )
        self.message_entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # 发送按钮（圆角）
        self.send_btn = RoundedButton(
            input_container,
            text="发送",
            command=self.send_message,
            width=90,
            height=38,
            radius=17,
        )
        self.send_btn.pack(side=tk.RIGHT, pady=4)
        
        # 绑定键盘事件：Enter发送消息，Shift+Enter换行
        def on_enter_key(event):
            if event.state & 0x1:  # Shift键被按下
                return  # 允许默认的换行行为
            else:
                self.send_message()
                return "break"  # 阻止默认的换行行为
        
        self.message_entry.bind('<Return>', on_enter_key)
        
        # 添加欢迎消息
        self.add_system_message("欢迎来到 NeoChat！")
        self.add_system_message(f"已连接到服务器，用户名: {self.client.username}")
        self.add_system_message("提示: 按 Enter 发送消息，Shift+Enter 换行")
        
    def add_system_message(self, message):
        """添加系统消息（居中显示）"""
        time_str = datetime.now().strftime('%H:%M:%S')
        
        # 创建容器
        msg_frame = tk.Frame(self.scrollable_frame, bg="#f0f2f5")
        msg_frame.pack(fill=tk.X, pady=5)
        
        # 系统消息居中显示
        content_frame = tk.Frame(msg_frame, bg="#f0f2f5")
        content_frame.pack()
        
        # 时间标签
        time_label = tk.Label(
            content_frame,
            text=time_str,
            font=("Arial", 9),
            fg="#999999",
            bg="#f0f2f5"
        )
        time_label.pack()
        
        # 系统消息气泡
        bubble = self._create_bubble_canvas(
            content_frame,
            message,
            "#e0e0e0",
            "#555555",
            font=("Microsoft YaHei", 10),
            max_width=420,
        )
        bubble.pack(pady=2)
        
        self._scroll_to_bottom()
    
    def add_user_message(self, username, message, time_str):
        """添加用户消息（QQ风格气泡）"""
        is_self = (username == self.client.username)
        
        # 创建消息容器
        msg_frame = tk.Frame(self.scrollable_frame, bg="#f0f2f5")
        msg_frame.pack(fill=tk.X, pady=8, padx=10)
        
        if is_self:
            # 自己的消息靠右
            content_frame = tk.Frame(msg_frame, bg="#f0f2f5")
            content_frame.pack(side=tk.RIGHT)
            
            # 用户名和时间（右对齐）
            info_frame = tk.Frame(content_frame, bg="#f0f2f5")
            info_frame.pack(side=tk.TOP, anchor="e", pady=(0, 3))
            
            time_label = tk.Label(
                info_frame,
                text=time_str,
                font=("Arial", 9),
                fg="#999999",
                bg="#f0f2f5"
            )
            time_label.pack(side=tk.RIGHT, padx=5)
            
            name_label = tk.Label(
                info_frame,
                text=username,
                font=("Microsoft YaHei", 10, "bold"),
                fg="#10b981",
                bg="#f0f2f5"
            )
            name_label.pack(side=tk.RIGHT)
            
            # 消息气泡（绿色）
            bubble = self._create_bubble_canvas(
                content_frame,
                message,
                "#95ec69",
                "white",
                font=("Microsoft YaHei", 11),
                max_width=360,
            )
            bubble.pack(side=tk.TOP, anchor="e")
            
        else:
            # 别人的消息靠左
            content_frame = tk.Frame(msg_frame, bg="#f0f2f5")
            content_frame.pack(side=tk.LEFT)
            
            # 用户名和时间（左对齐）
            info_frame = tk.Frame(content_frame, bg="#f0f2f5")
            info_frame.pack(side=tk.TOP, anchor="w", pady=(0, 3))
            
            name_label = tk.Label(
                info_frame,
                text=username,
                font=("Microsoft YaHei", 10, "bold"),
                fg="#667eea",
                bg="#f0f2f5"
            )
            name_label.pack(side=tk.LEFT)
            
            time_label = tk.Label(
                info_frame,
                text=time_str,
                font=("Arial", 9),
                fg="#999999",
                bg="#f0f2f5"
            )
            time_label.pack(side=tk.LEFT, padx=5)
            
            # 消息气泡（白色）
            bubble = self._create_bubble_canvas(
                content_frame,
                message,
                "white",
                "#333333",
                font=("Microsoft YaHei", 11),
                max_width=360,
            )
            bubble.pack(side=tk.TOP, anchor="w")
        
        self._scroll_to_bottom()
    
    def _on_canvas_configure(self, event):
        """Canvas大小改变时调整窗口宽度"""
        self.message_canvas.itemconfig(self.canvas_window, width=event.width)

    def _create_bubble_canvas(self, parent, text, bg_color, fg_color, font, max_width=360):
        """创建带圆角背景的消息气泡"""
        bubble_canvas = tk.Canvas(parent, bg="#f0f2f5", highlightthickness=0, bd=0)
        padding_x = 16
        padding_y = 10
        temp_id = bubble_canvas.create_text(0, 0, text=text, font=font, fill=fg_color, width=max_width, anchor="nw")
        bbox = bubble_canvas.bbox(temp_id) if temp_id else (0, 0, 0, 0)
        bubble_canvas.delete(temp_id)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        width = int(max(text_width + padding_x * 2, 80))
        height = int(max(text_height + padding_y * 2, 36))
        bubble_canvas.config(width=width, height=height)
        draw_rounded_rect(bubble_canvas, 0, 0, width, height, radius=18, fill=bg_color)
        bubble_canvas.create_text(
            padding_x,
            padding_y,
            text=text,
            font=font,
            fill=fg_color,
            width=width - padding_x * 2,
            anchor="nw",
        )
        return bubble_canvas
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        self.message_canvas.update_idletasks()
        self.message_canvas.yview_moveto(1.0)
    
    def on_message_received(self, message_json):
        """接收到消息的回调"""
        try:
            msg = json.loads(message_json)
            
            if msg.get('type') == 'system':
                self.window.after(0, self.add_system_message, msg.get('message', ''))
            elif msg.get('type') == 'message':
                # 不显示自己发送的消息（已经在发送时显示了）
                if msg.get('username') != self.client.username:
                    self.window.after(
                        0,
                        self.add_user_message,
                        msg.get('username', 'Unknown'),
                        msg.get('message', ''),
                        msg.get('time', datetime.now().strftime('%H:%M:%S'))
                    )
        except json.JSONDecodeError:
            # 如果不是 JSON 格式，作为普通消息显示
            self.window.after(0, self.add_system_message, message_json)
    
    def send_message(self):
        """发送消息"""
        message = self.message_entry.get("1.0", tk.END).strip()
        
        if not message:
            return
        
        if not self.client.connected:
            messagebox.showerror("错误", "未连接到服务器！")
            return
        
        # 发送消息
        if self.client.send_message(message):
            # 立即显示自己发送的消息
            time_str = datetime.now().strftime('%H:%M:%S')
            self.add_user_message(self.client.username, message, time_str)
            
            # 清空输入框
            self.message_entry.delete("1.0", tk.END)
            self.message_entry.focus()
        else:
            messagebox.showerror("错误", "发送消息失败！")
            self.add_system_message("发送失败: 连接已断开")

    def go_back(self):
        """返回登录界面"""
        if messagebox.askyesno("返回登录", "确定要返回登录界面重新连接吗？"):
            self.client.disconnect()
            self.window.destroy()
            self.login_window.deiconify()
            self.login_window.connect_btn.set_state(tk.NORMAL)
            self.login_window.connect_btn.set_text("连接")
            self.login_window.client = None
            self.login_window.host_entry.focus_set()
    
    def on_closing(self):
        """关闭窗口"""
        if messagebox.askokcancel("退出", "确定要退出聊天吗？"):
            self.client.disconnect()
            self.window.destroy()
            self.login_window.destroy()
    
    def run(self):
        """运行聊天窗口"""
        self.window.mainloop()


def main():
    """主函数"""
    app = LoginWindow()
    app.run()


if __name__ == '__main__':
    main()
