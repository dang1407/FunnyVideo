# 🎥 Video Downloader - Hướng dẫn sử dụng

## 🚀 Cài đặt nhanh

### 1. Cài yt-dlp
```bash
pip install yt-dlp
```

Hoặc dùng winget (Windows):
```bash
winget install yt-dlp
```

### 2. Chạy chương trình
```bash
backend video_downloader.py
```

## ✨ Tính năng

### 📹 Tải 1 video
```
Chọn: 1
URL: https://www.youtube.com/watch?v=xxxxx
```
- Tự động kiểm tra thời lượng
- Chỉ tải video ≤ 2 phút

### 📋 Tải playlist
```
Chọn: 2
URL: https://www.youtube.com/playlist?list=xxxxx
Giới hạn: 10 (hoặc Enter để tải tất cả)
```
- Lọc video theo thời lượng
- Bỏ qua video dài hơn 2 phút
- Hiển thị progress chi tiết

### 🎬 Tải Shorts từ kênh
```
Chọn: 3
URL kênh: https://www.youtube.com/@channelname
Số lượng: 10
```
- Tải Shorts nhanh (thường < 60s)
- Chọn số lượng muốn tải

### 🔍 Tìm kiếm và tải
```
Chọn: 4
Từ khóa: funny cats
Số kết quả: 10
```
- Tìm kiếm video theo từ khóa
- Tải tự động với filter thời lượng

## ⚙️ Cấu hình

Mở file `video_downloader.py` và chỉnh:

```python
OUTPUT_DIR = "D:\\FunnyVideo\\Downloads"  # Thư mục lưu
MAX_DURATION = 120  # 2 phút (120 giây)
VIDEO_QUALITY = "720"  # 720p (nhanh), 1080p (đẹp hơn)
VIDEO_FORMAT = "mp4"  # Format video
```

## 💡 Tips & Tricks

### Tải nhanh nhất
- Dùng `VIDEO_QUALITY = "480"` (quality thấp = tải nhanh)
- Giới hạn số video trong playlist
- Tải Shorts (rất ngắn, tải cực nhanh)

### Tải chất lượng cao
```python
VIDEO_QUALITY = "1080"  # Full HD
```

### Lọc video ngắn hơn
```python
MAX_DURATION = 60  # Chỉ tải video ≤ 1 phút
```

### Tải từ nhiều nguồn
yt-dlp hỗ trợ:
- YouTube
- TikTok
- Instagram
- Facebook
- Twitter/X
- và 1000+ sites khác!

## 📊 Ví dụ thực tế

### Tải 20 Shorts đầu tiên từ kênh
```
Chọn: 3
URL: https://www.youtube.com/@MrBeast
Số lượng: 20
```

### Tìm và tải video ngắn về động vật
```
Chọn: 4
Từ khóa: funny animals shorts
Số kết quả: 15
```

### Tải playlist nhưng chỉ 10 video ngắn nhất
```
Chọn: 2
URL: https://www.youtube.com/playlist?list=xxxxx
Giới hạn: 10
```

## 🐛 Xử lý lỗi

### Lỗi: "yt-dlp not found"
```bash
pip install yt-dlp
# hoặc
winget install yt-dlp
```

### Video không tải được
- Kiểm tra URL có đúng không
- Video có bị private/deleted không
- Thử cập nhật yt-dlp: `pip install -U yt-dlp`

### Tải chậm
- Giảm `VIDEO_QUALITY` xuống 480 hoặc 360
- Kiểm tra kết nối mạng
- YouTube có thể throttle tốc độ

## 🎯 Use cases

### 1. Thu thập video ngắn cho content
```python
MAX_DURATION = 120  # 2 phút
VIDEO_QUALITY = "720"  # Đủ tốt
```

### 2. Download Shorts hàng loạt
```python
# Tải 50 Shorts từ nhiều kênh hot
```

### 3. Tạo thư viện clip
```python
# Tìm kiếm theo keyword
# Lọc theo duration
# Tự động organize
```

## 📝 Notes

- Video được lưu với tên gốc từ YouTube
- Tự động merge video + audio thành 1 file
- Hỗ trợ resume nếu bị gián đoạn
- File format: MP4 (universal compatibility)

## 🔧 Advanced

### Tải audio only (nhạc)
Thêm option trong code:
```python
"-f", "bestaudio",
"--extract-audio",
"--audio-format", "mp3"
```

### Tải subtitle
```python
"--write-sub",
"--sub-lang", "vi,en"
```

### Tải thumbnail
```python
"--write-thumbnail"
```

## 📞 Support

Nếu gặp lỗi:
1. Update yt-dlp: `pip install -U yt-dlp`
2. Kiểm tra ffmpeg đã cài chưa
3. Xem log lỗi trong console

---

**Happy Downloading! 🎉**
