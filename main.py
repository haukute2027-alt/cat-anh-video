"""
Điểm khởi chạy chính (Entrypoint) cho ứng dụng Flet Mobile khi đóng gói APK.
"""
from app_mobile import main
import flet as ft

if __name__ == "__main__":
    ft.run(main)
