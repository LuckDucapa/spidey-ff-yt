from flask import Flask, request, render_template, jsonify
import requests

app = Flask(__name__, template_folder='../templates')

# --- CONFIGURATION ---
# Use a reliable public Cobalt instance. 
# You can find more instances at https://instances.cobalt.best/ if this one is busy.
COBALT_API_URL = "https://api.cobalt.tools/api/json" 
# Note: Public instances may have rate limits. For a serious project, host your own Cobalt instance on Render/Railway.

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/get-link', methods=['POST'])
def get_link():
    data = request.json
    video_url = data.get('url')
    
    if not video_url:
        return jsonify({'error': 'No URL provided'}), 400

    # Payload for Cobalt API
    # We ask for 1080p (max) and mp4 format
    payload = {
        "url": video_url,
        "vQuality": "max",
        "filenamePattern": "basic",
        "isAudioOnly": False
    }

    try:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # Send request to Cobalt
        response = requests.post(COBALT_API_URL, json=payload, headers=headers)
        resp_data = response.json()

        if response.status_code != 200:
            return jsonify({'error': 'Failed to process video. The link might be invalid or the server is busy.'}), 400

        # Cobalt returns different types of responses. We look for 'url' or 'picker'.
        if 'url' in resp_data:
            return jsonify({
                'status': 'success',
                'download_url': resp_data['url'],
                'filename': resp_data.get('filename', 'video.mp4')
            })
        elif 'picker' in resp_data:
            # sometimes it returns a list of items (picker)
            return jsonify({
                'status': 'success',
                'download_url': resp_data['picker'][0]['url'],
                'filename': 'video.mp4'
            })
        else:
             return jsonify({'error': 'Could not retrieve a direct link.'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)