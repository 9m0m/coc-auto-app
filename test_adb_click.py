"""
Script kiểm tra kết nối ADB và Click ngầm (Non-intrusive / Background Tap).
Chạy file này khi đang mở Giả lập (BlueStacks, LDPlayer...) để kiểm tra:
1. Có tự động tìm thấy cổng ADB không?
2. Có bấm được vào game mà KHÔNG làm di chuyển chuột Windows không?
"""

import sys
import os
import time

from core.viewport import setup_windows_environment, find_emulator_window, get_game_viewport, screen_to_android
from core.adb_manager import ADBManager

setup_windows_environment()


def main():
    print("=" * 60)
    print("   KIEM TRA KET NOI ADB VA CLICK NGAM (HYBRID MODE)")
    print("=" * 60)

    # 1. Tìm cửa sổ giả lập
    print("\n[1/3] Dang tim cua so gia lap tren man hinh...")
    win = find_emulator_window()
    if not win:
        print("[!] Khong tim thay cua so gia lap nao dang mo!")
        print("    -> Vui long mo BlueStacks/LDPlayer truoc khi chay test.")
        return

    hwnd = win._hWnd
    title = win.title
    print(f" -> Phat hien cua so: '{title}' (HWND: {hwnd})")

    vp = get_game_viewport(hwnd, title)
    print(f" -> Tọa độ Game Viewport (Windows): Left={vp[0]}, Top={vp[1]}, W={vp[2]}, H={vp[3]}")

    # 2. Tự động kết nối ADB
    print("\n[2/3] Dang tu dong do tim va ket noi cong ADB...")
    adb = ADBManager()
    serial = adb.auto_connect()

    if not serial:
        print("[!] Khong the ket noi toi cong ADB nao!")
        print("    -> Danh sach cong da quet:")
        for cand in adb.get_candidate_ports()[:8]:
            print(f"       - {cand['name']}: {cand['serial']}")
        return

    print(f" -> KET NOI THANH CONG toi ADB: {serial}")
    screen_size = adb.refresh_screen_size()
    if screen_size:
        print(f" -> Do phan giai man hinh Android: {screen_size[0]}x{screen_size[1]}")
    else:
        print(" -> Canh bao: Khong doc duoc kich thuoc man hinh Android.")
        return

    # 3. Thử nghiệm Click ngầm tại tâm màn hình game
    print("\n[3/3] Chuan bi thu nghiem Click ngam tai tam man hinh...")
    center_win_x = vp[0] + vp[2] // 2
    center_win_y = vp[1] + vp[3] // 2

    android_x, android_y = screen_to_android(center_win_x, center_win_y, vp, screen_size)
    print(f" -> Toa do tren Windows : ({center_win_x}, {center_win_y})")
    print(f" -> Quy doi sang Android: ({android_x}, {android_y})")
    print("\n>>> CHU Y: Quan sat con tro chuot tren man hinh!")
    print("    Trong 3 giay nua se thuc hien click ngam vao tam man hinh gia lap...")

    for i in range(3, 0, -1):
        print(f"    {i}...")
        time.sleep(1)

    ok = adb.tap(android_x, android_y)
    if ok:
        print("\n[THANH CONG] Da gui lenh Click ngam qua ADB!")
        print("-> Con tro chuot Windows cua ban hoan toan KHONG bi di chuyen!")
    else:
        print("\n[THAT BAI] Khong the gui lenh click qua ADB.")


if __name__ == "__main__":
    main()
