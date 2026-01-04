"""
Quick Download - Tải video YouTube cực nhanh và đơn giản
Chỉ cần paste URL, enter, xong!
"""

import subprocess
import os

# Thư mục lưu video
DOWNLOAD_FOLDER = "D:\\FunnyVideo\\Main_clips\\animals"

def quick_download(url):
    """Tải video nhanh nhất có thể"""
    
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    print(f"\n⬇️  Đang tải từ: {url}")
    print(f"📁 Lưu vào: {DOWNLOAD_FOLDER}\n")
    
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[height<=720]+bestaudio/best[height<=720]/best",  # Đảm bảo có audio
        "--merge-output-format", "mp4",
        "-o", os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
        "--no-playlist",
        "--progress",  # Hiển thị progress
        "--newline",   # Mỗi update trên dòng mới
        "--audio-multistreams",  # Đảm bảo lấy audio
        url
    ]
    
    try:
        # Không capture output để thấy progress bar
        subprocess.run(cmd, check=True)
        print(f"\n✅ Tải thành công! Lưu tại: {DOWNLOAD_FOLDER}\n")
        return True
    except FileNotFoundError:
        print("\n❌ Chưa cài yt-dlp!")
        print("Cài đặt: pip install yt-dlp\n")
        return False
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tải thất bại!")
        print(f"   Mã lỗi: {e.returncode}")
        print(f"   Kiểm tra URL hoặc kết nối mạng.\n")
        return False
    except KeyboardInterrupt:
        print("\n\n⏸️  Đã dừng tải!\n")
        return False

def main():
    print("="*60)
    print("⚡ QUICK DOWNLOAD - Tải video siêu nhanh")
    print("="*60)
    print(f"📁 Lưu vào: {DOWNLOAD_FOLDER}")
    print(f"🎥 Chất lượng: 720p (tối ưu tốc độ)\n")
    
    while True:
        url = input("📹 Paste URL (hoặc 'q' để thoát): ").strip()
        
        if url.lower() in ['q', 'quit', 'exit', '']:
            print("\n👋 Tạm biệt!\n")
            break
        
        quick_download(url)
        
        # Hỏi có muốn tải tiếp không
        cont = input("Tải video khác? (Enter = có, n = không): ").strip().lower()
        if cont == 'n':
            print("\n👋 Tạm biệt!\n")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Đã thoát!\n")
