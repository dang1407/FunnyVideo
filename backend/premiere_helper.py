"""
Premiere Helper - Sinh file để import vào Adobe Premiere Pro

Hỗ trợ 2 phương pháp:
1. FCP XML (Final Cut Pro XML) - Premiere có thể import trực tiếp (XMEML version 4)
2. ExtendScript (.jsx) - Tự động hóa hoàn toàn trong Premiere

Sử dụng:
    from premiere_helper import generate_premiere_xml, generate_premiere_jsx, export_premiere_xml
    
    # Phương pháp 1: Sinh FCP XML từ config JSON
    generate_premiere_xml("config.json", "output.xml")
    
    # Phương pháp 2: Sinh FCP XML trực tiếp từ clips
    export_premiere_xml(channel_name, config, selected_clips, output_xml_path)
    
    # Phương pháp 3: Sinh ExtendScript
    generate_premiere_jsx("config.json", "import_and_render.jsx")
"""

import json
import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
import uuid
from datetime import datetime
import urllib.parse
import subprocess
from consts import CODEC_NAME
from helper import get_pixel_aspect_ratio, get_video_info

PPRO_TICKS_PER_SECOND = 254_016_000_000

def seconds_to_ticks(seconds: float) -> int:
    return int(seconds * PPRO_TICKS_PER_SECOND)

def frames_to_ticks(frames: int, fps: float) -> int:
    return int(frames / fps * PPRO_TICKS_PER_SECOND)


def encode_path_for_premiere(path):
    """
    Encode đường dẫn file thành URL hợp lệ cho Premiere Pro XMEML.
    
    Premiere yêu cầu định dạng: file:///D%3a/FunnyVideo//Main_clips//file.mp4
    - Sử dụng file:/// (3 dấu /)
    - Dấu : trong ổ đĩa phải được encode thành %3a
    - 1 dấu / sau ổ đĩa, rồi // giữa các folder tiếp theo
    - Các ký tự đặc biệt như tiếng Việt, khoảng trắng được encode
    """
    # Chuẩn hóa đường dẫn
    normalized_path = os.path.normpath(path).replace("\\", "/")
    
    # Tách ổ đĩa và đường dẫn (ví dụ: D:/path -> D, /path)
    if len(normalized_path) >= 2 and normalized_path[1] == ':':
        drive = normalized_path[0].upper()
        rest_path = normalized_path[2:]  # Bỏ qua ":"
    else:
        drive = ""
        rest_path = normalized_path
    
    # Tách các phần của đường dẫn
    parts = rest_path.split('/')
    
    # Encode từng phần (tên file/folder) riêng biệt
    encoded_parts = []
    for part in parts:
        if part:  # Bỏ qua phần rỗng
            # Encode tên file/folder, giữ lại các ký tự an toàn
            encoded_part = urllib.parse.quote(part, safe='')
            encoded_parts.append(encoded_part)
    
    # Join: phần đầu dùng /, các phần sau dùng //
    # Ví dụ: /FunnyVideo//Main_clips//animals//file.mp4
    if len(encoded_parts) > 0:
        encoded_path = '/' + encoded_parts[0]
        if len(encoded_parts) > 1:
            encoded_path += '/' + '/'.join(encoded_parts[1:])
    else:
        encoded_path = ''
    # Xây dựng URL với ổ đĩa được encode
    if drive:
        return f"file://localhost/{drive}%3a{encoded_path}"
    else:
        return f"file://{encoded_path}"


def encode_path_for_xml(path):
    """Alias cho backward compatibility"""
    return encode_path_for_premiere(path)


def get_duration_frames(duration_seconds, fps):
    """Chuyển đổi giây sang số frames"""
    return int(duration_seconds * fps)


def get_timecode(frames, fps):
    """Chuyển đổi frames sang timecode HH:MM:SS:FF"""
    total_seconds = frames / fps
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    frame = int(frames % fps)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frame:02d}"


