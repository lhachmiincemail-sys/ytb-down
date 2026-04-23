import os
import re
import json
import sys
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ── Auto-detect ffmpeg ──────────────────
FFMPEG_PATH = None
FFMPEG_DIR = None
try:
    import imageio_ffmpeg
    path = imageio_ffmpeg.get_ffmpeg_exe()
    if os.path.exists(path):
        FFMPEG_PATH = path
        FFMPEG_DIR = os.path.dirname(path)
        std_ffmpeg = os.path.join(FFMPEG_DIR, 'ffmpeg.exe')
        if not os.path.exists(std_ffmpeg) and sys.platform == 'win32':
            import shutil
            shutil.copy(path, std_ffmpeg)
        print(f"[OK] ffmpeg verified: {FFMPEG_PATH}")
except Exception as e:
    print(f"[DEBUG] imageio-ffmpeg failed: {e}")

if not FFMPEG_PATH:
    import shutil
    sys_ffmpeg = shutil.which('ffmpeg')
    if sys_ffmpeg:
        FFMPEG_PATH = sys_ffmpeg
        FFMPEG_DIR = os.path.dirname(sys_ffmpeg)
        print(f"[OK] system ffmpeg found: {sys_ffmpeg}")

# Final fallback: check current dir
if not FFMPEG_PATH and os.path.exists('ffmpeg.exe'):
    FFMPEG_PATH = os.path.abspath('ffmpeg.exe')
    FFMPEG_DIR = os.path.dirname(FFMPEG_PATH)

print(f"Final FFMPEG_DIR: {FFMPEG_DIR}")

# ── Progress tracker ───────────────────────────────────────────────────────
progress_tracker = {}

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', '_', name)

