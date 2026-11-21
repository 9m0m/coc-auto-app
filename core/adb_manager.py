"""
Module Quản lý Kết nối và Điều khiển ADB (Android Debug Bridge)
Hỗ trợ tự động dò tìm cổng của BlueStacks 5, LDPlayer, MuMu Player, NoxPlayer.
"""

import os
import sys
import re
import subprocess
import winreg
from typing import Optional, List, Dict, Tuple


def get_base_dir() -> str:
    """Trả về thư mục gốc của ứng dụng (hỗ trợ cả môi trường PyInstaller .exe)."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_adb_binary() -> str:
    """Tìm file thực thi adb.exe trong dự án hoặc trong hệ thống.
    Khi chạy dưới dạng PyInstaller .exe (frozen), copy adb sang %LOCALAPPDATA%
    để tránh khóa thư mục tạm _MEIPASS gây lỗi 'Failed to remove temporary directory'.
    """
    # 1. Nếu là PyInstaller frozen .exe
    if getattr(sys, "frozen", False):
        try:
            local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            target_bin_dir = os.path.join(local_appdata, "COC_AutoMaster", "bin")
            os.makedirs(target_bin_dir, exist_ok=True)

            target_adb = os.path.join(target_bin_dir, "adb.exe")
            target_dll = os.path.join(target_bin_dir, "AdbWinApi.dll")

            src_bin_dir = os.path.join(sys._MEIPASS, "binaries")  # type: ignore
            src_adb = os.path.join(src_bin_dir, "adb.exe")
            src_dll = os.path.join(src_bin_dir, "AdbWinApi.dll")

            import shutil
            if os.path.isfile(src_adb) and (not os.path.isfile(target_adb) or os.path.getsize(target_adb) != os.path.getsize(src_adb)):
                shutil.copy2(src_adb, target_adb)
            if os.path.isfile(src_dll) and (not os.path.isfile(target_dll) or os.path.getsize(target_dll) != os.path.getsize(src_dll)):
                shutil.copy2(src_dll, target_dll)

            if os.path.isfile(target_adb):
                return target_adb
        except Exception:
            pass

    # 2. Tìm trong binaries/ của app (môi trường phát triển python thường)
    local_bin = os.path.join(get_base_dir(), "binaries", "adb.exe")
    if os.path.isfile(local_bin):
        return local_bin

    # 3. Tìm trong BlueStacks_nxt nếu có
    bs_adb = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
    if os.path.isfile(bs_adb):
        return bs_adb

    # 4. Mặc định gọi "adb" từ PATH
    return "adb"


class ADBManager:
    """Quản lý các kết nối ADB tới máy ảo/giả lập Android."""

    def __init__(self, adb_path: Optional[str] = None):
        self.adb_bin = adb_path or find_adb_binary()
        self.active_serial: Optional[str] = None
        self.screen_size: Optional[Tuple[int, int]] = None  # (width, height)

    def run_cmd(self, args: List[str], timeout: float = 5.0) -> Tuple[int, str]:
        """Chạy một lệnh ADB và trả về (exit_code, stdout)."""
        cmd = [self.adb_bin] + args
        try:
            # CREATE_NO_WINDOW = 0x08000000 để không bật cửa sổ cmd đen
            flags = 0x08000000 if sys.platform.startswith("win") else 0
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=flags,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return proc.returncode, proc.stdout.strip()
        except Exception as e:
            return -1, str(e)

    def scan_bluestacks_ports(self) -> List[Dict[str, str]]:
        """Quét các cổng ADB của BlueStacks 5 từ file bluestacks.conf."""
        found = []
        conf_path = None

        # Đọc UserDefinedDir từ Registry
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\BlueStacks_nxt") as key:
                user_dir, _ = winreg.QueryValueEx(key, "UserDefinedDir")
                test_conf = os.path.join(user_dir, "bluestacks.conf")
                if os.path.isfile(test_conf):
                    conf_path = test_conf
        except Exception:
            pass

        # Thử đường dẫn mặc định nếu không đọc được registry
        if not conf_path:
            for p in [r"C:\ProgramData\BlueStacks_nxt\bluestacks.conf", r"D:\BlueStacks_nxt\bluestacks.conf"]:
                if os.path.isfile(p):
                    conf_path = p
                    break

        if not conf_path or not os.path.isfile(conf_path):
            return found

        try:
            with open(conf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Tìm cấu hình của từng instance: bst.instance.<inst>.adb_port="<port>"
            # và display_name
            instance_ports: Dict[str, str] = {}
            instance_names: Dict[str, str] = {}

            for line in content.splitlines():
                m_port = re.match(r'bst\.instance\.([^.]+)\.(?:status\.)?adb_port="(\d+)"', line.strip())
                if m_port:
                    inst_id, port = m_port.group(1), m_port.group(2)
                    instance_ports[inst_id] = port

                m_name = re.match(r'bst\.instance\.([^.]+)\.display_name="([^"]+)"', line.strip())
                if m_name:
                    inst_id, name = m_name.group(1), m_name.group(2)
                    instance_names[inst_id] = name

            for inst_id, port in instance_ports.items():
                name = instance_names.get(inst_id, inst_id)
                found.append({
                    "name": f"BlueStacks - {name}",
                    "port": port,
                    "host": "127.0.0.1",
                    "serial": f"127.0.0.1:{port}",
                })
        except Exception:
            pass

        return found

    def get_candidate_ports(self) -> List[Dict[str, str]]:
        """Lấy danh sách tất cả các cổng giả lập có khả năng đang chạy."""
        candidates = []

        # 1. Quét BlueStacks
        bs_list = self.scan_bluestacks_ports()
        candidates.extend(bs_list)

        # 2. Cổng mặc định của LDPlayer, MuMu, Nox, MEmu
        common_ports = [
            ("LDPlayer", "5555"),
            ("LDPlayer 2", "5557"),
            ("LDPlayer 3", "5559"),
            ("MuMu Player", "7555"),
            ("MuMu Player 12", "16384"),
            ("NoxPlayer", "62001"),
            ("MEmu", "21503"),
        ]
        for name, port in common_ports:
            serial = f"127.0.0.1:{port}"
            if not any(c["serial"] == serial for c in candidates):
                candidates.append({
                    "name": name,
                    "port": port,
                    "host": "127.0.0.1",
                    "serial": serial,
                })

        return candidates

    def get_connected_devices(self) -> List[str]:
        """Lấy danh sách các serial thiết bị đã kết nối thành công và ở trạng thái 'device'."""
        code, out = self.run_cmd(["devices"])
        if code != 0:
            return []

        devices = []
        for line in out.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices

    def auto_connect(self) -> Optional[str]:
        """
        Tự động quét và kết nối tới giả lập đang mở.
        Trả về serial (ví dụ: '127.0.0.1:5555') hoặc None nếu không kết nối được.
        """
        # Kiểm tra xem có thiết bị nào đã sẵn sàng chưa
        ready = self.get_connected_devices()
        if ready:
            self.active_serial = ready[0]
            self.refresh_screen_size()
            return self.active_serial

        # Thử kết nối lần lượt các candidate ports
        candidates = self.get_candidate_ports()
        for cand in candidates:
            serial = cand["serial"]
            self.run_cmd(["connect", serial], timeout=2.0)
            if serial in self.get_connected_devices():
                self.active_serial = serial
                self.refresh_screen_size()
                return self.active_serial

        return None

    def refresh_screen_size(self) -> Optional[Tuple[int, int]]:
        """
        Lấy độ phân giải nội bộ hiện tại của màn hình Android (Width, Height).
        Đặc biệt hỗ trợ tự động nhận diện góc xoay màn hình (Portrait / Landscape)
        khi game chạy dọc trên giả lập được cấu hình ngang (như BlueStacks).
        """
        if not self.active_serial:
            return None

        # 1. Ưu tiên lấy kích thước hiển thị hiện tại (đã tính góc xoay: cur=... hoặc app=...)
        code, out = self.run_cmd(["-s", self.active_serial, "shell", "dumpsys", "window", "displays"])
        if code == 0:
            m = re.search(r"cur=(\d+)x(\d+)", out) or re.search(r"app=(\d+)x(\d+)", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                self.screen_size = (w, h)
                return self.screen_size

        # 2. Thử qua dumpsys display
        code, out = self.run_cmd(["-s", self.active_serial, "shell", "dumpsys", "display"])
        if code == 0:
            m = re.search(r"mCurrentDisplayRect=\w+\[\d+,\d+\]\[(\d+),(\d+)\]", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                self.screen_size = (w, h)
                return self.screen_size

        # 3. Fallback sang wm size
        code, out = self.run_cmd(["-s", self.active_serial, "shell", "wm", "size"])
        if code == 0:
            override_m = re.search(r"Override size:\s*(\d+)x(\d+)", out)
            if override_m:
                w, h = int(override_m.group(1)), int(override_m.group(2))
                self.screen_size = (w, h)
                return self.screen_size
            m = re.search(r"Physical size:\s*(\d+)x(\d+)", out) or re.search(r"(\d+)x(\d+)", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                self.screen_size = (w, h)
                return self.screen_size
        return None

    def tap(self, x: int, y: int) -> bool:
        """Thực hiện click ngầm (tap) vào tọa độ (x, y) trên màn hình Android."""
        if not self.active_serial:
            return False

        code, _ = self.run_cmd(
            ["-s", self.active_serial, "shell", "input", "tap", str(int(x)), str(int(y))]
        )
        return code == 0

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        """Thực hiện vuốt ngầm (swipe) từ (x1, y1) tới (x2, y2)."""
        if not self.active_serial:
            return False

        code, _ = self.run_cmd(
            [
                "-s",
                self.active_serial,
                "shell",
                "input",
                "swipe",
                str(int(x1)),
                str(int(y1)),
                str(int(x2)),
                str(int(y2)),
                str(int(duration_ms)),
            ]
        )
        return code == 0
