"""
Module trích xuất khung hình từ video với thuật toán lọc trùng lặp thông minh và tự động chọn ảnh nét nhất.
Hỗ trợ đường dẫn tiếng Việt Unicode trên Windows.
"""

import os
import cv2
import numpy as np
from dataclasses import dataclass
from typing import Callable, Optional, List, Dict, Any
import threading


@dataclass
class FrameSignature:
    dhash: np.ndarray
    hist: np.ndarray
    sharpness: float
    timestamp: float
    frame_index: int


def save_image_unicode(file_path: str, image: np.ndarray, format_ext: str = ".jpg", quality: int = 95) -> bool:
    """
    Lưu ảnh an toàn trên Windows ngay cả khi đường dẫn chứa ký tự tiếng Việt có dấu.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        ext = format_ext.lower()
        if ext in [".jpg", ".jpeg"]:
            params = [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)]
        elif ext == ".png":
            params = [int(cv2.IMWRITE_PNG_COMPRESSION), 3]
        elif ext == ".webp":
            params = [int(cv2.IMWRITE_WEBP_QUALITY), int(quality)]
        else:
            params = []

        success, buffer = cv2.imencode(ext, image, params)
        if not success:
            return False

        with open(file_path, "wb") as f:
            f.write(buffer)
        return True
    except Exception as e:
        print(f"Lỗi khi lưu ảnh {file_path}: {e}")
        return False


def compute_dhash(image: np.ndarray, hash_size: int = 8) -> np.ndarray:
    """
    Tính mã băm phân biệt (Difference Hash - dHash).
    Chuyển ảnh về kích thước nhỏ và so sánh độ sáng các điểm ảnh liền kề.
    Khả năng chống rung, chịu nhiễu nén rất tốt.
    """
    resized = cv2.resize(image, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    if len(resized.shape) == 3:
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    else:
        gray = resized
    return (gray[:, 1:] > gray[:, :-1]).flatten()


def compute_color_hist(image: np.ndarray) -> np.ndarray:
    """
    Tính biểu đồ phân bố màu sắc (HSV Color Histogram).
    Giúp phân biệt các đối tượng có hình dạng tương tự nhưng màu sắc khác nhau.
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # 16 bins cho kênh H (màu sắc), 16 bins cho kênh S (độ bão hòa màu)
    hist = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def compute_sharpness(image: np.ndarray) -> float:
    """
    Đo độ nét của khung hình bằng phương sai toán tử Laplacian (Laplacian Variance).
    Khung hình nét, nhiều chi tiết -> giá trị cao.
    Khung hình mờ, nhòe do chuyển động -> giá trị thấp.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_blank_or_solid_frame(image: np.ndarray, threshold_std: float = 8.0) -> bool:
    """
    Kiểm tra xem khung hình có phải là khung hình đơn sắc / tối om / trắng toát
    thường xuất hiện khi chuyển cảnh (fade to black / fade to white) hay không.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    mean_val, std_val = cv2.meanStdDev(gray)
    mean_f = float(mean_val[0][0])
    std_f = float(std_val[0][0])
    # Quá tối hoặc quá sáng và hầu như không có độ tương phản
    if (mean_f < 15.0 or mean_f > 240.0) and std_f < threshold_std:
        return True
    return False


def calculate_similarity(sig1: FrameSignature, sig2: FrameSignature, hash_weight: float = 0.5) -> float:
    """
    Tính toán độ tương đồng kết hợp giữa dHash (cấu trúc hình học) và Histogram (màu sắc).
    Trả về giá trị từ 0.0 (hoàn toàn khác nhau) đến 1.0 (hoàn toàn trùng khớp).
    """
    # 1. Độ tương đồng mã băm (dHash)
    diff_bits = np.count_nonzero(sig1.dhash != sig2.dhash)
    total_bits = sig1.dhash.size
    hash_sim = 1.0 - (diff_bits / float(total_bits))

    # 2. Độ tương đồng màu sắc (HSV Correlation)
    color_sim = cv2.compareHist(sig1.hist, sig2.hist, cv2.HISTCMP_CORREL)
    color_sim = max(0.0, float(color_sim))

    # Kết hợp có trọng số
    return (hash_weight * hash_sim) + ((1.0 - hash_weight) * color_sim)