def get_ydl_base_opts():
    """Base yt-dlp options shared by all requests."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_color': True,
        'noplaylist': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'tv', 'ios'],
                'skip': ['hls', 'dash']
            }
        },
        'check_formats': False,
        'force_ipv4': True,  # This is the magic fix for datacenter IPs!
    }
    
    # ── COOKIES LOGIC ──
    # البحث عن ملف cookies.txt في نفس مجلد السكربت
    cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
    if os.path.exists(cookies_path):
        opts['cookiefile'] = cookies_path
        print(f"[OK] Using cookies from: {cookies_path}")
    else:
        print("[INFO] No cookies.txt found. Running in guest mode.")

    if FFMPEG_DIR:
        opts['ffmpeg_location'] = FFMPEG_DIR
    return opts

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json or {}
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'الرجاء إدخال رابط يوتيوب'}), 400

    ydl_opts = get_ydl_base_opts()
    ydl_opts['extract_flat'] = False

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = info.get('formats', [])
        available = []
        height_map = {}

        for f in formats:
            height = f.get('height')
            vcodec = f.get('vcodec', 'none')
            if vcodec == 'none' or not height:
                continue

            acodec = f.get('acodec', 'none')
            has_audio = acodec != 'none'
            fsize = f.get('filesize') or f.get('filesize_approx') or 0

            if height not in height_map:
                height_map[height] = {
                    'format_id': f['format_id'],
                    'height': height,
                    'ext': f.get('ext', 'mp4'),
                    'filesize': fsize,
                    'has_audio': has_audio
                }
            else:
                prev = height_map[height]
                if not prev['has_audio'] and has_audio:
                    height_map[height] = {
                        'format_id': f['format_id'],
                        'height': height,
                        'ext': f.get('ext', 'mp4'),
                        'filesize': fsize,
                        'has_audio': True
                    }

        for height, entry in height_map.items():
            h = height
            if h >= 2160: label = "Ultra HD / 4K"
            elif h >= 1440: label = "Quad HD / 2K"
            elif h >= 1080: label = "Full HD (1080p)"
            elif h >= 720: label = "High Definition (720p)"
            elif h >= 480: label = "Standard (480p)"
            elif h >= 360: label = "SD Quality (360p)"
            else: label = f"{h}p"

            available.append({
                'format_id': entry['format_id'],
                'label': label,
                'height': h,
                'ext': entry['ext'],
                'filesize': entry['filesize'],
                'has_audio': entry['has_audio'],
                'type': 'video'
            })

        available.sort(key=lambda x: x['height'], reverse=True)
        available.append({
            'format_id': 'mp3',
            'label': 'MP3 (صوت فقط)',
            'height': 0,
            'ext': 'mp3',
            'filesize': 0,
            'has_audio': True,
            'type': 'audio'
        })

        return jsonify({
            'title': info.get('title', 'Unknown'),
            'thumbnail': info.get('thumbnail', ''),
            'duration': info.get('duration', 0),
            'uploader': info.get('uploader', ''),
            'view_count': info.get('view_count', 0),
            'formats': available
        })

    except Exception as e:
        error_msg = str(e)
        print(f"[DEBUG] Info Error: {error_msg}")
        
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
        has_cookies = os.path.exists(cookies_path)
        
        if "sign in to confirm" in error_msg.lower() or "bot" in error_msg.lower() or "403" in error_msg:
            if not has_cookies:
                error_msg = "❌ السيرفر لا يجد ملف cookies.txt. يرجى التأكد من رفعه في المجلد الرئيسي."
            else:
                error_msg = "⚠️ ملف cookies.txt موجود، لكن يوتيوب لا يزال يحظر الطلب. يرجى استخراج كوكيز جديدة (Fresh Cookies) وإعادة رفعها."
        
        return jsonify({'error': error_msg}), 500

def make_progress_hook(task_id):
    def hook(d):
        if d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            pct = (downloaded / total * 100) if total > 0 else 0
            pct_str = d.get('_percent_str', '').strip().replace('%', '')
            try: pct = float(pct_str) if pct_str else pct
            except: pass
            progress_tracker[task_id] = {
                'status': 'downloading',
                'percent': round(min(pct, 99), 1),
                'speed': d.get('_speed_str', '--'),
                'eta': d.get('_eta_str', '--')
            }
        elif d['status'] == 'finished':
            progress_tracker[task_id] = {'status': 'merging', 'percent': 99}
        elif d['status'] == 'error':
            progress_tracker[task_id] = {'status': 'error', 'percent': 0}
    return hook

@app.route('/api/download', methods=['POST'])
def download_video():
    data = request.json or {}
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    task_id = data.get('task_id', 'default')

    if not url: return jsonify({'error': 'الرجاء إدخال رابط يوتيوب'}), 400
    progress_tracker[task_id] = {'status': 'starting', 'percent': 0}

    try:
        base_opts = get_ydl_base_opts()
        base_opts['outtmpl'] = os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s')
        base_opts['progress_hooks'] = [make_progress_hook(task_id)]

        if format_id == 'mp3':
            ydl_opts = {
                **base_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            ydl_opts = {
                **base_opts,
                'format': f'{format_id}+bestaudio[ext=m4a]/{format_id}+bestaudio/{format_id}/best',
                'merge_output_format': 'mp4',
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if format_id == 'mp3':
                filename = os.path.splitext(filename)[0] + '.mp3'
            elif not filename.endswith('.mp4'):
                filename = os.path.splitext(filename)[0] + '.mp4'

        if not os.path.exists(filename):
            files = [os.path.join(DOWNLOAD_DIR, f) for f in os.listdir(DOWNLOAD_DIR)]
            if files: filename = max(files, key=os.path.getmtime)

        progress_tracker[task_id] = {
            'status': 'ready',
            'percent': 100,
            'filename': os.path.basename(filename)
        }
        return jsonify({'success': True, 'filename': os.path.basename(filename), 'task_id': task_id})

    except Exception as e:
        error_msg = str(e)
        print(f"[DEBUG] Download Error: {error_msg}")
        
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
        has_cookies = os.path.exists(cookies_path)
        
        if "sign in to confirm" in error_msg.lower() or "bot" in error_msg.lower() or "403" in error_msg:
            if not has_cookies:
                error_msg = "❌ السيرفر لا يجد ملف cookies.txt."
            else:
                error_msg = "⚠️ ملف cookies.txt موجود ولكن يوتيوب رفضه. حاول استخراج كوكيز جديدة."
                
        progress_tracker[task_id] = {'status': 'error', 'percent': 0, 'error': error_msg}
        return jsonify({'error': error_msg}), 500

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    return jsonify(progress_tracker.get(task_id, {'status': 'unknown', 'percent': 0}))

@app.route('/api/file/<filename>')
def serve_file(filename):
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({'error': 'الملف غير موجود'}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port, threaded=True)
