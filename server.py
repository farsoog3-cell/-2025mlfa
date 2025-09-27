from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, read_dst, EmbThread
from PIL import Image
import numpy as np
from io import BytesIO
import math

app = Flask(__name__)
CORS(app)

def generate_dst_from_image(image):
    """تحويل الصورة إلى DST مع إطار وغرز"""
    pattern = EmbPattern()

    # إضافة خيط افتراضي
    thread = EmbThread()
    thread.set_color(0, 0, 255)
    pattern.add_thread(thread)

    # تحويل الصورة لـ grayscale وتقليل الحجم
    image = image.convert("L").resize((200, 200))
    arr = np.array(image)

    # Threshold لتحديد المناطق الداكنة
    step = 2
    for y in range(0, arr.shape[0], step):
        for x in range(0, arr.shape[1], step):
            if arr[y, x] < 128:
                pattern.add_stitch_absolute(x, y)

    # إضافة إطار حول القالب
    min_x, max_x = 0, arr.shape[1]-1
    min_y, max_y = 0, arr.shape[0]-1
    pattern.add_stitch_absolute(min_x, min_y)
    pattern.add_stitch_absolute(max_x, min_y)
    pattern.add_stitch_absolute(max_x, max_y)
    pattern.add_stitch_absolute(min_x, max_y)
    pattern.add_stitch_absolute(min_x, min_y)

    pattern.end()
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return bio

def process_dst_file(file_stream):
    """إعادة كتابة DST وإضافة إطار"""
    pattern = read_dst(file_stream)

    # حساب الحدود
    xs = [s[0] for s in pattern.stitches]
    ys = [s[1] for s in pattern.stitches]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    # إضافة إطار حول القالب
    pattern.add_stitch_absolute(min_x, min_y)
    pattern.add_stitch_absolute(max_x, min_y)
    pattern.add_stitch_absolute(max_x, max_y)
    pattern.add_stitch_absolute(min_x, max_y)
    pattern.add_stitch_absolute(min_x, min_y)

    pattern.end()
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return bio

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400
    file = request.files['file']

    try:
        if file.filename.lower().endswith((".png", ".jpg", ".jpeg")):
            img = Image.open(file.stream).convert("RGB")
            dst_file = generate_dst_from_image(img)
        elif file.filename.lower().endswith(".dst"):
            dst_file = process_dst_file(file.stream)
        else:
            return jsonify({'error':'Unsupported file type'}), 400

        return send_file(
            dst_file,
            download_name='pattern.dst',
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
