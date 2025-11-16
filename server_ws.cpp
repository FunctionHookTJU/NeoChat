#include <websocketpp/config/asio_no_tls.hpp>
#include <websocketpp/server.hpp>
#include <iostream>
#include <set>
#include <string>
#include <mutex>
#include <map>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <thread>
#include <windows.h>

typedef websocketpp::server<websocketpp::config::asio> server;
typedef std::set<websocketpp::connection_hdl, std::owner_less<websocketpp::connection_hdl>> con_list;

class ChatServer {
public:
    ChatServer() {
        // 设置控制台为 UTF-8 编码
        SetConsoleOutputCP(65001);
        
        // 初始化服务器
        m_server.init_asio();
        m_server.set_reuse_addr(true);
        
        // 设置回调函数
        m_server.set_open_handler(bind(&ChatServer::on_open, this, std::placeholders::_1));
        m_server.set_close_handler(bind(&ChatServer::on_close, this, std::placeholders::_1));
        m_server.set_message_handler(bind(&ChatServer::on_message, this, std::placeholders::_1, std::placeholders::_2));
        m_server.set_fail_handler(bind(&ChatServer::on_fail, this, std::placeholders::_1));
        
        // 关闭访问日志和错误日志（减少噪音）
        m_server.clear_access_channels(websocketpp::log::alevel::all);
        m_server.clear_error_channels(websocketpp::log::elevel::all);
    }
    
    void run(uint16_t port) {
        try {
            // 监听端口
            m_server.listen(port);
            m_server.start_accept();
            
            std::cout << "==================================" << std::endl;
            std::cout << "   NeoChat WebSocket 服务器 (C++)" << std::endl;
            std::cout << "==================================" << std::endl;
            std::cout << "[服务器] 已启动在端口: " << port << std::endl;
            std::cout << "[服务器] 等待客户端连接..." << std::endl;
            std::cout << "[服务器] 输入消息并按回车发送 (署名为 Server)" << std::endl;
            std::cout << "==================================" << std::endl;
            
            // 启动输入线程
            std::thread input_thread(&ChatServer::input_loop, this);
            input_thread.detach();
            
            // 运行事件循环
            m_server.run();
        } catch (const std::exception& e) {
            std::cerr << "[错误] 服务器启动失败: " << e.what() << std::endl;
        }
    }
    
private:
    // 获取当前时间字符串
    std::string get_time() {
        auto now = std::time(nullptr);
        auto tm = *std::localtime(&now);
        std::ostringstream oss;
        oss << std::put_time(&tm, "%H:%M:%S");
        return oss.str();
    }
    
    // 连接打开
    void on_open(websocketpp::connection_hdl hdl) {
        std::lock_guard<std::mutex> guard(m_mutex);
        m_connections.insert(hdl);
        
        auto con = m_server.get_con_from_hdl(hdl);
        std::string remote = con->get_remote_endpoint();
        std::cout << "[服务器] 新连接来自: " << remote << std::endl;
    }
    
    // 连接关闭
    void on_close(websocketpp::connection_hdl hdl) {
        std::lock_guard<std::mutex> guard(m_mutex);
        
        // 获取用户名
        auto it = m_usernames.find(hdl);
        if (it != m_usernames.end()) {
            std::string username = it->second;
            std::cout << "[服务器] " << username << " 离开聊天室" << std::endl;
            
            // 广播离开消息
            std::string leave_msg = "[系统 " + get_time() + "] " + username + " 离开了聊天室";
            broadcast(leave_msg, hdl);
            
            m_usernames.erase(it);
        }
        
        m_connections.erase(hdl);
    }
    
    // 连接失败（静默处理 frp 健康检查）
    void on_fail(websocketpp::connection_hdl hdl) {
        // 静默处理连接失败，避免 frp 健康检查产生噪音
    }
    
    // 接收消息
    void on_message(websocketpp::connection_hdl hdl, server::message_ptr msg) {
        std::lock_guard<std::mutex> guard(m_mutex);
        
        std::string payload = msg->get_payload();
        
        // 检查是否是用户名（第一条消息）
        auto it = m_usernames.find(hdl);
        if (it == m_usernames.end()) {
            // 第一条消息是用户名
            m_usernames[hdl] = payload;
            std::cout << "[服务器] " << payload << " 加入聊天室" << std::endl;
            
            // 广播加入消息
            std::string join_msg = "[系统 " + get_time() + "] " + payload + " 加入了聊天室";
            broadcast(join_msg, hdl);
            
            // 发送欢迎消息
            std::string welcome_msg = "[系统 " + get_time() + "] 欢迎来到 NeoChat！当前在线人数: " + 
                                      std::to_string(m_usernames.size());
            try {
                m_server.send(hdl, welcome_msg, websocketpp::frame::opcode::text);
            } catch (const std::exception& e) {
                // 忽略发送错误
            }
        } else {
            // 正常聊天消息
            std::string username = it->second;
            std::cout << "[消息] " << username << ": " << payload << std::endl;
            
            // 广播消息
            std::string broadcast_msg = "[" + get_time() + "] " + username + ": " + payload;
            broadcast(broadcast_msg, hdl);
        }
    }
    
    // 广播消息（排除发送者）
    void broadcast(const std::string& msg, websocketpp::connection_hdl exclude) {
        for (auto it : m_connections) {
            if (!it.owner_before(exclude) && !exclude.owner_before(it)) {
                continue; // 跳过发送者
            }
            try {
                m_server.send(it, msg, websocketpp::frame::opcode::text);
            } catch (const std::exception& e) {
                // 忽略发送错误
            }
        }
    }
    
    // 广播消息（发送给所有人）
    void broadcast_all(const std::string& msg) {
        std::lock_guard<std::mutex> guard(m_mutex);
        for (auto it : m_connections) {
            try {
                m_server.send(it, msg, websocketpp::frame::opcode::text);
            } catch (const std::exception& e) {
                // 忽略发送错误
            }
        }
    }
    
    // 输入循环（服务器消息）
    void input_loop() {
        std::string input;
        while (true) {
            std::getline(std::cin, input);
            if (!input.empty()) {
                std::string server_msg = "[" + get_time() + "] Server: " + input;
                broadcast_all(server_msg);
                std::cout << "[已发送] Server: " << input << std::endl;
            }
        }
    }
    
    server m_server;
    con_list m_connections;
    std::map<websocketpp::connection_hdl, std::string, std::owner_less<websocketpp::connection_hdl>> m_usernames;
    std::mutex m_mutex;
};

int main() {
    ChatServer server;
    server.run(9999);
    return 0;
}
