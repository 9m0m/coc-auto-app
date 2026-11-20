"""
Module Quản lý Cửa sổ Giả lập và Tọa độ Khung nhìn (Viewport)
Hỗ trợ ánh xạ tọa độ màn hình Windows sang tọa độ nội bộ của Android.
"""

import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple, List
import pygetwindow as gw

import config

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

EMULATOR_PROCESS_KEYWORDS = [
    "nemuplayer", "mumuplayer", "mumu", "nemu",      # MuMu Player
    "hd-player", "bluestacks",                        # BlueStacks 5
    "dnplayer", "ldplayer", "ldboxplayer",            # LDPlayer
    "nox",                                            # NoxPlayer
    "memu",                                           # MEmu
]

EMULATOR_TITLE_KEYWORDS = [
    "bluestacks", "app player",
    "ldplayer",
    "nox",
    "mumu", "nemu",
    "memu",
    "clash of critters", "critters",
]


def setup_windows_environment() -> None:
    """Thiết lập môi trường UTF-8, DPI-awareness và tắt QuickEdit console."""
    if sys.platform.startswith("win"):
        try:
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:
            pass
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # DPI Awareness: Đọc toạ độ 1:1 chuẩn xác trên màn hình Windows
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            user32.SetProcessDPIAware()


def get_process_name_by_hwnd(hwnd: int) -> str:
    """Lấy tên file thực thi (.exe) của tiến trình sở hữu cửa sổ."""
    try:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        h_proc = kernel32.OpenProcess(0x1000, False, pid.value)
        if not h_proc:
            return ""
        buf = ctypes.create_unicode_buffer(512)
        size = wintypes.DWORD(512)
        exe_name = ""
        if kernel32.QueryFullProcessImageNameW(h_proc, 0, buf, ctypes.byref(size)):
            exe_name = os.path.basename(buf.value).lower()
        kernel32.CloseHandle(h_proc)
        return exe_name
    except Exception:
        return ""


def find_emulator_window() -> Optional[gw.Window]:
    """
    Tìm kiếm cửa sổ của các trình giả lập Android phổ biến đang mở.
    Ưu tiên 1: Cửa sổ giả lập đang được người dùng click/focus (Foreground Window).
    Ưu tiên 2: Cửa sổ có diện tích hiển thị lớn nhất trên màn hình.
    """
    candidates = []
    fore_hwnd = user32.GetForegroundWindow()
    try:
        for w in gw.getAllWindows():
            hwnd = w._hWnd
            if user32.IsIconic(hwnd):
                continue

            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            left = rect.left
            top = rect.top
            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if left < -10000 or top < -10000:
                continue

            if (width < 250 or height < 350) and (height < 250 or width < 350):
                continue

            title = (w.title or "").strip()
            title_lower = title.lower()

            # LOAI BO CHINH CUA SO CUA APP DE KHONG TU NHAN DIEN MINH
            if "coc auto master" in title_lower or "auto master" in title_lower:
                continue

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == os.getpid():
                continue

            proc_name = get_process_name_by_hwnd(hwnd)

            title_matched = any(k in title_lower for k in EMULATOR_TITLE_KEYWORDS)
            proc_matched = any(k in proc_name for k in EMULATOR_PROCESS_KEYWORDS)

            if title_matched or proc_matched:
                area = width * height
                is_foreground = 1 if (hwnd == fore_hwnd) else 0
                candidates.append((is_foreground, area, w, proc_name, title))
    except Exception:
        pass

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def get_window_rect(hwnd: int) -> Tuple[int, int, int, int]:
    """Lấy tọa độ thực (Physical Screen Pixels) của cửa sổ: left, top, width, height."""
    rect = wintypes.RECT()
    try:
        hr = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)
        )
        if hr == 0 and (rect.right - rect.left) > 100 and (rect.bottom - rect.top) > 100:
            return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    except Exception:
        pass

    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def get_game_viewport(hwnd: int, win_title: str) -> Tuple[int, int, int, int]:
    """
    Tính tọa độ vùng hiển thị game thực tế sau khi trừ thanh tiêu đề và thanh công cụ.
    """
    proc_name = get_process_name_by_hwnd(hwnd)
    title_lower = win_title.lower()

    # Xử lý riêng cho RenderWindow của LDPlayer
    if ("ldplayer" in title_lower) or ("dnplayer" in proc_name):
        try:
            render_hwnd = user32.FindWindowExW(hwnd, None, "RenderWindow", None)
            if render_hwnd:
                rect = wintypes.RECT()
                user32.GetWindowRect(render_hwnd, ctypes.byref(rect))
                rw = rect.right - rect.left
                rh = rect.bottom - rect.top
                if rw > 200 and rh > 350:
                    return rect.left, rect.top, rw, rh
        except Exception:
            pass

    left, top, w, h = get_window_rect(hwnd)
    title_bar_px, sidebar_left_px, sidebar_right_px = 0, 0, 0
    for keyword, (tb, sl, sr) in config.EMULATOR_VIEWPORT_OFFSETS.items():
        if (keyword in title_lower) or (keyword in proc_name):
            title_bar_px = tb
            sidebar_left_px = sl
            sidebar_right_px = sr
            break

    game_left = left + sidebar_left_px
    game_top = top + title_bar_px
    game_w = w - sidebar_left_px - sidebar_right_px
    game_h = h - title_bar_px

    if w > 480 or h > 820:
        scale = max(w / 443.0, h / 761.0)
        tb_adj = int(title_bar_px * scale)
        sl_adj = int(sidebar_left_px * scale)
        sr_adj = int(sidebar_right_px * scale)
        game_left = left + sl_adj
        game_top = top + tb_adj
        game_w = w - sl_adj - sr_adj
        game_h = h - tb_adj

    return game_left, game_top, game_w, game_h


def screen_to_android(
    win_x: int,
    win_y: int,
    game_vp: Tuple[int, int, int, int],
    android_size: Tuple[int, int],
) -> Tuple[int, int]:
    """
    Chuyển đổi tọa độ pixel trên màn hình Windows sang tọa độ màn hình Android nội bộ.
    """
    g_left, g_top, g_w, g_h = game_vp
    a_w, a_h = android_size

    rel_x = (win_x - g_left) / float(g_w)
    rel_y = (win_y - g_top) / float(g_h)

    # Giới hạn trong khoảng [0, 1]
    rel_x = max(0.0, min(1.0, rel_x))
    rel_y = max(0.0, min(1.0, rel_y))

    android_x = int(rel_x * a_w)
    android_y = int(rel_y * a_h)
    return android_x, android_y
