import json
import shlex
import subprocess
import os
import uuid
from tkinter import ttk, messagebox

import json
import subprocess
import os
import sys

# ==========================================
# CẤU HÌNH
# ==========================================
FFMPEG_EXEC = "ffmpeg"


def get_input_index(file_path, input_map, inputs_list):
    if file_path not in input_map:
        input_map[file_path] = len(inputs_list)
        inputs_list.append(file_path)
    return input_map[file_path]


def generate_ffmpeg_command(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    width = json_data.get('width', 1920)
    height = json_data.get('height', 1080)
    fps = json_data.get('fps', 25)
    out_path = json_data.get('outPath', 'output.mp4')

    input_map = {}
    inputs_list = []
    filter_chains = []
    concat_segments = []

    # ==========================================
    # TÍNH TOÁN TIMELINE TÍCH LŨY
    # ==========================================
    cumulative_time = 0.0
    clip_start_times = []

    for clip in json_data['clips']:
        clip_start_times.append(cumulative_time)

        # Tính duration của clip
        clip_duration = clip.get('duration')
        if not clip_duration:
            # Tìm main video layer để lấy duration
            main_video = next((l for l in clip.get('layers', []) if l['type'] == 'video'), None)
            if main_video:
                cut_from = main_video.get('cutFrom', 0)
                cut_to = main_video.get('cutTo')
                clip_duration = cut_to - cut_from if cut_to else 0

        cumulative_time += clip_duration if clip_duration else 0

    # ==========================================
    # XỬ LÝ VIDEO CLIPS
    # ==========================================
    for i, clip in enumerate(json_data['clips']):
        clip_duration = clip.get('duration')
        layers = clip.get('layers', [])
        clip_start_time = clip_start_times[i]

        out_v = f"v_clip_{i}_out"
        out_a = f"a_clip_{i}_out"
        current_v_pad = None
        has_audio = False

        main_video_layer = next((l for l in layers if l['type'] == 'video'), None)
        fill_color_layer = next((l for l in layers if l['type'] == 'fill-color'), None)

        # --- 1. PHÂN LOẠI LAYERS ---
        transition_layers = []
        logo_layers = []

        for layer in layers:
            if layer == main_video_layer or layer == fill_color_layer:
                continue

            if layer['type'] == 'video':
                # Transition video
                transition_layers.append(layer)
            elif layer['type'] == 'image-overlay':
                # Logo
                logo_layers.append(layer)

        # --- 2. TẠO LAYER NỀN (BASE) ---
        if main_video_layer:
            path = main_video_layer['path']
            idx = get_input_index(path, input_map, inputs_list)
            cut_to = main_video_layer.get('cutTo')
            cut_from = main_video_layer.get('cutFrom', 0)
            segment_duration = cut_to - cut_from if cut_to else None

            trim_cmd = f"[{idx}:v]trim=start={cut_from}"
            if cut_to:
                trim_cmd += f":end={cut_to}"
            trim_cmd += f",setpts=PTS-STARTPTS[v_tmp_{i}_raw]"
            filter_chains.append(trim_cmd)

            if json_data.get('keepSourceAudio', True):
                atrim_cmd = f"[{idx}:a]atrim=start={cut_from}"
                if cut_to:
                    atrim_cmd += f":end={cut_to}"
                atrim_cmd += f",asetpts=PTS-STARTPTS[{out_a}]"
                filter_chains.append(atrim_cmd)
                has_audio = True

            if main_video_layer.get('resizeMode') == 'contain-blur':
                bg_chain = (f"[v_tmp_{i}_raw]split=2[bg_{i}][fg_{i}];"
                            f"[bg_{i}]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=20:10[bg_blur_{i}];"
                            f"[fg_{i}]scale={width}:{height}:force_original_aspect_ratio=decrease[fg_scaled_{i}];"
                            f"[bg_blur_{i}][fg_scaled_{i}]overlay=(W-w)/2:(H-h)/2[v_base_{i}]")
                filter_chains.append(bg_chain)
                current_v_pad = f"[v_base_{i}]"
            else:
                scale_cmd = f"[v_tmp_{i}_raw]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}[v_base_{i}]"
                filter_chains.append(scale_cmd)
                current_v_pad = f"[v_base_{i}]"

        elif fill_color_layer:
            color = fill_color_layer.get('color', '#000000')
            dur = clip_duration if clip_duration else 0.1
            segment_duration = dur

            color_cmd = f"color=c={color}:s={width}x{height}:d={dur}[v_base_{i}]"
            filter_chains.append(color_cmd)
            current_v_pad = f"[v_base_{i}]"

            silence_cmd = f"anullsrc=cl=stereo:r=44100:d={dur}[{out_a}]"
            filter_chains.append(silence_cmd)
            has_audio = True

        # --- 3. OVERLAY LOGOS TRƯỚC (logo ở giữa, sẽ bị transition che khi có transition) ---
        for logo_idx, layer in enumerate(logo_layers):
            path = layer['path']
            idx = get_input_index(path, input_map, inputs_list)
            layer_pad = f"logo_{i}_{logo_idx}"

            # Thêm loop để logo không bị hết, scale về kích thước canvas
            cmd = f"[{idx}:v]loop=loop=-1:size=1:start=0,scale={width}:{height}:force_original_aspect_ratio=decrease[{layer_pad}]"
            filter_chains.append(cmd)

            # Logo luôn hiển thị, không cần enable condition phức tạp
            # Transition sẽ tự động che logo khi xuất hiện
            next_pad = f"v_clip_{i}_logo_{logo_idx}"
            overlay_cmd = f"{current_v_pad}[{layer_pad}]overlay=(W-w)/2:(H-h)/2:shortest=1[{next_pad}]"
            filter_chains.append(overlay_cmd)
            current_v_pad = f"[{next_pad}]"

        # --- 4. OVERLAY TRANSITIONS SAU CÙNG (đè lên logo, che logo khi có transition) ---
        overlay_idx = 0
        for layer in transition_layers:
            path = layer['path']
            idx = get_input_index(path, input_map, inputs_list)
            layer_pad = f"layer_{i}_{overlay_idx}"

            cut_from = layer.get('cutFrom', 0)
            cut_to = layer.get('cutTo')
            start_time = layer.get('start', 0)
            stop_time = layer.get('stop')

            trim_part = f"[{idx}:v]trim=start={cut_from}"
            if cut_to:
                trim_part += f":end={cut_to}"
            trim_part += f",setpts=PTS-STARTPTS[{layer_pad}_raw]"
            filter_chains.append(trim_part)

            scale_trans = f"[{layer_pad}_raw]scale={width}:{height}[{layer_pad}]"
            filter_chains.append(scale_trans)

            # Shift PTS để transition xuất hiện đúng thời điểm
            fps_fix = f"[{layer_pad}]setpts=PTS+{start_time}/TB[{layer_pad}_shifted]"
            filter_chains.append(fps_fix)

            # Enable transition video trong khoảng thời gian của nó
            enable_expr = f"enable='between(t,{start_time},{stop_time})'"
            next_pad = f"v_clip_{i}_trans_{overlay_idx}"
            overlay_cmd = f"{current_v_pad}[{layer_pad}_shifted]overlay=0:0:{enable_expr}[{next_pad}]"
            filter_chains.append(overlay_cmd)
            current_v_pad = f"[{next_pad}]"
            overlay_idx += 1

        # --- 5. KẾT THÚC CLIP ---
        if not has_audio:
            dur_str = f":d={segment_duration}" if segment_duration else ""
            silence_cmd = f"anullsrc=cl=stereo:r=44100{dur_str}[{out_a}]"
            filter_chains.append(silence_cmd)

        filter_chains.append(f"{current_v_pad}setsar=1[{out_v}]")
        concat_segments.append(f"[{out_v}]")
        concat_segments.append(f"[{out_a}]")

    # ==========================================
    # CONCAT & MIX
    # ==========================================
    n_clips = len(json_data['clips'])
    concat_cmd = "".join(concat_segments) + f"concat=n={n_clips}:v=1:a=1[main_video][main_audio_raw]"
    filter_chains.append(concat_cmd)

    audio_tracks = json_data.get('audioTracks', [])
    mix_inputs = ["[main_audio_raw]"]

    for k, track in enumerate(audio_tracks):
        path = track['path']
        idx = get_input_index(path, input_map, inputs_list)
        start = track.get('start', 0)
        cut_from = track.get('cutFrom', 0)
        cut_to = track.get('cutTo')
        mix_vol = track.get('mixVolume', 1)

        track_pad = f"track_{k}"
        delayed_pad = f"track_{k}_delayed"

        cmd = f"[{idx}:a]atrim=start={cut_from}"
        if cut_to:
            cmd += f":end={cut_to}"
        cmd += f",asetpts=PTS-STARTPTS,volume={mix_vol}[{track_pad}]"
        filter_chains.append(cmd)

        delay_ms = int(start * 1000)
        delay_cmd = f"[{track_pad}]adelay={delay_ms}|{delay_ms}[{delayed_pad}]"
        filter_chains.append(delay_cmd)
        mix_inputs.append(f"[{delayed_pad}]")

    if len(mix_inputs) > 1:
        mix_cmd = "".join(
            mix_inputs) + f"amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0[final_audio]"
        filter_chains.append(mix_cmd)
    else:
        filter_chains.append(f"[main_audio_raw]acopy[final_audio]")

    # ==========================================
    # EXECUTE
    # ==========================================
    cmd_args = [FFMPEG_EXEC, "-y"]
    for inp in inputs_list:
        cmd_args.extend(["-i", inp])

    cmd_args.extend(["-filter_complex", ";".join(filter_chains)])
    cmd_args.extend(["-map", "[main_video]", "-map", "[final_audio]"])
    cmd_args.extend([
        "-c:v", "h264_nvenc",
        "-preset", "p6",
        "-tune", "hq",
        "-rc", "vbr",
        "-cq", "23",
        "-b:v", "0",
        "-c:a", "aac",
        "-b:a", "192k",
        "-r", str(fps),
        out_path
    ])
    
    try:
        subprocess.run(cmd_args, check=True)
        messagebox.showinfo("Hoàn thành", f"Render video thành công!\n\nĐường dẫn:\n{out_path}")
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Lỗi render", f"FFmpeg render thất bại!\n\nMã lỗi: {e.returncode}\n\nVui lòng kiểm tra console để xem chi tiết lỗi.")
        raise

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
