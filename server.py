from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes, Thread
from io import BytesIO
from flask_cors import CORS
from PIL import Image
import numpy as np
import math

app = Flask(__name__)
CORS(app)

# إعدادات آمنة للماكينة
MAX_SIZE = 400
STITCH_SPACING = 3
JUMP_THRESHOLD = 15
MAX_COLORS = 1  # سنستخدم لون واحد لمحاكاة الخيط المتصل

# تحويل الصورة إلى مسار غرزة متصلة
def image_to_stitch_path(img: Image.Image):
    img.thumbnail((MAX_SIZE, MAX_SIZE))
    img = img.convert('L')  # تحويل للصورة الرمادية
    pixels = np.array(img)
    width, height = img.size
    points = []

    for y in range(0, height, STITCH_SPACING):
        for x in range(0, width, STITCH_SPACING):
            brightness = pixels[y, x]
            if brightness < 200:  # نقاط الغرز حسب الظل
                points.append((x, y))
    
    # ترتيب النقاط بطريقة تقريبية لمسار الإبرة
    if not points:
        return []

    sorted_points = [points.pop(0)]
    while points:
        last = sorted_points[-1]
        next_point = min(points, key=lambda p: math.hypot(p[0]-last[0], p[1]-last[1]))
        sorted_points.append(next_point)
        points.remove(next_point)
    
    return sorted_points

# إنشاء PES من مسار الغرز
def generate_pes_from_path(points):
    pattern = EmbPattern()
    # لون واحد للخيط
    pattern.add_thread(Thread(0,0,0))
    prev = None
    for x, y in points:
        if prev:
            dx = x - prev[0]
            dy = y - prev[1]
            dist = math.hypot(dx, dy)
            if dist > JUMP_THRESHOLD:
                pattern.add_jump(x, y)
            else:
                pattern.add_stitch_absolute(x, y)
        else:
            pattern.add_stitch_absolute(x, y)
        prev = (x, y)
    pattern.end()
    buf = BytesIO()
    write_pes(pattern, buf)
    buf.seek(0)
    return buf

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        if 'image' not in request.files:
            return {"error": "يجب رفع صورة PNG أو JPG"}, 400

        img_file = request.files['image']
        img = Image.open(img_file)
        points = image_to_stitch_path(img)
        buf = generate_pes_from_path(points)

        return send_file(buf, download_name="stitch_pattern.pes", mimetype="application/x-pes")
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
