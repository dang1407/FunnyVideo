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
    blur_amount = config_dict.get("blur") * 100
    keep_audio = config.get("keepSourceAudio", True)
    ffmpeg_opts = config.get("ffmpegOptions", {}).get("outputArgs", [])
    clips = config["clips"]

    transition_file = None
    if config.get("defaults") and config["defaults"].get("transition"):
        transition_file = config["defaults"]["transition"]

    # Lấy logo path từ config nếu có
    logo_path = None
    if clips and clips[0].get("layers"):
        overlay_layer = next((x for x in clips[0]["layers"] if x["type"] == "image-overlay"), None)
        if overlay_layer:
            logo_path = overlay_layer["path"]

    # === BƯỚC 1: Render clips với logo (trừ transition) ===
    clip_files = []
    for idx, clip_cfg in enumerate(clips):
        video_layer = next((x for x in clip_cfg["layers"] if x["type"] == "video"), None)
        if not video_layer:
            continue

        video_path = video_layer["path"]
        tmp_out = f"tmp_clip_{idx}_{uuid.uuid4().hex[:6]}.mp4"

        # ---- XÁC ĐỊNH CLIP CÓ PHẢI TRANSITION HAY KHÔNG ----
        is_transition_clip = "Transition.mov" in video_path

        # Input cho ffmpeg
        inputs = ["-i", video_path]
        filter_complex = []

        # ==== LOGIC OVERLAY LOGO ĐÃ ĐƯỢC SỬA ====
        if not is_transition_clip and logo_path and os.path.exists(logo_path):
            # Có logo, KHÔNG phải transition => overlay logo
            inputs += ["-i", logo_path]

            filter_complex.append("[0:v]split=2[bg][fg]")
            filter_complex.append(
                f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"boxblur={blur_amount}:1[bg_blur]"
            )
            filter_complex.append(
                f"[fg]scale=-2:{height}:force_original_aspect_ratio=decrease[fg_scaled]"
            )
            filter_complex.append(
                f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[composed]"
            )
            filter_complex.append(
                f"[composed][1:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2[with_logo]"
            )
            filter_complex.append(
                f"[with_logo]fps={fps},setsar=1,format=yuv420p[outv]"
            )

        else:
            # Là transition HOẶC không có logo => không overlay logo
            filter_complex.append("[0:v]split=2[bg][fg]")
            filter_complex.append(
                f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"boxblur={blur_amount}:1[bg_blur]"
            )
            filter_complex.append(
                f"[fg]scale=-2:{height}:force_original_aspect_ratio=decrease[fg_scaled]"
            )
            filter_complex.append(
                f"[bg_blur][fg_scaled]overlay=(W-w)/2:(H-h)/2[composed]"
            )
            filter_complex.append(
                f"[composed]fps={fps},setsar=1,format=yuv420p[outv]"
            )

        # Render video clip
        cmd = ["ffmpeg", "-y", "-hwaccel", "cuda"] + inputs
        cmd += ["-filter_complex", ";".join(filter_complex)]
        cmd += ["-map", "[outv]"]

        if keep_audio:
            cmd += ["-map", "0:a?"]

        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
        if keep_audio:
            cmd += ["-c:a", "aac", "-b:a", "320k"]

        cmd += [tmp_out]
        run(cmd)
        clip_files.append(tmp_out)

    # === BƯỚC 2: Render transitions (KHÔNG có logo) ===
    trans_files = []
    if transition_file:
        for idx in range(len(clip_files) - 1):
            trans_tmp = f"tmp_trans_{idx}_{uuid.uuid4().hex[:6]}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", transition_file,
                "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},fps={fps},setsar=1,format=yuv420p",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "18",
                "-an",
                trans_tmp
            ]
            run(cmd)
            trans_files.append(trans_tmp)

    # === BƯỚC 3: Concat video + transitions ===
    final_sequence = []
    for i, clip_file in enumerate(clip_files):
        final_sequence.append(clip_file)
        if i < len(trans_files):
            final_sequence.append(trans_files[i])

    # FFmpeg concat input
    inputs = []
    for f in final_sequence:
        inputs += ["-i", f]

    n = len(final_sequence)
    concat_filter = "".join([f"[{i}:v]" for i in range(n)])
    concat_filter += f"concat=n={n}:v=1:a=0[outv]"

    cmd = ["ffmpeg", "-y"] + inputs
    cmd += ["-filter_complex", concat_filter]
    cmd += ["-map", "[outv]"]

    # === Audio render riêng ===
    if keep_audio:
        audio_inputs = []
        for cf in clip_files:
            audio_inputs += ["-i", cf]

        audio_filter = "".join([f"[{i}:a]" for i in range(len(clip_files))])
        audio_filter += f"concat=n={len(clip_files)}:v=0:a=1[outa]"

        temp_audio = f"temp_audio_{uuid.uuid4().hex[:6]}.aac"
        audio_cmd = ["ffmpeg", "-y"] + audio_inputs
        audio_cmd += ["-filter_complex", audio_filter]
        audio_cmd += ["-map", "[outa]", "-c:a", "aac", "-b:a", "320k", temp_audio]
        run(audio_cmd)

        temp_video_only = f"temp_video_{uuid.uuid4().hex[:6]}.mp4"
        cmd += ["-c:v", "h264_nvenc", "-preset", "p6", temp_video_only]
        run(cmd)

        final_cmd = [
            "ffmpeg", "-y",
            "-i", temp_video_only,
            "-i", temp_audio,
            "-c:v", "copy",
            "-c:a", "copy",
            out_path
        ]
        run(final_cmd)

        if os.path.exists(temp_audio):
            os.remove(temp_audio)
        if os.path.exists(temp_video_only):
            os.remove(temp_video_only)

    else:
        cmd += ["-c:v", "h264_nvenc", "-preset", "p6", out_path]
        run(cmd)

    # === XÓA FILE TẠM ===
    for f in clip_files + trans_files:
        if os.path.exists(f):
            os.remove(f)

    print("✅ DONE:", out_path)
    messagebox.showinfo("Hoàn thành", f"Render video thành công!\n\nĐường dẫn:\n{out_path}")
    return out_path
