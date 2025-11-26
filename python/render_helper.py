import json
import shlex
import subprocess
import os
import uuid
from tkinter import ttk, messagebox
def run(cmd):
    print("⚙️ Run:", " ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)

def build_and_render_from_config(video_config_path, config_dict):
    with open(video_config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    out_path = config["outPath"]
    width = 1920
    height = 1080
    fps = config_dict.get("fps")
    blur_amount = config_dict.get("blur") * 200 # Độ mờ của background (có thể điều chỉnh)
    keep_audio = config.get("keepSourceAudio", True)
    ffmpeg_opts = config.get("ffmpegOptions", {}).get("outputArgs", [])
    clips = config["clips"]

    transition_file = None
    if config.get("defaults") and config["defaults"].get("transition"):
        transition_file = config["defaults"]["transition"]

    temp_clips = []

    # === STEP 1: Render từng clip -> tmp file (chưa có logo) ===
    for idx, clip_cfg in enumerate(clips):

        video_layer = next((x for x in clip_cfg["layers"] if x["type"] == "video"), None)
        if not video_layer:
            continue

        video_path = video_layer["path"]

        tmp_out = f"tmp_clip_{idx}_{uuid.uuid4().hex[:6]}.mp4"
        temp_clips.append(tmp_out)

        inputs = ["-i", video_path]
        filter_complex = []

        # [0:v] split thành 2 stream: background và foreground
        # Background: scale to fill, blur
        # Foreground: scale to fit height, giữ tỉ lệ
        filter_complex.append(
            f"[0:v]split=2[bg][fg]"
        )

        # Background: scale full, crop center, blur
        filter_complex.append(
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},"
            f"boxblur={blur_amount}:1[bg_blur]"
        )

        # Foreground: scale to fit height, giữ tỉ lệ
        filter_complex.append(
            f"[fg]scale=-2:{height}:force_original_aspect_ratio=decrease[fg_scaled]"
        )

        # Overlay foreground lên background blur, center position
        filter_complex.append(
            f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[composed]"
        )

        # Set fps và format
        filter_complex.append(
            f"[composed]fps={fps},setsar=1,format=yuv420p[outv]"
        )

        cmd = ["ffmpeg", "-y", "-hwaccel", "cuda"] + inputs
        cmd += ["-filter_complex", ";".join(filter_complex)]
        cmd += ["-map", "[outv]"]

        if keep_audio:
            cmd += ["-map", "0:a?"]

        cmd += ffmpeg_opts
        cmd += [tmp_out]

        run(cmd)

    # === STEP 2: Tạo sequence với logo overlay: clip+logo, trans, clip+logo, trans,... ===

    final_sequence = []

    # Lấy logo path từ config nếu có
    logo_path = None
    if clips and clips[0].get("layers"):
        overlay_layer = next((x for x in clips[0]["layers"] if x["type"] == "image-overlay"), None)
        if overlay_layer:
            logo_path = overlay_layer["path"]

    for i, clip_file in enumerate(temp_clips):

        # Add logo vào clip
        if logo_path and os.path.exists(logo_path):
            clip_with_logo = f"tmp_clip_logo_{i}_{uuid.uuid4().hex[:6]}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", clip_file,
                "-i", logo_path,
                "-filter_complex",
                "[0:v][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[outv]",
                "-map", "[outv]",
                "-map", "0:a?",
                "-c:v", "h264_nvenc",
                "-preset", "p6",
                "-c:a", "copy",
                clip_with_logo
            ]
            run(cmd)
            final_sequence.append(clip_with_logo)
        else:
            # Không có logo thì dùng clip gốc
            final_sequence.append(clip_file)

        # nếu có transition & không phải clip cuối
        if transition_file and i < len(temp_clips) - 1:
            trans_tmp = f"tmp_trans_{i}_{uuid.uuid4().hex[:6]}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", transition_file,
                "-filter_complex",
                f"[0:v]scale={width}:{height},setsar=1,format=yuv420p[outv]",
                "-map", "[outv]",
                "-c:v", "h264_nvenc",
                "-preset", "p6",
                trans_tmp
            ]
            run(cmd)
            final_sequence.append(trans_tmp)

    # === STEP 3: concat toàn bộ 1 lần ===

    list_file = "merge_list.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for file in final_sequence:
            f.write(f"file '{os.path.abspath(file)}'\n")

    if os.path.exists(out_path):
        os.remove(out_path)

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_file,
        "-c:v", "h264_nvenc",
        "-preset", "p6"
    ]

    if keep_audio:
        cmd += ["-c:a", "aac", "-b:a", "320k"]

    cmd += [out_path]
    run(cmd)

    # === STEP 4: Xóa tmp ===
    for f in temp_clips:
        if os.path.exists(f):
            os.remove(f)

    # xóa clip with logo tmp
    for f in final_sequence:
        if f.startswith("tmp_clip_logo") and os.path.exists(f):
            os.remove(f)

    # xóa transition tmp
    for f in final_sequence:
        if f.startswith("tmp_trans") and os.path.exists(f):
            os.remove(f)

    if os.path.exists(list_file):
        os.remove(list_file)

    print("✅ DONE:", out_path)
    messagebox.showinfo("Hoàn thành", f"Render video thành công!\n\nĐường dẫn:\n{out_path}")
    return out_path