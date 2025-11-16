@echo off
chcp 65001 > nul
echo ==========================================
echo NeoChat 完整服务启动
echo ==========================================
echo.
echo 正在启动服务...
echo.

:: 启动 TCP 服务器
start "NeoChat TCP 服务器" cmd /k "echo [TCP 服务器 - 端口 9999] && python server_tcp.py"

:: 等待1秒
timeout /t 1 /nobreak > nul

:: 启动 WebSocket 桥接服务器
start "NeoChat 桥接服务器" cmd /k "echo [桥接服务器 - 端口 8080] && python bridge_server.py"

echo.
echo ==========================================
echo ✓ 服务启动完成！
echo ==========================================
echo.
echo [1] TCP 服务器     : 端口 9999
echo [2] 桥接服务器     : 端口 8080
echo.
echo 使用方法:
echo 1. 浏览器打开 client.html
echo 2. 选择 "桥接(8080)" 连接
echo 3. 或使用 Python: python client_tcp.py
echo.
echo 按任意键打开浏览器客户端...
pause > nul
start client.html
