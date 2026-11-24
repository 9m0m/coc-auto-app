"""
Entry point chính của COC Auto App.
Chạy ứng dụng với giao diện đồ họa trực quan (GUI).
"""

import sys
import os
import ctypes

# Thiết lập DPI Awareness ở mức cao nhất trước khi nạp bất kỳ thư viện GUI/MSS nào
if sys.platform.startswith("win"):
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

# Thêm thư mục gốc vào PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.app import run

if __name__ == "__main__":
    run()