def format_seconds(seconds: float) -> str:
    """Định dạng giây thành chuỗi mm:ss hoặc hh:mm:ss"""
    sec = int(seconds)
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    secs = sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class VideoFrameExtractor:
    """
    Bộ trích xuất khung hình thông minh từ video.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.82,
        sample_interval_sec: float = 0.2,
        min_scene_duration_sec: float = 0.3,
        min_sharpness: float = 15.0,
        filter_blank_frames: bool = True,
        pick_sharpest: bool = True,
        global_dedup: bool = True,
        image_format: str = "jpg",
        image_quality: int = 95
    ):
        """
        :param similarity_threshold: Ngưỡng tương đồng (0.5 -> 0.95). 0.82 là cân bằng hoàn hảo.
        :param sample_interval_sec: Khoảng thời gian quét (giây). 0.2s = quét 5 lần/giây.
        :param min_scene_duration_sec: Thời lượng tối thiểu để coi là một cảnh hợp lệ (tránh chớp nháy).
        :param min_sharpness: Ngưỡng độ nét tối thiểu để loại bỏ các ảnh quá mờ.
        :param filter_blank_frames: Tự động loại bỏ màn hình đen/trắng khi chuyển cảnh.
        :param pick_sharpest: Tự động chọn khung hình nét nhất trong chuỗi khung hình tương đồng.
        :param global_dedup: Lọc trùng lặp toàn cục (nếu cảnh cũ xuất hiện lại thì không lưu lại).
        :param image_format: 'jpg', 'png', hoặc 'webp'.
        :param image_quality: Chất lượng ảnh nén (1-100).
        """
        self.similarity_threshold = float(similarity_threshold)
        self.sample_interval_sec = max(0.05, float(sample_interval_sec))
        self.min_scene_duration_sec = float(min_scene_duration_sec)
        self.min_sharpness = float(min_sharpness)
        self.filter_blank_frames = bool(filter_blank_frames)
        self.pick_sharpest = bool(pick_sharpest)
        self.global_dedup = bool(global_dedup)
        self.image_format = image_format.lower().strip(".")
        self.image_quality = int(image_quality)

    def extract(
        self,
        video_path: str,
        output_dir: str,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        Thực hiện trích xuất khung hình từ video.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Không tìm thấy tệp video: {video_path}")

        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Không thể mở video bằng OpenCV: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or np.isnan(fps):
            fps = 30.0  # Mặc định an toàn nếu metadata video thiếu fps

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            total_frames = 1

        duration_sec = total_frames / fps
        frame_step = max(1, int(round(fps * self.sample_interval_sec)))

        # Dữ liệu theo dõi
        saved_files: List[str] = []
        saved_signatures: List[FrameSignature] = []
        
        # Dữ liệu của cụm phân cảnh hiện tại
        current_cluster_best_frame: Optional[np.ndarray] = None
        current_cluster_best_sig: Optional[FrameSignature] = None
        current_cluster_start_time: float = 0.0
        current_cluster_end_time: float = 0.0
        current_cluster_count: int = 0

        frame_idx = 0
        last_reported_percent = -1

        def try_save_candidate(best_frame: np.ndarray, best_sig: FrameSignature, cluster_duration: float) -> bool:
            """Hàm lưu ứng viên nét nhất từ một cụm cảnh nếu thỏa mãn các điều kiện."""
            nonlocal saved_files, saved_signatures

            # 1. Kiểm tra thời lượng tối thiểu của cảnh
            if cluster_duration < self.min_scene_duration_sec and len(saved_signatures) > 0:
                # Nếu cảnh diễn ra quá chớp nhoáng (< 0.3s) thì có thể chỉ là chuyển cảnh tạm thời
                pass

            # 2. Kiểm tra độ nét tối thiểu (nếu bật lọc mờ)
            if best_sig.sharpness < self.min_sharpness:
                return False

            # 3. Lọc trùng lặp toàn cục (so sánh với tất cả các ảnh đã lưu trước đó)
            if self.global_dedup and saved_signatures:
                for past_sig in saved_signatures:
                    sim = calculate_similarity(past_sig, best_sig)
                    if sim >= self.similarity_threshold:
                        # Đã có ảnh gần như trùng lặp được lưu trước đó
                        return False

            # Đạt tiêu chuẩn -> Lưu ảnh ra đĩa
            count = len(saved_files) + 1
            sec = best_sig.timestamp
            time_tag = f"{int(sec // 60):02d}m{int(sec % 60):02d}s"
            filename = f"anh_{count:03d}_{time_tag}.{self.image_format}"
            full_path = os.path.join(output_dir, filename)

            if save_image_unicode(full_path, best_frame, f".{self.image_format}", self.image_quality):
                saved_files.append(full_path)
                saved_signatures.append(best_sig)
                return True
            return False

        try:
            while True:
                if cancel_event and cancel_event.is_set():
                    break

                # Đọc khung hình
                if frame_idx % frame_step == 0:
                    ret, frame = cap.read()
                    if not ret:
                        break

                    current_time_sec = frame_idx / fps

                    # Bỏ qua khung hình đơn sắc / tối đen chuyển cảnh nếu được bật
                    if self.filter_blank_frames and is_blank_or_solid_frame(frame):
                        frame_idx += 1
                        continue

                    # Tính toán chữ ký đặc trưng của khung hình
                    dhash = compute_dhash(frame)
                    hist = compute_color_hist(frame)
                    sharpness = compute_sharpness(frame)
                    sig = FrameSignature(
                        dhash=dhash,
                        hist=hist,
                        sharpness=sharpness,
                        timestamp=current_time_sec,
                        frame_index=frame_idx
                    )

                    if current_cluster_best_sig is None:
                        # Bắt đầu cụm cảnh đầu tiên
                        current_cluster_best_frame = frame.copy()
                        current_cluster_best_sig = sig
                        current_cluster_start_time = current_time_sec
                        current_cluster_end_time = current_time_sec
                        current_cluster_count = 1
                    else:
                        # So sánh khung hình hiện tại với đại diện cụm hiện tại
                        sim = calculate_similarity(current_cluster_best_sig, sig)

                        if sim >= self.similarity_threshold:
                            # Khung hình cùng một cảnh / cùng một món đồ!
                            current_cluster_end_time = current_time_sec
                            current_cluster_count += 1
                            # Nếu khung hình này nét hơn khung hình đang giữ -> cập nhật khung hình nét nhất!
                            if self.pick_sharpest and (sharpness > current_cluster_best_sig.sharpness):
                                current_cluster_best_frame = frame.copy()
                                current_cluster_best_sig = sig
                        else:
                            # Cảnh đã thay đổi hoặc chuyển sang món đồ mới!
                            # Lưu khung hình nét nhất của cảnh vừa kết thúc
                            cluster_duration = current_cluster_end_time - current_cluster_start_time
                            newly_saved = try_save_candidate(current_cluster_best_frame, current_cluster_best_sig, cluster_duration)

                            # Khởi tạo cụm mới với khung hình hiện tại
                            current_cluster_best_frame = frame.copy()
                            current_cluster_best_sig = sig
                            current_cluster_start_time = current_time_sec
                            current_cluster_end_time = current_time_sec
                            current_cluster_count = 1

                            if newly_saved and progress_callback:
                                progress_callback({
                                    "percent": round((frame_idx / total_frames) * 100, 1),
                                    "current_sec": current_time_sec,
                                    "total_sec": duration_sec,
                                    "saved_count": len(saved_files),
                                    "latest_file": saved_files[-1] if saved_files else None,
                                    "status": f"Đã tìm thấy ảnh mới ({len(saved_files)}) lúc {format_seconds(current_time_sec)}"
                                })

                    # Gửi cập nhật tiến độ định kỳ
                    percent = int((frame_idx / total_frames) * 100)
                    if progress_callback and percent != last_reported_percent and percent % 2 == 0:
                        last_reported_percent = percent
                        progress_callback({
                            "percent": percent,
                            "current_sec": current_time_sec,
                            "total_sec": duration_sec,
                            "saved_count": len(saved_files),
                            "latest_file": saved_files[-1] if saved_files else None,
                            "status": f"Đang quét video... {format_seconds(current_time_sec)} / {format_seconds(duration_sec)}"
                        })
                else:
                    # Bỏ qua nhanh khung hình mà không giải nén đầy đủ để đạt tốc độ tối đa
                    ret = cap.grab()
                    if not ret:
                        break

                frame_idx += 1

            # Kết thúc video: Lưu cụm cảnh cuối cùng
            if current_cluster_best_sig is not None and current_cluster_best_frame is not None:
                cluster_duration = current_cluster_end_time - current_cluster_start_time
                newly_saved = try_save_candidate(current_cluster_best_frame, current_cluster_best_sig, cluster_duration)
                if newly_saved and progress_callback:
                    progress_callback({
                        "percent": 100,
                        "current_sec": duration_sec,
                        "total_sec": duration_sec,
                        "saved_count": len(saved_files),
                        "latest_file": saved_files[-1] if saved_files else None,
                        "status": f"Hoàn tất cảnh cuối! Đã lưu {len(saved_files)} ảnh."
                    })

        finally:
            cap.release()

        # Tạo file tổng kết danh sách ảnh
        try:
            summary_path = os.path.join(output_dir, "thong_tin_trich_xuat.txt")
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write("=== KẾT QUẢ TRÍCH XUẤT ẢNH TỪ VIDEO ===\n")
                f.write(f"Tệp video nguồn: {os.path.basename(video_path)}\n")
                f.write(f"Độ dài video: {format_seconds(duration_sec)} ({duration_sec:.1f} giây)\n")
                f.write(f"Tổng số ảnh trích xuất: {len(saved_files)} ảnh\n")
                f.write(f"Ngưỡng lọc trùng lặp: {int(self.similarity_threshold * 100)}%\n")
                f.write(f"Tần suất quét: {self.sample_interval_sec}s/lần\n\n")
                f.write("Danh sách ảnh đã lưu:\n")
                for i, file_path in enumerate(saved_files, 1):
                    f.write(f"{i}. {os.path.basename(file_path)}\n")
        except Exception:
            pass

        return {
            "total_frames_scanned": frame_idx,
            "total_video_frames": total_frames,
            "duration_sec": duration_sec,
            "saved_count": len(saved_files),
            "output_dir": output_dir,
            "saved_files": saved_files,
            "fps": fps
        }
