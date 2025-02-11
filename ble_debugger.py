import asyncio
import tkinter as tk
from tkinter import ttk, scrolledtext
from bleak import BleakScanner, BleakClient
from bleak.exc import BleakError

class BLEApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BLE调试工具")
        self.client = None
        self.loop = asyncio.get_event_loop()
        self.setup_ui()
        
    def setup_ui(self):
        # 设备列表框架
        frame_devices = ttk.LabelFrame(self.root, text="蓝牙设备")
        frame_devices.pack(padx=10, pady=5, fill=tk.X)

        self.btn_scan = ttk.Button(frame_devices, text="扫描设备", command=self.start_scan)
        self.btn_scan.pack(side=tk.LEFT, padx=5)

        self.device_list = ttk.Treeview(frame_devices, columns=('name', 'address'), show='headings', height=5)
        self.device_list.heading('name', text='设备名称')
        self.device_list.heading('address', text='MAC地址')
        self.device_list.pack(padx=5, pady=5, fill=tk.X)
        self.device_list.bind('<<TreeviewSelect>>', self.select_device)

        # 连接信息框架
        frame_conn = ttk.LabelFrame(self.root, text="连接信息")
        frame_conn.pack(padx=10, pady=5, fill=tk.X)

        ttk.Label(frame_conn, text="特征值UUID:").grid(row=0, column=0, padx=5)
        self.char_entry = ttk.Entry(frame_conn, width=40)
        self.char_entry.grid(row=0, column=1, padx=5)
        self.char_entry.insert(0, "0000ffe1-0000-1000-8000-00805f9b34fb")  # 常见特征值示例

        self.btn_connect = ttk.Button(frame_conn, text="连接", command=self.toggle_connection)
        self.btn_connect.grid(row=0, column=2, padx=5)

        # 数据接收框架
        frame_rx = ttk.LabelFrame(self.root, text="接收数据")
        frame_rx.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

        self.rx_text = scrolledtext.ScrolledText(frame_rx, wrap=tk.WORD, height=10)
        self.rx_text.pack(fill=tk.BOTH, expand=True)

        # 数据发送框架
        frame_tx = ttk.LabelFrame(self.root, text="发送数据")
        frame_tx.pack(padx=10, pady=5, fill=tk.X)

        self.tx_entry = ttk.Entry(frame_tx)
        self.tx_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.btn_send = ttk.Button(frame_tx, text="发送", command=self.send_data)
        self.btn_send.pack(side=tk.RIGHT, padx=5)

    def start_scan(self):
        async def scan():
            self.btn_scan.config(state=tk.DISABLED)
            self.device_list.delete(*self.device_list.get_children())
            devices = await BleakScanner.discover()
            for d in devices:
                self.device_list.insert('', tk.END, values=(d.name, d.address))
            self.btn_scan.config(state=tk.NORMAL)

        asyncio.run_coroutine_threadsafe(scan(), self.loop)

    def select_device(self, event):
        selected = self.device_list.selection()
        if selected:
            self.selected_device = self.device_list.item(selected[0])['values'][1]

    def toggle_connection(self):
        if self.client and self.client.is_connected:
            asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)
        else:
            asyncio.run_coroutine_threadsafe(self.connect(), self.loop)

    async def connect(self):
        try:
            self.client = BleakClient(self.selected_device)
            await self.client.connect()
            self.btn_connect.config(text="断开")
            await self.client.start_notify(
                self.char_entry.get(),
                lambda _, data: self.show_data(data)
            )
        except Exception as e:
            self.show_message(f"连接失败: {str(e)}")

    async def disconnect(self):
        await self.client.stop_notify(self.char_entry.get())
        await self.client.disconnect()
        self.btn_connect.config(text="连接")
        self.show_message("已断开连接")

    def send_data(self):
        data = self.tx_entry.get()
        try:
            # 支持16进制输入（格式如：AABBCC 或 AA BB CC）
            if all(c in "0123456789abcdefABCDEF " for c in data):
                data = bytes.fromhex(data.replace(" ", ""))
            else:
                data = data.encode()
            
            asyncio.run_coroutine_threadsafe(
                self.client.write_gatt_char(self.char_entry.get(), data),
                self.loop
            )
        except Exception as e:
            self.show_message(f"发送失败: {str(e)}")

    def show_data(self, data):
        hex_str = ' '.join(f"{b:02X}" for b in data)
        self.rx_text.insert(tk.END, hex_str + '\n')
        self.rx_text.see(tk.END)

    def show_message(self, msg):
        self.rx_text.insert(tk.END, f"系统信息: {msg}\n")
        self.rx_text.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    app = BLEApp(root)
    root.mainloop()