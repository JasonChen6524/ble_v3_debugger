import asyncio
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

# 设置Windows事件循环策略
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class BLEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BLE调试工具 v3.2")
        self.client = None
        self.selected_device = None
        self.scanning = False
        
        # 初始化事件循环
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.setup_ui()
        self.setup_style()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Linux权限提示
        if sys.platform.startswith('linux'):
            self.show_system_msg("提示：Linux系统可能需要运行'sudo setcap cap_net_raw,cap_net_admin+eip $(readlink -f $(which python3))'")

    def setup_style(self):
        """初始化界面样式"""
        style = ttk.Style()
        style.configure('Red.TButton', foreground='red')
        style.configure('Green.TButton', foreground='dark green')
        style.map('Connect.TButton',
                foreground=[('active', 'white'), ('!disabled', 'black')],
                background=[('disabled', 'gray'), ('active', 'dark cyan')])

    def setup_ui(self):
        """构建用户界面"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 设备扫描区域
        scan_frame = ttk.LabelFrame(main_frame, text="设备扫描 (建议靠近设备)")
        scan_frame.pack(fill=tk.X, pady=5)

        self.btn_scan = ttk.Button(
            scan_frame, 
            text="开始扫描", 
            command=self.start_scan,
            style='Green.TButton'
        )
        self.btn_scan.pack(side=tk.LEFT, padx=5, pady=5)

        # 扫描过滤框
        self.filter_entry = ttk.Entry(scan_frame, width=25)
        self.filter_entry.pack(side=tk.RIGHT, padx=5)
        self.filter_entry.insert(0, "输入名称/MAC过滤")

        # 设备列表
        self.device_list = ttk.Treeview(
            scan_frame,
            columns=('name', 'address', 'rssi'),
            show='headings',
            height=6
        )
        self.device_list.heading('name', text='设备名称')
        self.device_list.heading('address', text='MAC地址')
        self.device_list.heading('rssi', text='信号强度')
        self.device_list.column('name', width=150)
        self.device_list.column('address', width=180)
        self.device_list.column('rssi', width=80, anchor=tk.CENTER)
        self.device_list.pack(fill=tk.X, padx=5, pady=5)
        self.device_list.bind('<<TreeviewSelect>>', self.select_device)

        # 连接控制区域
        conn_frame = ttk.LabelFrame(main_frame, text="连接控制")
        conn_frame.pack(fill=tk.X, pady=5)

        ttk.Label(conn_frame, text="特征值UUID:").grid(row=0, column=0, padx=5)
        self.char_entry = ttk.Entry(conn_frame, width=45)
        self.char_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        self.char_entry.insert(0, "0000ffe1-0000-1000-8000-00805f9b34fb")

        self.btn_connect = ttk.Button(
            conn_frame,
            text="连接设备",
            command=self.toggle_connection,
            style='Connect.TButton',
            state=tk.DISABLED
        )
        self.btn_connect.grid(row=0, column=2, padx=10)

        # 数据接收区域
        rx_frame = ttk.LabelFrame(main_frame, text="接收数据")
        rx_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.rx_text = scrolledtext.ScrolledText(
            rx_frame,
            wrap=tk.WORD,
            height=12,
            font=('Consolas', 10)
        )
        self.rx_text.pack(fill=tk.BOTH, expand=True)
        self.rx_text.tag_config('system', foreground='gray')

        # 数据发送区域
        tx_frame = ttk.LabelFrame(main_frame, text="发送数据")
        tx_frame.pack(fill=tk.X, pady=5)

        self.tx_entry = ttk.Entry(tx_frame)
        self.tx_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.btn_send = ttk.Button(
            tx_frame,
            text="发送",
            command=self.send_data,
            state=tk.DISABLED
        )
        self.btn_send.pack(side=tk.RIGHT, padx=5)

    def start_scan(self):
        """启动设备扫描"""
        async def _scan():
            self.scanning = True
            self.btn_scan.config(state=tk.DISABLED, text="扫描中...")
            self.device_list.delete(*self.device_list.get_children())
            self.show_system_msg("正在扫描BLE设备（约5秒）...")
            
            try:
                async with BleakScanner() as scanner:
                    await asyncio.sleep(5.0)  # 扫描持续时间
                    devices = await scanner.get_discovered_devices()
                    
                    # 更新设备列表
                    for d in devices:
                        self.root.after(0, self._insert_device, 
                            d.name or "Unknown",
                            d.address,
                            d.rssi or "N/A"
                        )
                    
                    self.show_system_msg(f"发现 {len(devices)} 个设备")
                    print("调试信息 - 发现设备:")  # 终端输出用于调试
                    for d in devices:
                        print(f"  {d.address} | {d.name or 'Unknown'} | RSSI: {d.rssi}")

            except Exception as e:
                self.show_system_msg(f"扫描失败: {str(e)}")
                messagebox.showerror("错误", f"扫描失败: {str(e)}")
            finally:
                self.btn_scan.config(state=tk.NORMAL, text="开始扫描")
                self.scanning = False

        self.loop.create_task(_scan())

    def _insert_device(self, name, address, rssi):
        """安全插入设备到列表"""
        filter_text = self.filter_entry.get().lower()
        if filter_text:
            if filter_text not in name.lower() and filter_text not in address.lower():
                return
        self.device_list.insert('', tk.END, values=(name, address, rssi))

    def select_device(self, event):
        """选择设备"""
        selected = self.device_list.selection()
        if selected:
            self.selected_device = self.device_list.item(selected[0])['values'][1]
            self.btn_connect.config(state=tk.NORMAL)

    def toggle_connection(self):
        """切换连接状态"""
        if self.client and self.client.is_connected:
            self.loop.call_soon_threadsafe(asyncio.create_task, self.disconnect())
        else:
            self.loop.call_soon_threadsafe(asyncio.create_task, self.connect())

    async def connect(self):
        """建立连接"""
        try:
            self.client = BleakClient(self.selected_device)
            await self.client.connect()
            self.btn_connect.config(text="断开连接", style='Red.TButton')
            self.btn_send.config(state=tk.NORMAL)
            self.char_entry.config(state=tk.DISABLED)
            self.show_system_msg(f"已连接: {self.selected_device}")
            
            # 启用通知（修正后的正确语法）
            await self.client.start_notify(
                self.char_entry.get(),
                lambda _, data: self.show_data(data)
            )  # 确保括号闭合

        except Exception as e:
            self.show_system_msg(f"连接失败: {str(e)}")
            self.btn_connect.config(text="连接设备", style='Connect.TButton')

    async def disconnect(self):
        """断开连接"""
        try:
            await self.client.stop_notify(self.char_entry.get())
            await self.client.disconnect()
            self.show_system_msg("连接已断开")
        except Exception as e:
            self.show_system_msg(f"断开错误: {str(e)}")
        finally:
            self.btn_connect.config(text="连接设备", style='Connect.TButton')
            self.btn_send.config(state=tk.DISABLED)
            self.char_entry.config(state=tk.NORMAL)

    def send_data(self):
        """发送数据"""
        data = self.tx_entry.get().strip()
        if not data:
            return

        async def _send():
            try:
                # 自动检测数据格式
                if all(c in "0123456789abcdefABCDEF " for c in data):
                    send_bytes = bytes.fromhex(data.replace(" ", ""))
                else:
                    send_bytes = data.encode('utf-8')
                
                await self.client.write_gatt_char(
                    self.char_entry.get(),
                    send_bytes
                )
                self.tx_entry.delete(0, tk.END)
                self.show_system_msg(f"已发送: {send_bytes.hex(' ').upper()}")
                
            except Exception as e:
                self.show_system_msg(f"发送失败: {str(e)}")

        self.loop.call_soon_threadsafe(asyncio.create_task, _send())

    def show_data(self, data):
        """显示接收到的数据"""
        hex_str = ' '.join(f"{b:02X}" for b in data)
        timestamp = asyncio.get_event_loop().time()
        self.rx_text.insert(tk.END, f"[{timestamp:.2f}] RX: {hex_str}\n")
        self.rx_text.see(tk.END)

    def show_system_msg(self, msg):
        """显示系统消息"""
        self.rx_text.insert(tk.END, f"[系统] {msg}\n", 'system')
        self.rx_text.see(tk.END)

    def on_closing(self):
        """关闭窗口时的清理操作"""
        if self.client and self.client.is_connected:
            self.loop.run_until_complete(self.disconnect())
        self.loop.close()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = BLEApp(root)
    root.mainloop()