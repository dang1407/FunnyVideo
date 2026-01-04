"""
Video Downloader - Tải video YouTube nhanh chóng
Hỗ trợ: single video, playlist, channel
Lọc video theo thời lượng
"""

import os
import sys
import subprocess
import json
from datetime import timedelta

# ==========================================
# CẤU HÌNH
# ==========================================
OUTPUT_DIR = "D:\\FunnyVideo\\Main_clips\\animals"  # Thư mục lưu video
MAX_DURATION = 120  # Thời lượng tối đa (giây) - 2 phút
VIDEO_FORMAT = "mp4"  # Format video
VIDEO_QUALITY = "720"  # 720p (nhanh), có thể đổi sang 1080, 480...

# ==========================================
# KIỂM TRA YT-DLP
# ==========================================
def check_ytdlp():
    """Kiểm tra yt-dlp đã cài chưa"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True
        )
        print(f"✅ yt-dlp version: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("❌ Chưa cài yt-dlp!")
        print("\n📌 Cài đặt:")
        print("   pip install yt-dlp")
        print("   hoặc: winget install yt-dlp")
        return False

# ==========================================
# LẤY THÔNG TIN VIDEO
# ==========================================
def get_video_info(url):
    """Lấy thông tin video không tải xuống"""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",  # Chỉ lấy 1 video
        url
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"❌ Lỗi lấy thông tin: {e}")
        return None

def get_playlist_info(url):
    """Lấy danh sách video trong playlist"""
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        url
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    videos.append(json.loads(line))
                except:
                    pass
        return videos
    except Exception as e:
        print(f"❌ Lỗi lấy playlist: {e}")
        return []

# ==========================================
# TẢI VIDEO
# ==========================================
def download_video(url, output_dir=OUTPUT_DIR, max_duration=MAX_DURATION):
    """
    Tải video từ URL
    Tự động lọc video theo thời lượng
    """
    
    # Tạo thư mục nếu chưa có
    os.makedirs(output_dir, exist_ok=True)
    
    # Lấy thông tin video trước
    print(f"\n🔍 Đang kiểm tra video...")
    info = get_video_info(url)
    
    if not info:
        print("❌ Không lấy được thông tin video")
        return False
    
    duration = info.get('duration', 0)
    title = info.get('title', 'Unknown')
    uploader = info.get('uploader', 'Unknown')
    
    print(f"📹 Video: {title}")
    print(f"👤 Kênh: {uploader}")
    print(f"⏱️  Thời lượng: {timedelta(seconds=duration)}")
    
    # Kiểm tra thời lượng
    if duration > max_duration:
        print(f"⚠️  Video dài hơn {max_duration}s - BỎ QUA")
        return False
    
    # Tải video
    print(f"\n⬇️  Đang tải...")
    print(f"📁 Lưu vào: {output_dir}\n")
    
    # Format selector đảm bảo có cả video và audio
    # Thử nhiều format fallback để đảm bảo có tiếng
    cmd = [
        "yt-dlp",
        "-f", f"bestvideo[height<={VIDEO_QUALITY}]+bestaudio/best[height<={VIDEO_QUALITY}]/best",
        "--merge-output-format", VIDEO_FORMAT,
        "-o", os.path.join(output_dir, "%(title)s.%(ext)s"),
        "--no-playlist",
        "--progress",  # Hiển thị progress bar
        "--newline",   # Mỗi progress update trên dòng mới
        "--audio-multistreams",  # Đảm bảo lấy audio
        url
    ]
    
    # Debug: in command
    print("🔧 Debug - Command:")
    print(" ".join(cmd))
    print()
    
    try:
        # Không capture output để thấy progress real-time
        result = subprocess.run(cmd, check=True)
        print(f"\n✅ Tải thành công!")
        print(f"📁 Vị trí: {output_dir}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Lỗi tải video!")
        print(f"   Mã lỗi: {e.returncode}")
        print(f"   Kiểm tra URL hoặc kết nối mạng")
        return False
    except FileNotFoundError:
        print(f"\n❌ Không tìm thấy yt-dlp!")
        print(f"   Cài đặt: pip install yt-dlp")
        return False

def download_playlist(url, output_dir=OUTPUT_DIR, max_duration=MAX_DURATION, limit=None):
    """
    Tải tất cả video trong playlist (lọc theo thời lượng)
    """
    
    print(f"\n🔍 Đang lấy danh sách playlist...")
    videos = get_playlist_info(url)
    
    if not videos:
        print("❌ Không tìm thấy video nào")
        return
    
    print(f"📋 Tìm thấy {len(videos)} video")
    
    if limit:
        videos = videos[:limit]
        print(f"📌 Giới hạn tải {limit} video đầu tiên")
    
    # Tạo thư mục
    os.makedirs(output_dir, exist_ok=True)
    
    # Tải từng video
    success_count = 0
    skip_count = 0
    
    for i, video in enumerate(videos, 1):
        video_url = f"https://www.youtube.com/watch?v={video['id']}"
        
        print(f"\n{'='*60}")
        print(f"📹 [{i}/{len(videos)}] {video.get('title', 'Unknown')}")
        print(f"{'='*60}")
        
        # Lấy thông tin chi tiết
        info = get_video_info(video_url)
        if not info:
            print("⚠️  Bỏ qua (không lấy được info)")
            skip_count += 1
            continue
        
        duration = info.get('duration', 0)
        print(f"⏱️  Thời lượng: {timedelta(seconds=duration)}")
        
        # Kiểm tra thời lượng
        if duration > max_duration:
            print(f"⚠️  BỎ QUA (dài hơn {max_duration}s)")
            skip_count += 1
            continue
        
        # Tải video
        if download_video(video_url, output_dir, max_duration):
            success_count += 1
        else:
            skip_count += 1
    
    print(f"\n{'='*60}")
    print(f"✅ HOÀN TẤT!")
    print(f"📊 Thành công: {success_count}/{len(videos)}")
    print(f"⏭️  Bỏ qua: {skip_count}/{len(videos)}")
    print(f"📁 Thư mục: {output_dir}")
    print(f"{'='*60}")

# ==========================================
# CHỨC NĂNG BỔ SUNG
# ==========================================
def download_shorts(channel_url, output_dir=OUTPUT_DIR, limit=10):
    """
    Tải YouTube Shorts từ kênh (thường dưới 60s)
    """
    
    print(f"\n🔍 Đang tìm Shorts từ kênh...")
    
    # Lấy tất cả video ngắn từ kênh
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        "--playlist-items", f"1-{limit}",
        f"{channel_url}/shorts"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    videos.append(json.loads(line))
                except:
                    pass
        
        print(f"📋 Tìm thấy {len(videos)} Shorts")
        
        # Tải từng short
        for i, video in enumerate(videos, 1):
            video_url = f"https://www.youtube.com/watch?v={video['id']}"
            print(f"\n[{i}/{len(videos)}] Đang tải: {video.get('title', 'Unknown')}")
            download_video(video_url, output_dir, max_duration=60)
        
        print("\n✅ Hoàn tất tải Shorts!")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")

def search_and_download(query, max_results=10, output_dir=OUTPUT_DIR):
    """
    Tìm kiếm và tải video theo từ khóa
    """
    
    print(f"\n🔍 Tìm kiếm: '{query}'")
    
    search_url = f"ytsearch{max_results}:{query}"
    
    cmd = [
        "yt-dlp",
        "--dump-json",
        "--flat-playlist",
        search_url
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8',
            errors='replace'
        )
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                try:
                    videos.append(json.loads(line))
                except:
                    pass
        
        print(f"📋 Tìm thấy {len(videos)} video")
        
        # Tải từng video
        for i, video in enumerate(videos, 1):
            video_url = f"https://www.youtube.com/watch?v={video['id']}"
            print(f"\n[{i}/{len(videos)}] {video.get('title', 'Unknown')}")
            download_video(video_url, output_dir, MAX_DURATION)
        
        print("\n✅ Hoàn tất!")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")

# ==========================================
# GIAO DIỆN CHÍNH
# ==========================================
def main():
    print("="*60)
    print("🎥 VIDEO DOWNLOADER - YouTube & More")
    print("="*60)
    
    # Kiểm tra yt-dlp
    if not check_ytdlp():
        return
    
    print(f"\n📌 Cấu hình:")
    print(f"   - Thư mục: {OUTPUT_DIR}")
    print(f"   - Thời lượng tối đa: {MAX_DURATION}s ({MAX_DURATION//60}p)")
    print(f"   - Chất lượng: {VIDEO_QUALITY}p")
    
    while True:
        print("\n" + "="*60)
        print("MENU:")
        print("="*60)
        print("1. Tải 1 video")
        print("2. Tải playlist")
        print("3. Tải Shorts từ kênh")
        print("4. Tìm kiếm và tải")
        print("5. Thay đổi cấu hình")
        print("0. Thoát")
        print("="*60)
        
        choice = input("\n👉 Chọn: ").strip()
        
        if choice == "1":
            url = input("📹 URL video: ").strip()
            if url:
                download_video(url)
        
        elif choice == "2":
            url = input("📋 URL playlist: ").strip()
            limit_input = input("📊 Giới hạn số video (Enter = tất cả): ").strip()
            limit = int(limit_input) if limit_input else None
            if url:
                download_playlist(url, limit=limit)
        
        elif choice == "3":
            url = input("👤 URL kênh (VD: https://www.youtube.com/@channelname): ").strip()
            limit_input = input("📊 Số lượng Shorts (mặc định 10): ").strip()
            limit = int(limit_input) if limit_input else 10
            if url:
                download_shorts(url, limit=limit)
        
        elif choice == "4":
            query = input("🔍 Từ khóa tìm kiếm: ").strip()
            limit_input = input("📊 Số kết quả (mặc định 10): ").strip()
            limit = int(limit_input) if limit_input else 10
            if query:
                search_and_download(query, max_results=limit)
        
        elif choice == "5":
            print(f"\n📌 Cấu hình hiện tại:")
            print(f"   - OUTPUT_DIR: {OUTPUT_DIR}")
            print(f"   - MAX_DURATION: {MAX_DURATION}s")
            print(f"   - VIDEO_QUALITY: {VIDEO_QUALITY}p")
            print("\n💡 Để thay đổi, sửa trực tiếp trong file!")
        
        elif choice == "0":
            print("\n👋 Tạm biệt!")
            break
        
        else:
            print("❌ Lựa chọn không hợp lệ!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Đã hủy!")
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
