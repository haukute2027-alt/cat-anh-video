# 🎬 BỘ CÔNG CỤ CẮT ẢNH TỪ VIDEO THÔNG MINH (CHỐNG TRÙNG LẶP & CHỌN ẢNH NÉT NHẤT)

Công cụ chuyên dụng để **chụp lại từng sản phẩm / từng khoảnh khắc độc lập từ video ngắn** thành các ảnh chất lượng cao (như ảnh chụp màn hình) mà **không bị trùng lặp**, **không bị mờ do rung tay hay chuyển động**.

---

## ✨ CÁC TÍNH NĂNG NỔI BẬT

1. **Lọc trùng lặp thông minh (Deduplication)**:
   - Kết hợp thuật toán **dHash (Mã băm phân biệt cấu trúc)** và **HSV Color Histogram (Biểu đồ phân bố màu sắc)**.
   - Nhận diện chính xác khi nào video chuyển sang món đồ / phân cảnh mới.
   - Nếu món đồ đó xuất hiện nhiều giây trong video, công cụ **chỉ lưu 1 ảnh duy nhất**, không lưu hàng chục ảnh giống hệt nhau.
   - **Lọc trùng lặp toàn cục**: Nếu video tua lại hoặc chiếu lại món đồ cũ, công cụ sẽ tự động bỏ qua.

2. **Chống rung & Tự động chọn khung hình nét nhất (Smart Sharpness Selection)**:
   - Khi người quay đang giơ món đồ lên hoặc chuyển cảnh, khung hình thường bị mờ (motion blur).
   - Công cụ dùng thuật toán **Laplacian Variance** để đo độ nét của từng khung hình và **chỉ chọn khung hình rõ nét nhất** trong suốt phân cảnh đó.

3. **Bỏ qua màn hình đen / chuyển cảnh tối (Fade Transition Filter)**:
   - Tự động bỏ qua các khung hình tối om khi chuyển cảnh để không lưu ảnh vô nghĩa.

4. **Hỗ trợ đầy đủ tiếng Việt có dấu trên Windows**:
   - Tên thư mục hoặc tên tệp video chứa dấu tiếng Việt (`CẮT ẢNH TỪ VIDEO`) đều chạy mượt mà 100%.

5. **Giao diện đồ họa (GUI) trực quan & Dễ dùng**:
   - Có thanh trượt tinh chỉnh độ nhạy theo ý muốn.
   - Hiển thị thanh tiến trình % và thời gian còn lại.
   - Dải xem trước ảnh (Thumbnail strip) xuất hiện ngay lập tức khi ảnh được cắt.
   - Nhấp vào ảnh để xem ngay hoặc bấm nút "Mở thư mục ảnh".

---

## 🚀 CÁCH SỬ DỤNG

### Cách 1: Sử dụng Giao diện Đồ Họa (Dễ nhất - Khuyên dùng)

1. Nhấp đúp vào tệp **`Chay_Cong_Cu.bat`** (hoặc gõ lệnh `python app_gui.py`).
2. Nhấn nút **"📂 Chọn Video..."** và chọn tệp video bạn cần cắt.
   *(Mẹo: Bạn cũng có thể kéo thả tệp video thả thẳng vào tệp `Chay_Cong_Cu.bat`)*.
3. Điều chỉnh các thông số (nếu cần, mặc định đã được tối ưu sẵn):
   - **Độ nhạy lọc trùng lặp**: Mặc định **82%** (cân bằng hoàn hảo).
     - Muốn lấy *nhiều ảnh hơn* (kể cả thay đổi nhỏ): Tăng lên `88% - 92%`.
     - Muốn chỉ lấy khi *cảnh thay đổi hoàn toàn*: Giảm về `72% - 78%`.
   - **Tần suất quét**: Mặc định `0.20s/lần` (quét 5 khung hình mỗi giây).
4. Nhấn **"▶ BẮT ĐẦU CẮT ẢNH"**.
5. Sau khi hoàn tất, bấm **"📂 Mở Thư Mục Ảnh"** để lấy toàn bộ ảnh thành phẩm.

---

### Cách 2: Sử dụng Dòng Lệnh (CLI)

Chạy lệnh trong PowerShell hoặc Command Prompt:

```bash
# Cắt cơ bản với cài đặt mặc định
python cli.py "duong_dan_video.mp4"

# Tùy chỉnh thư mục lưu và độ nhạy lọc trùng lặp
python cli.py "duong_dan_video.mp4" -o "thu_muc_luu" -t 0.85 -i 0.2
```

**Các tham số bổ sung:**
- `-t` hoặc `--threshold`: Ngưỡng lọc trùng lặp từ `0.5` đến `0.95` (mặc định: `0.82`).
- `-i` hoặc `--interval`: Tần suất quét tính bằng giây (mặc định: `0.2s`).
- `-f` hoặc `--format`: Định dạng ảnh `jpg` hoặc `png` (mặc định: `jpg`).
- `-q` hoặc `--quality`: Chất lượng ảnh JPG `1 - 100` (mặc định: `95`).

---

## 📁 CẤU TRÚC DỰ ÁN

- `Chay_Cong_Cu.bat`: Tệp chạy nhanh 1-click trên Windows.
- `app_gui.py`: Giao diện ứng dụng máy tính (Desktop GUI).
- `video_extractor.py`: Bộ máy xử lý và thuật toán trích xuất khung hình thông minh.
- `cli.py`: Công cụ dòng lệnh nhanh.
- `output/`: Thư mục mặc định chứa các ảnh đã cắt được (phân theo tên video).
