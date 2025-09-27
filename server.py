from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, EmbThread
from PIL import Image, ImageOps
import numpy as np
from io import BytesIO

app = Flask(__name__)
CORS(app)

def remove_background(image):
    """تحويل الصورة إلى أبيض وأسود وإزالة الخلفية البيضاء"""
    # تحويل للصورة رمادي
    gray = image.convert("L")
    # Threshold
    bw = gray.point(lambda x: 0 if x < 128 else 255, '1')
    # إزالة الحواف البيضاء
    bbox = bw.getbbox()
    if bbox:
        bw = bw.crop(bbox)
    return bw

def generate_stitches(image):
    """إنشاء ملف DST مع مسار كامل وغرز ساتان يمين/يسار"""
    pattern = EmbPattern()
    thread = EmbThread()
    thread.set_color(0,0,0)  # أسود
    pattern.add_thread(thread)

    img = image
    pixels = np.array(img)
    height, width = pixels.shape

    step = 2  # حجم الغرزة

    # توليد الغرز يمين ويسار لملء الصورة
    for y in range(0, height, step):
        direction = 1 if y % 4 == 0 else -1  # تغيير الاتجاه
        for x in range(0, width, step):
            px = x if direction == 1 else width - x - 1
            if pixels[y, px] == 0:  # أسود
                pattern.add_stitch_absolute(px, y)

    # إضافة إطار حول القالب
    pattern.add_stitch_absolute(0,0)
    pattern.add_stitch_absolute(width-1,0)
    pattern.add_stitch_absolute(width-1,height-1)
    pattern.add_stitch_absolute(0,height-1)
    pattern.add_stitch_absolute(0,0)

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
        img = Image.open(file.stream).convert("RGB")
        img = remove_background(img)
        dst_file = generate_stitches(img)
        return send_file(
            dst_file,
            download_name='pattern.dst',
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
