"""
Entry point chính của COC Auto App.
Chạy ứng dụng với giao diện đồ họa trực quan (GUI).
"""

import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ui.app import run

if __name__ == "__main__":
    run()
