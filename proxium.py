#!/usr/bin/env python3
import socket
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
import tkinter.scrolledtext as st
import time

class Proxium:
    def __init__(self, local_ip, local_port, remote_ip, remote_port, log_callback, packet_callback=None):
        self.local_ip = local_ip
        self.local_port = local_port
        self.remote_ip = remote_ip
        self.remote_port = remote_port
        self.log_callback = log_callback
        self.packet_callback = packet_callback
        self.stop_event = threading.Event()
        self.tcp_server_socket = None
        self.udp_socket = None
        self.tcp_thread = None
        self.udp_thread = None

    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def notify_packet(self, direction, data, src_addr=None, dst_addr=None):
        if self.packet_callback:
            info = {
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'direction': direction,
                'length': len(data),
                'src_addr': src_addr,
                'dst_addr': dst_addr,
                'data': data,
            }
            self.packet_callback(info)

    def start(self):
        self.stop_event.clear()
        self.tcp_thread = threading.Thread(target=self.start_tcp_forwarding, daemon=True)
        self.tcp_thread.start()
        self.udp_thread = threading.Thread(target=self.start_udp_forwarding, daemon=True)
        self.udp_thread.start()
        self.log("端口转发服务已启动。")

    def stop(self):
        self.stop_event.set()
        if self.tcp_server_socket:
            try:
                self.tcp_server_socket.close()
            except Exception as e:
                self.log("关闭TCP服务器出错：" + str(e))
        if self.udp_socket:
            try:
                self.udp_socket.close()
            except Exception as e:
                self.log("关闭UDP服务器出错：" + str(e))
        self.log("停止指令已发送，正在退出转发线程...")

    def forward_data(self, source, destination, direction, src_addr=None, dst_addr=None):
        source.settimeout(1)
        try:
            while not self.stop_event.is_set():
                try:
                    data = source.recv(4096)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log("数据接收出错：" + str(e))
                    break
                if not data:
                    break
                self.notify_packet(direction, data, src_addr, dst_addr)
                try:
                    destination.sendall(data)
                except Exception as e:
                    self.log("数据发送出错：" + str(e))
                    break
        except Exception as e:
            self.log("数据转发出错：" + str(e))

    def handle_tcp_client(self, client_sock, addr):
        self.log(f"[TCP] 收到来自 {addr} 的连接")
        try:
            remote_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            remote_sock.settimeout(1)
            remote_sock.connect((self.remote_ip, self.remote_port))
        except Exception as e:
            self.log("连接远端TCP服务器失败：" + str(e))
            client_sock.close()
            return

        client_sock.settimeout(1)
        t1 = threading.Thread(target=self.forward_data, args=(client_sock, remote_sock, '客户端->远端', addr, (self.remote_ip, self.remote_port)), daemon=True)
        t2 = threading.Thread(target=self.forward_data, args=(remote_sock, client_sock, '远端->客户端', (self.remote_ip, self.remote_port), addr), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        try:
            client_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            remote_sock.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        client_sock.close()
        remote_sock.close()
        self.log(f"[TCP] 与 {addr} 的连接已关闭。")

    def start_tcp_forwarding(self):
        self.tcp_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.tcp_server_socket.bind((self.local_ip, self.local_port))
            self.tcp_server_socket.listen(5)
            self.tcp_server_socket.settimeout(1)
            self.log(f"[TCP] 正在监听 {self.local_ip}:{self.local_port}，转发到 {self.remote_ip}:{self.remote_port}")
        except Exception as e:
            self.log("TCP服务器启动错误：" + str(e))
            return

        while not self.stop_event.is_set():
            try:
                client_sock, addr = self.tcp_server_socket.accept()
                threading.Thread(target=self.handle_tcp_client, args=(client_sock, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                self.log("TCP接收连接时出错：" + str(e))
                break
        self.log("[TCP] 转发线程退出。")

    def start_udp_forwarding(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.udp_socket.bind((self.local_ip, self.local_port))
            self.udp_socket.settimeout(1)
            self.log(f"[UDP] 正在监听 {self.local_ip}:{self.local_port}，转发到 {self.remote_ip}:{self.remote_port}")
        except Exception as e:
            self.log("UDP服务器启动错误：" + str(e))
            return

        client_addr = None
        while not self.stop_event.is_set():
            try:
                data, addr = self.udp_socket.recvfrom(65535)
                if addr == (self.remote_ip, self.remote_port):
                    if client_addr:
                        self.udp_socket.sendto(data, client_addr)
                        self.notify_packet('远端->客户端', data, addr, client_addr)
                        self.log(f"[UDP] 将远端数据转发给客户端 {client_addr}")
                else:
                    client_addr = addr
                    self.udp_socket.sendto(data, (self.remote_ip, self.remote_port))
                    self.notify_packet('客户端->远端', data, addr, (self.remote_ip, self.remote_port))
                    self.log(f"[UDP] 将客户端 {client_addr} 数据转发至远端")
            except socket.timeout:
                continue
            except Exception as e:
                self.log("UDP转发出错：" + str(e))
                break
        self.log("[UDP] 转发线程退出。")


class ProxiumGUI:
    def __init__(self, master):
        self.master = master
        master.title("Proxium - 端口转发与抓包工具")
        master.geometry("800x600")
        master.minsize(600, 400)

        self.style = ttk.Style()
        self.style.theme_use('clam')

        self.notebook = ttk.Notebook(master)
        self.notebook.pack(expand=True, fill='both', padx=5, pady=5)

        self.forward_frame = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.notebook.add(self.forward_frame, text="端口转发")

        self.capture_frame = ttk.Frame(self.notebook, padding="10 10 10 10")
        self.notebook.add(self.capture_frame, text="抓包")

        self.create_forward_tab()
        self.create_capture_tab()

        self.forwarder = None
        self.packets = []
        self.max_packets = 500

    def create_forward_tab(self):
        ttk.Label(self.forward_frame, text="本地IP:").grid(column=0, row=0, sticky=tk.W, pady=2)
        self.local_ip = tk.StringVar(value="127.0.0.1")
        ttk.Entry(self.forward_frame, width=20, textvariable=self.local_ip).grid(column=1, row=0, sticky="we", pady=2)

        ttk.Label(self.forward_frame, text="本地端口:").grid(column=2, row=0, sticky=tk.W, pady=2)
        self.local_port = tk.StringVar(value="11434")
        ttk.Entry(self.forward_frame, width=10, textvariable=self.local_port).grid(column=3, row=0, sticky="we", pady=2)

        ttk.Label(self.forward_frame, text="目标IP:").grid(column=0, row=1, sticky=tk.W, pady=2)
        self.remote_ip = tk.StringVar(value="192.168.6.99")
        ttk.Entry(self.forward_frame, width=20, textvariable=self.remote_ip).grid(column=1, row=1, sticky="we", pady=2)

        ttk.Label(self.forward_frame, text="目标端口:").grid(column=2, row=1, sticky=tk.W, pady=2)
        self.remote_port = tk.StringVar(value="11434")
        ttk.Entry(self.forward_frame, width=10, textvariable=self.remote_port).grid(column=3, row=1, sticky="we", pady=2)

        self.forward_frame.columnconfigure(1, weight=1)
        self.forward_frame.columnconfigure(3, weight=1)

        self.start_button = ttk.Button(self.forward_frame, text="启动", command=self.start_forwarding)
        self.start_button.grid(column=0, row=2, columnspan=2, sticky="we", pady=5)

        self.stop_button = ttk.Button(self.forward_frame, text="停止", command=self.stop_forwarding, state="disabled")
        self.stop_button.grid(column=2, row=2, columnspan=2, sticky="we", pady=5)

        ttk.Label(self.forward_frame, text="日志:").grid(column=0, row=3, columnspan=4, sticky=tk.W, pady=(10,2))
        self.log_text = st.ScrolledText(self.forward_frame, height=10, wrap=tk.WORD)
        self.log_text.grid(column=0, row=4, columnspan=4, sticky="nsew", pady=(0, 5))
        self.forward_frame.rowconfigure(4, weight=1)

    def create_capture_tab(self):
        # 按钮
        btn_frame = ttk.Frame(self.capture_frame)
        btn_frame.grid(column=0, row=0, columnspan=4, sticky="we", pady=2)
        self.clear_btn = ttk.Button(btn_frame, text="清空列表", command=self.clear_capture)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.export_btn = ttk.Button(btn_frame, text="导出", command=self.export_packets)
        self.export_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.capture_count_label = ttk.Label(btn_frame, text="已捕获: 0 个数据包")
        self.capture_count_label.pack(side=tk.LEFT)

        self.capture_frame.columnconfigure(0, weight=1)

        # 数据包列表
        columns = ('时间', '方向', '长度', '源地址', '目标地址')
        self.packet_tree = ttk.Treeview(self.capture_frame, columns=columns, show='headings', height=15)
        for col in columns:
            self.packet_tree.heading(col, text=col)
            if col == '时间':
                self.packet_tree.column(col, width=140)
            elif col == '方向':
                self.packet_tree.column(col, width=120)
            elif col == '长度':
                self.packet_tree.column(col, width=80)
            else:
                self.packet_tree.column(col, width=200)
        self.packet_tree.grid(column=0, row=1, columnspan=4, sticky="nsew", pady=(5, 0))

        scrollbar = ttk.Scrollbar(self.capture_frame, orient=tk.VERTICAL, command=self.packet_tree.yview)
        scrollbar.grid(column=4, row=1, sticky="ns")
        self.packet_tree.configure(yscrollcommand=scrollbar.set)

        # 详情区域
        ttk.Label(self.capture_frame, text="数据包详情:").grid(column=0, row=2, columnspan=4, sticky=tk.W, pady=(10,2))
        self.detail_text = st.ScrolledText(self.capture_frame, height=8, wrap=tk.WORD)
        self.detail_text.grid(column=0, row=3, columnspan=4, sticky="nsew", pady=(0, 5))

        self.capture_frame.rowconfigure(1, weight=2)
        self.capture_frame.rowconfigure(3, weight=1)

        self.packet_tree.bind('<<TreeviewSelect>>', self.show_packet_detail)

    def format_hex_dump(self, data, bytes_per_line=16):
        lines = []
        for i in range(0, len(data), bytes_per_line):
            chunk = data[i:i+bytes_per_line]
            hex_part = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            lines.append(f'{i:04x}: {hex_part:<{bytes_per_line*3}}  {ascii_part}')
        return '\n'.join(lines)

    def show_packet_detail(self, event):
        selection = self.packet_tree.selection()
        if not selection:
            return
        item = self.packet_tree.item(selection[0])
        values = item['values']
        idx = self.packet_tree.index(selection[0])
        if idx < len(self.packets):
            packet = self.packets[idx]
            data = packet.get('data', b'')
            detail = f"时间: {values[0]}\n方向: {values[1]}\n长度: {values[2]} 字节\n源地址: {values[3]}\n目标地址: {values[4]}\n\n--- 16进制数据 ---\n"
            if data:
                detail += self.format_hex_dump(data)
            else:
                detail += '无数据'
            self.detail_text.delete(1.0, tk.END)
            self.detail_text.insert(tk.END, detail)

    def log(self, msg):
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")

    def on_packet_captured(self, packet_info):
        self.packets.append(packet_info)
        if len(self.packets) > self.max_packets:
            self.packets.pop(0)
            old_item = self.packet_tree.get_children()
            if old_item:
                self.packet_tree.delete(old_item[0])

        src = f"{packet_info.get('src_addr', ('', ''))[0]}:{packet_info.get('src_addr', ('', ''))[1]}" if packet_info.get('src_addr') else ''
        dst = f"{packet_info.get('dst_addr', ('', ''))[0]}:{packet_info.get('dst_addr', ('', ''))[1]}" if packet_info.get('dst_addr') else ''

        self.packet_tree.insert('', 'end', values=(
            packet_info.get('timestamp', ''),
            packet_info.get('direction', ''),
            packet_info.get('length', 0),
            src,
            dst
        ))
        self.capture_count_label.config(text=f"已捕获: {len(self.packets)} 个数据包")

    def start_forwarding(self):
        try:
            local_port = int(self.local_port.get())
            remote_port = int(self.remote_port.get())
        except ValueError:
            self.log("端口必须是整数")
            return
        self.forwarder = Proxium(
            self.local_ip.get(),
            local_port,
            self.remote_ip.get(),
            remote_port,
            self.log,
            self.on_packet_captured
        )
        self.forwarder.start()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.log("端口转发已启动。")

    def stop_forwarding(self):
        if self.forwarder:
            self.forwarder.stop()
            self.forwarder = None
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.log("停止指令已发送，请等待转发线程退出。")

    def clear_capture(self):
        for item in self.packet_tree.get_children():
            self.packet_tree.delete(item)
        self.packets = []
        self.capture_count_label.config(text="已捕获: 0 个数据包")

    def export_packets(self):
        if not self.packets:
            self.log("没有可导出的数据包")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="导出抓包数据"
        )
        if not filepath:
            return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("Proxium 抓包导出\n")
                f.write("=" * 60 + "\n\n")
                for i, packet in enumerate(self.packets, 1):
                    src = f"{packet.get('src_addr', ('', ''))[0]}:{packet.get('src_addr', ('', ''))[1]}" if packet.get('src_addr') else ''
                    dst = f"{packet.get('dst_addr', ('', ''))[0]}:{packet.get('dst_addr', ('', ''))[1]}" if packet.get('dst_addr') else ''
                    f.write(f"数据包 #{i}\n")
                    f.write(f"时间: {packet.get('timestamp', '')}\n")
                    f.write(f"方向: {packet.get('direction', '')}\n")
                    f.write(f"长度: {packet.get('length', 0)} 字节\n")
                    f.write(f"源地址: {src}\n")
                    f.write(f"目标地址: {dst}\n")
                    data = packet.get('data', b'')
                    if data:
                        f.write("\n--- 16进制数据 ---\n")
                        hex_dump = self.format_hex_dump(data)
                        f.write(hex_dump)
                    f.write("\n" + "-" * 60 + "\n\n")
                f.write(f"总计: {len(self.packets)} 个数据包\n")
            self.log(f"抓包数据已导出到: {filepath}")
        except Exception as e:
            self.log(f"导出失败: {e}")


def main():
    root = tk.Tk()
    app = ProxiumGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
