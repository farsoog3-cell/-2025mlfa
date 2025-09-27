from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, write_dse, EmbThread
from PIL import Image
import numpy as np
from io import BytesIO

app = Flask(__name__)
CORS(app)

def preprocess_image(image):
    """تحويل الصورة إلى أبيض وأسود وإزالة الخلفية"""
    gray = image.convert("L")
    bw = gray.point(lambda x: 0 if x < 128 else 255, '1')
    bbox = bw.getbbox()
    if bbox:
        bw = bw.crop(bbox)
    return bw

def generate_stitches(image, file_type="DST"):
    """إنشاء ملف DST/DSE مع غرز Fill / Satin فعلي"""
    pattern = EmbPattern()
    thread = EmbThread()
    thread.set_color(0,0,0)
    pattern.add_thread(thread)

    pixels = np.array(image)
    height, width = pixels.shape
    step = 2  # حجم الغرزة

    # توليد الغرز مع ملء كامل الصورة
    for y in range(0, height, step):
        direction = 1 if (y//step)%2 == 0 else -1
        for x in range(0, width, step):
            px = x if direction==1 else width - x - 1
            if pixels[y, px] == 0:
                pattern.add_stitch_absolute(px, y)

    # إضافة إطار حول القالب
    pattern.add_stitch_absolute(0,0)
    pattern.add_stitch_absolute(width-1,0)
    pattern.add_stitch_absolute(width-1,height-1)
    pattern.add_stitch_absolute(0,height-1)
    pattern.add_stitch_absolute(0,0)

    pattern.end()
    bio = BytesIO()
    if file_type.upper()=="DSE":
        write_dse(pattern, bio)
    else:
        write_dst(pattern, bio)
    bio.seek(0)
    return bio

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400
    file = request.files['file']
    file_type = request.form.get('type', 'DST').upper()

    try:
        img = Image.open(file.stream).convert("RGB")
        img = preprocess_image(img)
        emb_file = generate_stitches(img, file_type)
        return send_file(
            emb_file,
            download_name=f'pattern.{file_type.lower()}',
            mimetype='application/octet-stream'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
