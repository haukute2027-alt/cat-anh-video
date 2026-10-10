"""
Ứng dụng Mobile Cắt Ảnh Video Thông Minh (Flet - Flutter)
Chạy mượt mà trên trình duyệt di động (Android / iOS) và có thể đóng gói thành APK.
"""

import os
import sys
import shutil
import zipfile
import threading
from typing import List

import flet as ft
from video_extractor import VideoFrameExtractor, format_seconds


def main(page: ft.Page):
    page.title = "Cắt Ảnh Video - Mobile App"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 16
    page.scroll = ft.ScrollMode.ADAPTIVE
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # Biến trạng thái
    selected_video_path = {"path": "", "name": ""}
    output_dir_ref = {"path": ""}
    zip_path_ref = {"path": ""}
    is_processing = [False]
    cancel_event = threading.Event()
    extracted_images: List[str] = []

    # UI Components
    txt_video_name = ft.Text(
        "Chưa chọn video nào",
        size=13,
        color=ft.Colors.GREY_400,
        italic=True,
        overflow=ft.TextOverflow.ELLIPSIS
    )
    
    txt_video_info = ft.Text("", size=12, color=ft.Colors.BLUE_300)

    slider_sim = ft.Slider(
        min=50.0,
        max=95.0,
        divisions=45,
        value=82.0,
        label="{value}%",
    )
    lbl_sim_val = ft.Text("82% (Chuẩn - Khuyên dùng)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)

    def on_sim_change(e):
        val = round(slider_sim.value)
        if val >= 88:
            tag = "Rất nhạy (Nhiều ảnh)"
        elif val >= 78:
            tag = "Chuẩn - Khuyên dùng"
        else:
            tag = "Lọc gắt (Chỉ đổi cảnh lớn)"
        lbl_sim_val.value = f"{val}% ({tag})"
        page.update()

    slider_sim.on_change = on_sim_change

    slider_interval = ft.Slider(
        min=0.05,
        max=0.8,
        divisions=15,
        value=0.20,
        label="{value}s",
    )
    lbl_interval_val = ft.Text("0.20s / lần (~5 ảnh/giây)", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_400)

    def on_interval_change(e):
        val = round(slider_interval.value, 2)
        rate = int(round(1.0 / val)) if val > 0 else 0
        lbl_interval_val.value = f"{val:.2f}s / lần (~{rate} lần/giây)"
        page.update()

    slider_interval.on_change = on_interval_change

    sw_sharp = ft.Switch(label="Tự chọn ảnh nét nhất (chống mờ tay rung)", value=True)
    sw_blank = ft.Switch(label="Bỏ qua khung hình tối/chuyển cảnh", value=True)
    sw_dedup = ft.Switch(label="Lọc trùng lặp toàn video", value=True)

    progress_bar = ft.ProgressBar(value=0, height=8, border_radius=4)
    lbl_status = ft.Text("Sẵn sàng.", size=13, weight=ft.FontWeight.W_500, color=ft.Colors.GREY_300)
    
    # Nút bấm
    btn_start = ft.ElevatedButton(
        "BẮT ĐẦU CẮT ẢNH",
        icon=ft.Icons.PLAY_ARROW_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.BLUE_600,
            color=ft.Colors.WHITE,
            padding=16,
            shape=ft.RoundedRectangleBorder(radius=10)
        )
    )

    btn_stop = ft.OutlinedButton(
        "DỪNG",
        icon=ft.Icons.STOP_ROUNDED,
        style=ft.ButtonStyle(
            color=ft.Colors.RED_400,
            padding=16,
            shape=ft.RoundedRectangleBorder(radius=10)
        ),
        disabled=True
    )

    btn_download_zip = ft.ElevatedButton(
        "TẢI FILE ZIP VỀ MÁY",
        icon=ft.Icons.DOWNLOAD_ROUNDED,
        style=ft.ButtonStyle(
            bgcolor=ft.Colors.GREEN_700,
            color=ft.Colors.WHITE,
            padding=14,
            shape=ft.RoundedRectangleBorder(radius=10)
        ),
        visible=False
    )

    gallery_row = ft.Row(wrap=True, scroll=ft.ScrollMode.ADAPTIVE, spacing=10)

    # File Picker
    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            file = e.files[0]
            selected_video_path["path"] = file.path
            selected_video_path["name"] = file.name
            txt_video_name.value = f"📹 {file.name}"
            txt_video_name.color = ft.Colors.WHITE
            txt_video_name.italic = False

            # Tính toán thư mục lưu mặc định
            base_dir = os.path.dirname(os.path.abspath(file.path)) if file.path else "output"
            video_base = os.path.splitext(file.name)[0]
            output_dir_ref["path"] = os.path.join(base_dir, "output", f"{video_base}_anh")

            txt_video_info.value = f"Nơi lưu: .../{video_base}_anh"
            btn_start.disabled = False
            page.update()

    file_picker = ft.FilePicker(on_result=on_file_picked)
    page.overlay.append(file_picker)

    def pick_video_click(e):
        file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["mp4", "mov", "avi", "mkv", "webm", "flv"]
        )

    # Hàm tạo file ZIP khi xong
    def create_zip_archive(folder_path: str, video_name: str) -> str:
        zip_filename = f"{os.path.splitext(video_name)[0]}_anh.zip"
        zip_full_path = os.path.join(os.path.dirname(folder_path), zip_filename)
        with zipfile.ZipFile(zip_full_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith((".jpg", ".png", ".jpeg")):
                        file_p = os.path.join(root, f)
                        zf.write(file_p, arcname=f)
        return zip_full_path

    # Tiến trình trích xuất
    def run_extraction_worker():
        v_path = selected_video_path["path"]
        out_dir = output_dir_ref["path"]
        th = slider_sim.value / 100.0
        interval = slider_interval.value
        pick_sharp = sw_sharp.value
        filter_b = sw_blank.value
        dedup_g = sw_dedup.value

        extractor = VideoFrameExtractor(
            similarity_threshold=th,
            sample_interval_sec=interval,
            pick_sharpest=pick_sharp,
            filter_blank_frames=filter_b,
            global_dedup=dedup_g,
            image_format="jpg",
            image_quality=95
        )

        def progress_cb(info):
            percent = info.get("percent", 0)
            curr = format_seconds(info.get("current_sec", 0))
            tot = format_seconds(info.get("total_sec", 0))
            count = info.get("saved_count", 0)
            latest = info.get("latest_file")

            progress_bar.value = percent / 100.0
            lbl_status.value = f"Đang quét {percent:.0f}% ({curr}/{tot}) • {count} ảnh"

            if latest and latest not in extracted_images and os.path.exists(latest):
                extracted_images.append(latest)
                # Thêm vào gallery
                try:
                    img_card = ft.Container(
                        content=ft.Column([
                            ft.Image(src=latest, width=120, height=90, fit=ft.ImageFit.COVER, border_radius=8),
                            ft.Text(os.path.basename(latest), size=10, width=120, no_wrap=True)
                        ], spacing=4),
                        padding=4,
                        bgcolor=ft.Colors.GREY_900,
                        border_radius=8
                    )
                    gallery_row.controls.append(img_card)
                except Exception:
                    pass

            page.update()

        try:
            res = extractor.extract(
                video_path=v_path,
                output_dir=out_dir,
                progress_callback=progress_cb,
                cancel_event=cancel_event
            )

            # Nén ZIP để tải về trên mobile
            count = res.get("saved_count", 0)
            zip_p = create_zip_archive(out_dir, selected_video_path["name"])
            zip_path_ref["path"] = zip_p

            lbl_status.value = f"✅ Hoàn tất! Đã trích xuất {count} ảnh."
            lbl_status.color = ft.Colors.GREEN_400
            progress_bar.value = 1.0
            btn_download_zip.visible = True
            btn_download_zip.text = f"TẢI FILE ZIP ({count} ẢNH)"

        except Exception as err:
            lbl_status.value = f"❌ Lỗi: {err}"
            lbl_status.color = ft.Colors.RED_400
        finally:
            is_processing[0] = False
            btn_start.disabled = False
            btn_stop.disabled = True
            page.update()

    def start_extraction(e):
        if not selected_video_path["path"]:
            lbl_status.value = "⚠️ Vui lòng chọn tệp video trước!"
            lbl_status.color = ft.Colors.ORANGE_400
            page.update()
            return

        is_processing[0] = True
        cancel_event.clear()
        extracted_images.clear()
        gallery_row.controls.clear()
        btn_start.disabled = True
        btn_stop.disabled = False
        btn_download_zip.visible = False
        progress_bar.value = 0
        lbl_status.value = "Đang bắt đầu xử lý video..."
        lbl_status.color = ft.Colors.BLUE_300
        page.update()

        t = threading.Thread(target=run_extraction_worker, daemon=True)
        t.start()

    def stop_extraction(e):
        if is_processing[0]:
            cancel_event.set()
            lbl_status.value = "Đang dừng lại..."
            lbl_status.color = ft.Colors.RED_400
            btn_stop.disabled = True
            page.update()

    def download_zip(e):
        if zip_path_ref["path"] and os.path.exists(zip_path_ref["path"]):
            os.startfile(os.path.dirname(zip_path_ref["path"]))

    btn_start.on_click = start_extraction
    btn_stop.on_click = stop_extraction
    btn_download_zip.on_click = download_zip

    # GIAO DIỆN CHÍNH (MOBILE LAYOUT)
    page.add(
        # Header Mobile
        ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Icon(ft.Icons.PHOTO_CAMERA_BACK_ROUNDED, size=32, color=ft.Colors.BLUE_400),
                    ft.Text("Cắt Ảnh Video", size=20, weight=ft.FontWeight.BOLD),
                ], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("Tự động lọc trùng lặp & Chống mờ", size=12, color=ft.Colors.GREY_400),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
            padding=ft.padding.only(bottom=10)
        ),

        # Thẻ 1: Chọn Video
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("1. Chọn Video", size=14, weight=ft.FontWeight.BOLD),
                    txt_video_name,
                    txt_video_info,
                    ft.ElevatedButton(
                        "CHỌN VIDEO TỪ THIẾT BỊ",
                        icon=ft.Icons.VIDEO_FILE_ROUNDED,
                        on_click=pick_video_click,
                        style=ft.ButtonStyle(
                            bgcolor=ft.Colors.BLUE_GREY_800,
                            color=ft.Colors.WHITE,
                            shape=ft.RoundedRectangleBorder(radius=8)
                        )
                    )
                ], spacing=8),
                padding=14
            )
        ),

        # Thẻ 2: Cài đặt thông minh
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("2. Cài Đặt Lọc Trùng Lặp", size=14, weight=ft.FontWeight.BOLD),
                    ft.Row([
                        ft.Text("Độ nhạy:", size=12),
                        lbl_sim_val
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    slider_sim,

                    ft.Row([
                        ft.Text("Tần suất quét:", size=12),
                        lbl_interval_val
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    slider_interval,

                    ft.Divider(height=10),
                    sw_sharp,
                    sw_blank,
                    sw_dedup,
                ], spacing=6),
                padding=14
            )
        ),

        # Thẻ 3: Điều khiển & Tiến độ
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([btn_start, btn_stop], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                    ft.Container(content=progress_bar, padding=ft.padding.only(top=8, bottom=4)),
                    lbl_status,
                    btn_download_zip
                ], spacing=8),
                padding=14
            )
        ),

        # Thẻ 4: Bộ sưu tập ảnh đã cắt
        ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text("3. Ảnh Đã Cắt", size=14, weight=ft.FontWeight.BOLD),
                    gallery_row
                ], spacing=8),
                padding=14
            )
        )
    )


if __name__ == "__main__":
    # Chạy trên tất cả IP (host 0.0.0.0) cổng 8550 để điện thoại cùng Wi-Fi truy cập được
    port = 8550
    print(f"==================================================")
    print(f"📱 FLET MOBILE APP SẴN SÀNG")
    print(f"🌐 Mở trên trình duyệt máy tính: http://localhost:{port}")
    print(f"📱 Mở trên điện thoại (cùng Wi-Fi): http://192.168.1.24:{port}")
    print(f"==================================================")
    
    # Khởi chạy ứng dụng Flet (web view cho mobile)
    ft.run(
        main,
        host="0.0.0.0",
        port=port,
        view=ft.AppView.WEB_BROWSER,
        assets_dir="."
    )
