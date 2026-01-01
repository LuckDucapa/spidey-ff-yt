from flask import Flask, request, render_template_string, Response, stream_with_context
import yt_dlp
import requests
import urllib.parse

app = Flask(__name__)

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple YT Downloader</title>
    <style>
        body { font-family: sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }
        input { width: 70%; padding: 10px; }
        button { padding: 10px 20px; cursor: pointer; }
        .card { border: 1px solid #ddd; padding: 15px; margin-top: 10px; border-radius: 8px; }
        .download-btn {
            background-color: #0070f3; color: white; text-decoration: none;
            padding: 8px 15px; border-radius: 5px; display: inline-block; margin-top: 10px;
        }
    </style>
</head>
<body>
    <h1>YouTube Downloader (No FFmpeg)</h1>
    <form method="POST" action="/info">
        <input type="text" name="url" placeholder="Paste YouTube URL here..." required>
        <button type="submit">Get Info</button>
    </form>
    
    {% if video %}
    <div class="card">
        <h3>{{ video.title }}</h3>
        <img src="{{ video.thumbnail }}" width="200" style="border-radius:10px;">
        <p>Duration: {{ video.duration }}s</p>
        
        <h4>Video Formats (Max 720p due to no FFmpeg):</h4>
        {% for fmt in formats %}
            {% if fmt.vcodec != 'none' and fmt.acodec != 'none' %}
            <div style="margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                <strong>{{ fmt.resolution }}</strong> ({{ fmt.ext }}) - {{ fmt.filesize_approx }}
                <br>
                <a href="/download?url={{ fmt.url | quote }}&title={{ video.title | quote }}&ext={{ fmt.ext }}" class="download-btn">Download Video</a>
            </div>
            {% endif %}
        {% endfor %}

        <h4>Audio Only:</h4>
        {% for fmt in formats %}
            {% if fmt.vcodec == 'none' and fmt.acodec != 'none' %}
            <div style="margin-bottom: 10px; border-bottom: 1px solid #eee; padding-bottom: 5px;">
                <strong>Audio</strong> ({{ fmt.ext }}) - {{ fmt.abr }}kbps
                <br>
                <a href="/download?url={{ fmt.url | quote }}&title={{ video.title | quote }}&ext={{ fmt.ext }}" class="download-btn">Download Audio</a>
            </div>
            {% endif %}
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>
"""

# Custom filter for URL encoding in templates
@app.template_filter('quote')
def quote_filter(s):
    return urllib.parse.quote(str(s))

@app.route('/', methods=['GET'])
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/info', methods=['POST'])
def get_info():
    url = request.form.get('url')
    if not url:
        return "URL required", 400

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        # Without FFmpeg, we can't merge, so we rely on formats that already have both
        # or separate streams.
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Basic video info
            video_data = {
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration')
            }
            
            # Filter formats
            # We explicitly look for 'progressive' (video+audio) or audio-only
            clean_formats = []
            for f in info.get('formats', []):
                # Helper to format size
                filesize = f.get('filesize') or f.get('filesize_approx')
                size_str = f"{round(filesize / 1024 / 1024, 2)} MB" if filesize else "Unknown size"
                
                clean_formats.append({
                    'format_id': f['format_id'],
                    'ext': f['ext'],
                    'resolution': f.get('resolution', 'Audio only'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec'),
                    'abr': f.get('abr'),
                    'filesize_approx': size_str,
                    'url': f['url'] # The direct Google video URL
                })

            # Sort: simple logic to put higher quality first
            clean_formats.reverse()

            return render_template_string(HTML_TEMPLATE, video=video_data, formats=clean_formats)
            
    except Exception as e:
        return f"Error extracting info: {str(e)}", 500

@app.route('/download')
def download_proxy():
    # Vercel Limitation: This proxy approach will TIMEOUT if the file is large
    # because Vercel functions have execution time limits (10s - 60s).
    
    video_url = request.args.get('url')
    title = request.args.get('title', 'download')
    ext = request.args.get('ext', 'mp4')
    
    if not video_url:
        return "No URL provided", 400

    filename = f"{title}.{ext}"
    # Clean filename
    filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in ' .-_']).rstrip()

    # Stream the file from Google -> Vercel -> User
    req = requests.get(video_url, stream=True)
    
    return Response(
        stream_with_context(req.iter_content(chunk_size=1024*1024)),
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Type": req.headers.get('content-type', 'application/octet-stream')
        }
    )

if __name__ == '__main__':
    app.run(debug=True)