def prettify_xml(elem):
    """Định dạng XML đẹp với indentation"""
    rough_string = ET.tostring(elem, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")

def add_group(outputs_elem, group_index, channel_index):
    group = ET.SubElement(outputs_elem, "group")

    ET.SubElement(group, "index").text = str(group_index)
    ET.SubElement(group, "numchannels").text = "1"
    ET.SubElement(group, "downmix").text = "0"

    channel = ET.SubElement(group, "channel")
    ET.SubElement(channel, "index").text = str(channel_index)

def add_audio(parent_ele, channel_index, channel_count):
    aud = ET.SubElement(parent_ele, 'audio')
    sample = ET.SubElement(aud, 'samplecharacteristics')
    ET.SubElement(sample, 'depth').text = '16'
    ET.SubElement(sample, 'samplerate').text = '48000'

    ET.SubElement(aud, 'channelcount').text = f'{channel_count}'
    # ET.SubElement(aud, 'layout').text = 'stereo'

    # audiochannel = ET.SubElement(aud, 'audiochannel')
    # ET.SubElement(audiochannel, 'sourcechannel').text = F'{channel_index}'
    # ET.SubElement(audiochannel, 'channellabel').text = 'left'

def add_text(parent, tag, text):
    el = ET.SubElement(parent, tag)
    el.text = str(text)
    return el

def add_links(parent, video_clip_id, video_track_index, audio_clip_id_1, audio1_track_index, audio_clip_id_2, audio2_track_index):
    # Link video
    link_video = ET.SubElement(parent, 'link')
    ET.SubElement(link_video, 'linkclipref').text = video_clip_id
    ET.SubElement(link_video, 'mediatype').text = 'video'
    ET.SubElement(link_video, 'trackindex').text = str(video_track_index)
    ET.SubElement(link_video, 'clipindex').text = '1'

    # Link audio 1
    link_audio_1 = ET.SubElement(parent, 'link')
    ET.SubElement(link_audio_1, 'linkclipref').text = audio_clip_id_1
    ET.SubElement(link_audio_1, 'mediatype').text = 'audio'
    ET.SubElement(link_audio_1, 'trackindex').text = str(audio1_track_index)
    ET.SubElement(link_audio_1, 'clipindex').text = '1'
    ET.SubElement(link_audio_1, 'groupindex').text = '1'

    # Link audio 2
    link_audio_2 = ET.SubElement(parent, 'link')
    ET.SubElement(link_audio_2, 'linkclipref').text = audio_clip_id_2
    ET.SubElement(link_audio_2, 'mediatype').text = 'audio'
    ET.SubElement(link_audio_2, 'trackindex').text = str(audio2_track_index)
    ET.SubElement(link_audio_2, 'clipindex').text = '1'
    ET.SubElement(link_audio_2, 'groupindex').text = '1'

def create_parameter(parent, pid, name, value=None,
                     valuemin=None, valuemax=None,
                     horiz=None, vert=None):
    param = ET.SubElement(parent, "parameter", {"authoringApp": "PremierePro"})
    add_text(param, "parameterid", pid)
    add_text(param, "name", name)

    if valuemin is not None:
        add_text(param, "valuemin", valuemin)
    if valuemax is not None:
        add_text(param, "valuemax", valuemax)

    if value is not None:
        add_text(param, "value", value)
    else:
        value_el = ET.SubElement(param, "value")
        if horiz is not None:
            add_text(value_el, "horiz", horiz)
        if vert is not None:
            add_text(value_el, "vert", vert)

    return param

# Scale height
def create_basic_motion_filter(parent, output_size, video_size, pixel_aspect_ratio):
    filter_el = ET.SubElement(parent, "filter")
    effect = ET.SubElement(filter_el, "effect")

    add_text(effect, "name", "Basic Motion")
    add_text(effect, "effectid", "basic")
    add_text(effect, "effectcategory", "motion")
    add_text(effect, "effecttype", "motion")
    add_text(effect, "mediatype", "video")
    add_text(effect, "pproBypass", "false")

    if pixel_aspect_ratio:
        create_parameter(effect, "scale", "Scale",
                     value=f"{round((output_size/(video_size * pixel_aspect_ratio)) * 100, 1)}", valuemin="0", valuemax="1000")
    else: 
        create_parameter(effect, "scale", "Scale",
                     value=f"{round((output_size/video_size) * 100, 1)}", valuemin="0", valuemax="1000")
    create_parameter(effect, "rotation", "Rotation",
                     value="0", valuemin="-8640", valuemax="8640")

    create_parameter(effect, "center", "Center",
                     horiz="0", vert="0")

    create_parameter(effect, "centerOffset", "Anchor Point",
                     horiz="0", vert="0")

    create_parameter(effect, "antiflicker", "Anti-flicker Filter",
                     value="0", valuemin="0.0", valuemax="1.0")

    return filter_el


def create_gaussian_blur_filter(parent, blur):
    filter_el = ET.SubElement(parent, "filter")
    effect = ET.SubElement(filter_el, "effect")

    add_text(effect, "name", "Gaussian Blur")
    add_text(effect, "effectid", "Gaussian Blur")
    add_text(effect, "effectcategory", "Blur")
    add_text(effect, "effecttype", "motion")
    add_text(effect, "mediatype", "video")
    add_text(effect, "pproBypass", "false")
    blur_value = blur
    if(0 <= blur and blur <= 1):
        blur_value = blur * 100

    create_parameter(effect, "radius", "Radius",
                     value=str(blur_value), valuemin="0", valuemax="100")

    return filter_el

def create_distort_filter(parent, output_width, output_height, video_width, video_height):
    filter_el = ET.SubElement(parent, "filter")
    effect = ET.SubElement(filter_el, "effect")

    add_text(effect, "name", "Distort")
    add_text(effect, "effectid", "deformation")
    add_text(effect, "effectcategory", "motion")
    add_text(effect, "effecttype", "motion")
    add_text(effect, "mediatype", "video")

    scale_width = output_width/video_width
    scale_height = output_height/video_height
    disort_value = round((1 - (scale_width / scale_height))*100, 1)
    create_parameter(effect, "aspect", "Aspect",
                     value=disort_value,
                     valuemin="-10000", valuemax="10000")

    return filter_el

def set_audio_track_default_att(track):
    audio_track_attrs = {
        'TL.SQTrackAudioKeyframeStyle': '0',
        'TL.SQTrackShy': '0',
        'TL.SQTrackExpandedHeight': '25',
        'TL.SQTrackExpanded': '0',
        'MZ.TrackTargeted': '1',
        'PannerCurrentValue': '0.5',
        'PannerIsInverted': 'true',
        'PannerStartKeyframe': '-91445760000000000,0.5,0,0,0,0,0,0',
        'PannerName': 'Balance',
        'premiereTrackType': 'Stereo'
    }
    for k, v in audio_track_attrs.items():
        track.set(k, v)

def set_video_track_default_att(track):
    audio_track_attrs = {
        'TL.SQTrackShy': '0',
        'TL.SQTrackExpandedHeight': '25',
        'TL.SQTrackExpanded': '0',
        'MZ.TrackTargeted': '0',
    }
    for k, v in audio_track_attrs.items():
        track.set(k, v)

def create_audio_sub_ele(audio_clipitem, master_clip_text, path, clip_duration, fps, current_frame, cut_from, cut_to, media_files):
    master_clip_tracka1 = ET.SubElement(audio_clipitem, 'masterclipid')
    master_clip_tracka1.text = master_clip_text

    aci_name = ET.SubElement(audio_clipitem, 'name')
    aci_name.text = os.path.basename(path)
    
    aci_duration = ET.SubElement(audio_clipitem, 'duration')
    aci_duration.text = str(get_duration_frames(clip_duration, fps))
    
    aci_rate = ET.SubElement(audio_clipitem, 'rate')
    aci_timebase = ET.SubElement(aci_rate, 'timebase')
    aci_timebase.text = str(fps)
    
    aci_start = ET.SubElement(audio_clipitem, 'start')
    aci_start.text = str(current_frame)
    
    aci_end = ET.SubElement(audio_clipitem, 'end')
    aci_end.text = str(current_frame + get_duration_frames(clip_duration, fps))
    
    aci_in = ET.SubElement(audio_clipitem, 'in')
    aci_in.text = str(get_duration_frames(cut_from, fps))
    
    aci_out = ET.SubElement(audio_clipitem, 'out')
    aci_out.text = str(get_duration_frames(cut_to, fps))
    
    aci_file = ET.SubElement(audio_clipitem, 'file')
    aci_file.set('id', media_files[path])

def generate_premiere_xml(config_path, output_xml_path=None):
    """
    Sinh file FCP XML từ config JSON
    
    Adobe Premiere Pro có thể import file này qua:
    File -> Import -> chọn file .xml
    
    Args:
        config_path: Đường dẫn file JSON config
        output_xml_path: Đường dẫn file XML output (mặc định cùng tên với .xml)
    
    Returns:
        Đường dẫn file XML đã tạo
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    if output_xml_path is None:
        output_xml_path = config_path.replace('.json', '.xml')
    
    width = config.get('width', 1920)
    height = config.get('height', 1080)
    fps = config.get('fps', 25)
    clips = config.get('clips', [])
    
    # Tạo root element
    xmeml = ET.Element('xmeml', version="4")
    
    # Tạo sequence
    sequence = ET.SubElement(xmeml, 'sequence')
    sequence.set('id', f"sequence-{uuid.uuid4().hex[:8]}")

    # sequence uuid 
    sequence_uuid = ET.SubElement(sequence, 'uuid')
    sequence_uuid.text = str(uuid.uuid4())
    

    # Duration - tính tổng duration
    total_duration = 0
    for clip in clips:
        clip_duration = clip.get('duration', 0)
        if not clip_duration:
            video_layer = next((l for l in clip.get('layers', []) if l['type'] == 'video'), None)
            if video_layer:
                cut_from = video_layer.get('cutFrom', 0)
                cut_to = video_layer.get('cutTo', 0)
                clip_duration = cut_to - cut_from if cut_to else 0
        total_duration += clip_duration
    
    duration_elem = ET.SubElement(sequence, 'duration')
    duration_elem.text = str(get_duration_frames(total_duration, fps))
    
    # Rate
    rate = ET.SubElement(sequence, 'rate')
    timebase = ET.SubElement(rate, 'timebase')
    timebase.text = str(fps)
    ntsc = ET.SubElement(rate, 'ntsc')
    ntsc.text = "FALSE"
    
    # Sequence name
    seq_name = ET.SubElement(sequence, 'name')
    seq_name.text = os.path.splitext(os.path.basename(config_path))[0]
    

    # Media
    media = ET.SubElement(sequence, 'media')
    
    # Video track
    video = ET.SubElement(media, 'video')
    video_format = ET.SubElement(video, 'format')
    sample_characteristics = ET.SubElement(video_format, 'samplecharacteristics')
    sc_rate = ET.SubElement(sample_characteristics, 'rate')
    sc_timebase = ET.SubElement(sc_rate, 'timebase')
    sc_timebase.text = str(fps)
    ET.SubElement(sc_rate, 'ntsc').text = 'FALSE'

    codec = ET.SubElement(sample_characteristics, 'codec')
    ET.SubElement(codec, 'name').text = CODEC_NAME
    appspecificdata = ET.SubElement(codec, 'appspecificdata')
    ET.SubElement(appspecificdata, 'appname').text = 'Final Cut Pro'
    ET.SubElement(appspecificdata, 'appmanufacturer').text = 'Apple Inc.'
    ET.SubElement(appspecificdata, 'appversion').text = '7.0'

    data = ET.SubElement(appspecificdata, 'data')
    qtcodec = ET.SubElement(data, 'qtcodec')

    ET.SubElement(qtcodec, 'codecname').text = CODEC_NAME
    ET.SubElement(qtcodec, 'codectypename').text = CODEC_NAME
    ET.SubElement(qtcodec, 'codectypecode').text = 'apcn'
    ET.SubElement(qtcodec, 'codecvendorcode').text = 'appl'
    ET.SubElement(qtcodec, 'spatialquality').text = '1024'
    ET.SubElement(qtcodec, 'temporalquality').text = '0'
    ET.SubElement(qtcodec, 'keyframerate').text = '0'
    ET.SubElement(qtcodec, 'datarate').text = '0'
    sc_width = ET.SubElement(sample_characteristics, 'width')
    sc_width.text = str(width)
    sc_height = ET.SubElement(sample_characteristics, 'height')
    sc_height.text = str(height)
    ET.SubElement(sample_characteristics, 'anamorphic').text = 'FALSE'
    ET.SubElement(sample_characteristics, 'pixelaspectratio').text = 'square'
    ET.SubElement(sample_characteristics, 'fielddominance').text = 'none'
    ET.SubElement(sample_characteristics, 'colordepth').text = '24'

    # Video Track 1 (blur video background)
    track_v1 = ET.SubElement(video, 'track')
    set_video_track_default_att(track_v1)
    # Video Track 2 (main video)
    track_v2 = ET.SubElement(video, 'track')
    
    # Overlay tracks (phải khai báo trong video section)
    track_v3 = ET.SubElement(video, 'track')  # Logo track
    track_v4 = ET.SubElement(video, 'track')  # Transition track
    
    # Audio tracks
    audio = ET.SubElement(media, 'audio')
    ET.SubElement(audio, 'numOutputChannels').text = '2'
    audio_format = ET.SubElement(audio, 'format')
    outputs = ET.SubElement(audio, 'outputs')
    add_group(outputs, 1, 1)
    add_group(outputs, 2, 2)
    audio_sample = ET.SubElement(audio_format, 'samplecharacteristics')
    audio_depth = ET.SubElement(audio_sample, 'depth')
    audio_depth.text = "16"
    audio_samplerate = ET.SubElement(audio_sample, 'samplerate')
    audio_samplerate.text = "48000"
    
    # Audio Track 1
    track_a1 = ET.SubElement(audio, 'track')
    track_a2 = ET.SubElement(audio, 'track')
    track_a3 = ET.SubElement(audio, 'track')
    track_a4 = ET.SubElement(audio, 'track')
    # set_audio_track_default_att(track_a1)
    # set_audio_track_default_att(track_a2)
    # Thu thập tất cả media files và đánh dấu đã định nghĩa chưa
    media_files = {}  # path -> file_id
    defined_files = set()  # Các file đã được định nghĩa đầy đủ
    current_frame = 0
    
    def create_file_element(parent, path, file_id, video_width, video_height, duration, is_logo = False, pixel_aspect_ratio = None):
        """Tạo file element - đầy đủ nếu lần đầu, chỉ id nếu đã định nghĩa"""
        file_elem = ET.SubElement(parent, 'file')
        file_elem.set('id', file_id)
        
        if path not in defined_files:
            # Lần đầu tiên - định nghĩa đầy đủ
            file_name = ET.SubElement(file_elem, 'name')
            file_name.text = os.path.basename(path)
            pathurl = ET.SubElement(file_elem, 'pathurl')
            pathurl.text = encode_path_for_xml(path)
            
            file_rate = ET.SubElement(file_elem, 'rate')
            file_time_base = ET.SubElement(file_rate, 'timebase')
            file_time_base.text = str(fps) 
            ET.SubElement(file_rate, 'ntsc').text = 'FALSE'
            ET.SubElement(file_elem, 'duration').text = str(duration)
            timecode = ET.SubElement(file_elem, 'timecode')

            rate = ET.SubElement(timecode, 'rate')
            ET.SubElement(rate, 'timebase').text = str(fps)
            ET.SubElement(rate, 'ntsc').text = 'FALSE'
            ET.SubElement(timecode, 'string').text = '00:00:00:00'
            ET.SubElement(timecode, 'frame').text = '0'
            ET.SubElement(timecode, 'displayformat').text = 'NDF'
            # Thêm media info cơ bản
            media_elem = ET.SubElement(file_elem, 'media')

            vid = ET.SubElement(media_elem, 'video')
            sample = ET.SubElement(vid, 'samplecharacteristics')
            rate = ET.SubElement(sample, 'rate')
            ET.SubElement(rate, 'timebase').text = str(fps)
            ET.SubElement(rate, 'ntsc').text = 'FALSE'

            ET.SubElement(sample, 'width').text = str(video_width)
            ET.SubElement(sample, 'height').text = str(video_height)
            ET.SubElement(sample, 'anamorphic').text = 'FALSE'
            ET.SubElement(sample, 'pixelaspectratio').text = str(pixel_aspect_ratio) if pixel_aspect_ratio else 'square'
            ET.SubElement(sample, 'fielddominance').text = 'none'
            if is_logo != True:
                add_audio(media_elem, 1, 2)
            # if is_main_clip == True:
            #     add_audio(media_elem, 2, 1)
            defined_files.add(path)
        
        return file_elem

    def create_log_and_color_element(parent):
        logginginfo = ET.SubElement(parent, "logginginfo")
        for tag in [
            "description",
            "scene",
            "shottake",
            "lognote",
            "good",
            "originalvideofilename",
            "originalaudiofilename"
        ]:
            ET.SubElement(logginginfo, tag)

        # ----- colorinfo -----
        colorinfo = ET.SubElement(parent, "colorinfo")
        for tag in [
            "lut",
            "lut1",
            "asc_sop",
            "asc_sat",
            "lut2"
        ]:
            ET.SubElement(colorinfo, tag)

        # ----- labels -----
        labels = ET.SubElement(parent, "labels")
        label2 = ET.SubElement(labels, "label2")
        label2.text = "Iris"

    for clip_idx, clip in enumerate(clips):
        layers = clip.get('layers', [])
        clip_duration = clip.get('duration', 0)
        
        # Tìm main video/fill-color layer
        video_layer = next((l for l in layers if l['type'] == 'video'), None)
        fill_color = next((l for l in layers if l['type'] == 'fill-color'), None)
        track_v1_clipitem_id = f"clipitem-{clip_idx*10 + 1}"
        track_v2_clipitem_id = f"clipitem-{clip_idx*10 + 2}"
        tracka1_clip_item_id = f"audio-clipitem-{clip_idx*10 + 1}"
        tracka2_clip_item_id = f"audio-clipitem-{clip_idx*10 + 2}"
        tracka3_clip_item_id = f"audio-clipitem-{clip_idx*10 + 3}"
        tracka4_clip_item_id = f"audio-clipitem-{clip_idx*10 + 4}"
        tracka5_clip_item_id = f"audio-clipitem-{clip_idx*10 + 5}"
        
        if video_layer:
            path = video_layer['path']
            blur = video_layer['blur']
            thumb_duration, thumb_path, video_width, video_height = get_video_info(path)
            pixel_aspect_ratio = get_pixel_aspect_ratio(path)
            cut_from = video_layer.get('cutFrom', 0)
            cut_to = video_layer.get('cutTo', 0)
            clip_duration = cut_to - cut_from if cut_to else 0
            
            # Thêm vào media files
            if path not in media_files:
                media_files[path] = f"file-{len(media_files) + 1}"
           
            master_clip_text = f'masterclip-{clip_idx}'
            
            # Tạo clip item cho video mờ chạy nền phía dưới
            
            bg_blur_video = ET.SubElement(track_v1, 'clipitem')
            bg_blur_video.set('id', f"{track_v1_clipitem_id}")

            ET.SubElement(bg_blur_video, 'masterclipid').text = master_clip_text
            ET.SubElement(bg_blur_video, 'name').text = os.path.basename(path)
            ET.SubElement(bg_blur_video, 'enabled').text = 'TRUE'
            
            ci_duration_frame_float = get_duration_frames(clip_duration, fps)
            ET.SubElement(bg_blur_video, 'duration').text = str(ci_duration_frame_float)

            ci_rate_trackv1 = ET.SubElement(bg_blur_video, 'rate')
            ET.SubElement(ci_rate_trackv1, 'timebase').text = str(fps)
            ET.SubElement(ci_rate_trackv1, 'ntsc').text = 'FALSE'
            ET.SubElement(bg_blur_video, 'start').text = str(current_frame)
            ET.SubElement(bg_blur_video, 'end').text = str(current_frame + ci_duration_frame_float)
            ET.SubElement(bg_blur_video, 'in').text = str(get_duration_frames(cut_from, fps))
            ET.SubElement(bg_blur_video, 'out').text = str(get_duration_frames(cut_to, fps))
            ET.SubElement(bg_blur_video, 'pproTicksIn').text = '0'
            ET.SubElement(bg_blur_video, 'pproTicksOut').text = str(frames_to_ticks(ci_duration_frame_float, fps))
            ET.SubElement(bg_blur_video, 'alphatype').text = 'none'
            ET.SubElement(bg_blur_video, 'pixelaspectratio').text = 'square'
            ET.SubElement(bg_blur_video, 'anamorphic').text = 'FALSE'
            # File reference - sử dụng helper function
            create_file_element(bg_blur_video, path, media_files[path], video_width, video_height, ci_duration_frame_float, )
            # Filter
            create_basic_motion_filter(bg_blur_video, width, video_width, pixel_aspect_ratio)

            # create_distort_filter(bg_blur_video, width, height, video_width, video_height)
            create_gaussian_blur_filter(bg_blur_video, blur)
            # Log and color
            create_log_and_color_element(bg_blur_video)

            # Tạo clip item cho video chính trong track
            clipitem = ET.SubElement(track_v2, 'clipitem')
            clipitem.set('id', track_v2_clipitem_id)
            
            master_clip_trackv2 = ET.SubElement(clipitem, 'masterclipid')
            master_clip_trackv2.text = master_clip_text

            ci_name = ET.SubElement(clipitem, 'name')
            ci_name.text = os.path.basename(path)

            ET.SubElement(clipitem, 'enabled').text = 'TRUE'
            
            ci_duration_frame_float = get_duration_frames(clip_duration, fps)
            ci_duration = ET.SubElement(clipitem, 'duration')
            ci_duration.text = str(ci_duration_frame_float)


            ci_rate = ET.SubElement(clipitem, 'rate')
            ci_timebase = ET.SubElement(ci_rate, 'timebase')
            ci_timebase.text = str(fps)
            ET.SubElement(ci_rate, 'ntsc').text = 'FALSE'
            
            ci_start = ET.SubElement(clipitem, 'start')
            ci_start.text = str(current_frame)
            
            ci_end = ET.SubElement(clipitem, 'end')
            ci_end.text = str(current_frame + ci_duration_frame_float)
            
            ci_in = ET.SubElement(clipitem, 'in')
            ci_in.text = str(get_duration_frames(cut_from, fps))
            
            ci_out = ET.SubElement(clipitem, 'out')
            ci_out.text = str(get_duration_frames(cut_to, fps))
            
            ET.SubElement(clipitem, 'pproTicksIn').text = '0'
            ET.SubElement(clipitem, 'pproTicksOut').text = str(frames_to_ticks(ci_duration_frame_float, fps))
            ET.SubElement(clipitem, 'alphatype').text = 'none'
            ET.SubElement(clipitem, 'pixelaspectratio').text = 'square'
            ET.SubElement(clipitem, 'anamorphic').text = 'FALSE'
            # File reference - sử dụng helper function
            create_file_element(clipitem, path, media_files[path], video_width, video_height, ci_duration_frame_float)
            # Filter
            create_basic_motion_filter(clipitem, height, video_height, None)            
            add_links(clipitem, track_v2_clipitem_id, 1, tracka1_clip_item_id, 2, tracka2_clip_item_id, 3)
            # Log and color
            create_log_and_color_element(clipitem)
            # # filter
            # ET.SubElement(clipitem, 'enabled').text = 'TRUE'
            # ET.SubElement(clipitem, 'locked').text = 'FALSE'

            
            # Audio clip item (nếu keep audio)
            audio_clipitem_a1 = ET.SubElement(track_a1, 'clipitem')
            audio_clipitem_a1.set('id', tracka1_clip_item_id)
            create_audio_sub_ele(audio_clipitem_a1, master_clip_text, path, clip_duration, fps, current_frame, cut_from, cut_to, media_files)

            audio_clipitem_a2 = ET.SubElement(track_a2, 'clipitem')
            audio_clipitem_a2.set('id', tracka2_clip_item_id)
            create_audio_sub_ele(audio_clipitem_a2, master_clip_text, path, clip_duration, fps, current_frame, cut_from, cut_to, media_files)

            
            # Thêm link clip background và 2 audio với nhau 
            add_links(audio_clipitem_a1, track_v2_clipitem_id, 1, tracka1_clip_item_id, 2, tracka2_clip_item_id, 3)
            add_links(audio_clipitem_a2, track_v2_clipitem_id, 1, tracka1_clip_item_id, 2, tracka2_clip_item_id, 3)
            
        elif fill_color:
            clip_duration = clip.get('duration', 0.1)
        
        # Xử lý overlay layers (logo, transition)
        for layer in layers:
            if layer['type'] == 'image-overlay':
                # Logo
                logo_path = layer['path']
                if logo_path not in media_files:
                    media_files[logo_path] = f"file-{len(media_files) + 1}"
                
                logo_item = ET.SubElement(track_v3, 'clipitem')
                logo_item.set('id', f"logo-{clip_idx}")
                
                logo_name = ET.SubElement(logo_item, 'name')
                logo_name.text = os.path.basename(logo_path)
                
                logo_duration = ET.SubElement(logo_item, 'duration')
                logo_duration.text = str(get_duration_frames(clip_duration, fps))
                
                logo_start = ET.SubElement(logo_item, 'start')
                logo_start.text = str(current_frame)
                
                logo_end = ET.SubElement(logo_item, 'end')
                logo_end.text = str(current_frame + get_duration_frames(clip_duration, fps))

                ET.SubElement(logo_item, 'in').text = '100000'
                ET.SubElement(logo_item, 'out').text = f'{100000 + clip_duration}'
                
                # File reference - sử dụng helper function
                create_file_element(logo_item, logo_path, media_files[logo_path], width, height, total_duration, True)

                create_log_and_color_element(logo_item)
            
            elif layer['type'] == 'video' and layer != video_layer:
                # Transition video
                trans_path = layer['path']
                trans_start = layer.get('start', 0)
                trans_stop = layer.get('stop', 0)
                trans_cut_from = layer.get('cutFrom', 0)
                trans_cut_to = layer.get('cutTo', 0)
                trans_item_id = f"trans-{clip_idx*10+1}"
                master_clip_trans = f"master-clip-trans-{clip_idx*10+1}"
                trans_duration_frame = get_duration_frames(trans_stop - trans_start, fps)
                if trans_path not in media_files:
                    media_files[trans_path] = f"file-{len(media_files) + 1}"
                
                trans_item = ET.SubElement(track_v4, 'clipitem')
                trans_item.set('id', trans_item_id)

                trans_master_clip_id = ET.SubElement(trans_item, 'masterclipid')
                trans_master_clip_id.text = master_clip_trans
                
                trans_name = ET.SubElement(trans_item, 'name')
                trans_name.text = os.path.basename(trans_path)
                
                trans_duration = ET.SubElement(trans_item, 'duration')
                trans_duration.text = str(trans_duration_frame)
                
                trans_start_elem = ET.SubElement(trans_item, 'start')
                trans_start_frame = current_frame + get_duration_frames(trans_start, fps)
                trans_start_elem.text = str(trans_start_frame)
                
                trans_end = ET.SubElement(trans_item, 'end')
                trans_end_frame = current_frame + get_duration_frames(trans_stop, fps)
                trans_end.text = str(trans_end_frame)
                
                trans_in = ET.SubElement(trans_item, 'in')
                trans_in.text = str(get_duration_frames(trans_cut_from, fps))
                
                trans_out = ET.SubElement(trans_item, 'out')
                trans_out.text = str(get_duration_frames(trans_cut_to, fps))

                ET.SubElement(trans_item, 'pproTicksIn').text = '0'
                ET.SubElement(trans_item, 'pproTicksOut').text = str(frames_to_ticks(trans_duration_frame, fps))

                # File reference - sử dụng helper function
                create_file_element(trans_item, trans_path, media_files[trans_path], width, height, trans_duration_frame)
                # Thêm log
                create_log_and_color_element(trans_item)

                add_links(trans_item, trans_item_id, 4, tracka3_clip_item_id, 3, tracka4_clip_item_id, 4)
                # todo: add audio track for transition
                audio_clipitem_a3 = ET.SubElement(track_a3, 'clipitem')
                audio_clipitem_a3.set('id', tracka3_clip_item_id)
                create_audio_sub_ele(audio_clipitem_a3, master_clip_trans, trans_path, trans_stop - trans_start, fps, trans_start_frame, trans_cut_from, trans_cut_to, media_files)
                add_links(audio_clipitem_a3, trans_item_id, 4, tracka3_clip_item_id, 3, tracka4_clip_item_id, 4)

                audio_clipitem_a4 = ET.SubElement(track_a4, 'clipitem')
                audio_clipitem_a4.set('id', tracka4_clip_item_id)
                create_audio_sub_ele(audio_clipitem_a4, master_clip_trans, trans_path, trans_stop - trans_start, fps, trans_start_frame, trans_cut_from, trans_cut_to, media_files)
                add_links(audio_clipitem_a4, trans_item_id, 4, tracka3_clip_item_id, 3, tracka4_clip_item_id, 4)
        
        current_frame += get_duration_frames(clip_duration, fps)
    
    
    ET.SubElement(track_v1, 'enabled').text = 'TRUE'
    ET.SubElement(track_v1, 'locked').text = 'FALSE'

    ET.SubElement(track_v2, 'enabled').text = 'TRUE'
    ET.SubElement(track_v2, 'locked').text = 'FALSE'

    ET.SubElement(track_v3, 'enabled').text = 'TRUE'
    ET.SubElement(track_v3, 'locked').text = 'FALSE'

    ET.SubElement(track_v4, 'enabled').text = 'TRUE'
    ET.SubElement(track_v4, 'locked').text = 'FALSE'
    # Timecode
    timecode = ET.SubElement(sequence, 'timecode')
    tc_rate = ET.SubElement(timecode, 'rate')
    tc_timebase = ET.SubElement(tc_rate, 'timebase')
    tc_timebase.text = str(fps)
    tc_ntsc = ET.SubElement(tc_rate, 'ntsc')
    tc_ntsc.text = "FALSE"
    tc_string = ET.SubElement(timecode, 'string')
    tc_string.text = "00:00:00:00"
    tc_frame = ET.SubElement(timecode, 'frame')
    tc_frame.text = "0"
    tc_displayformat = ET.SubElement(timecode, 'displayformat')
    tc_displayformat.text = 'NDF'

    labels = ET.SubElement(sequence, 'labels')
    label2 = ET.SubElement(labels, 'label2')
    label2.text = 'Forest'

    # Logging info
    logginginfo = ET.SubElement(sequence, 'logginginfo')
    ET.SubElement(logginginfo, 'description').text = ''
    ET.SubElement(logginginfo, 'scene').text = ''
    ET.SubElement(logginginfo, 'shottake').text = ''
    ET.SubElement(logginginfo, 'lognote').text = ''
    ET.SubElement(logginginfo, 'good').text = ''
    ET.SubElement(logginginfo, 'originalvideofilename').text = ''
    ET.SubElement(logginginfo, 'originalaudiofilename').text = ''

    # Ghi file XML
    xml_string = prettify_xml(xmeml)
    
    # Thêm XML declaration với encoding
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n' + xml_string.split('\n', 1)[1]
    os.makedirs(os.path.dirname(output_xml_path), exist_ok=True)

    with open(output_xml_path, 'w', encoding='utf-8') as f:
        f.write(xml_string)
    
    print(f"✅ Đã tạo FCP XML: {output_xml_path}")
    print(f"   Import vào Premiere: File -> Import -> chọn file này")
    
    return output_xml_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python premiere_helper.py <config.json> [--xml|--jsx|--all]")
        print("")
        print("Options:")
        print("  --xml   Sinh FCP XML để import vào Premiere")
        print("  --jsx   Sinh ExtendScript để tự động hóa")
        print("  --all   Sinh cả XML và JSX (mặc định)")
        sys.exit(1)
    
    config_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "--all"
    
    if not os.path.exists(config_path):
        print(f"Error: File not found: {config_path}")
        sys.exit(1)
    
    if mode in ["--xml", "--all"]:
        generate_premiere_xml(config_path)
    
    # if mode in ["--jsx", "--all"]:
    #     generate_premiere_jsx(config_path)
    #     generate_premiere_batch_render_jsx(config_path)
    
    print("\n✅ Hoàn thành!")


# ==============================================================================
# HÀM EXPORT XML MỚI - XMEML VERSION 4 CHO ADOBE PREMIERE PRO
# ==============================================================================

def probe_video_info(video_path):
    """
    Lấy thông tin video bằng ffprobe: duration, width, height, fps
    """
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-show_entries", "format=duration",
            "-of", "json",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        
        # Lấy thông tin từ stream
        stream = data.get("streams", [{}])[0] if data.get("streams") else {}
        format_info = data.get("format", {})
        
        width = stream.get("width", 1920)
        height = stream.get("height", 1080)
        
        # Parse fps từ r_frame_rate (ví dụ: "30/1" hoặc "30000/1001")
        fps_str = stream.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(float, fps_str.split("/"))
            fps = num / den if den != 0 else 30
        else:
            fps = float(fps_str)
        
        # Lấy duration
        duration = float(stream.get("duration", 0) or format_info.get("duration", 0))
        
        return {
            "width": width,
            "height": height,
            "fps": fps,
            "duration": duration
        }
    except Exception as e:
        print(f"⚠️ Không thể probe video {video_path}: {e}")
        return {"width": 1920, "height": 1080, "fps": 30, "duration": 0}


def tc_to_frames(tc: str, fps: int) -> int:
    """HH:MM:SS:FF -> frames"""
    try:
        hh, mm, ss, ff = map(int, tc.split(":"))
        return (hh * 3600 + mm * 60 + ss) * fps + ff
    except:
        return 0


def frames_to_tc(frames: int, fps: int) -> str:
    """frames -> HH:MM:SS:FF"""
    total_seconds = frames // fps
    ff = frames % fps
    hh = total_seconds // 3600
    mm = (total_seconds % 3600) // 60
    ss = total_seconds % 60
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"




