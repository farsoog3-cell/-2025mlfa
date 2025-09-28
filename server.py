from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes, COLOR_BLACK, Thread
from io import BytesIO
from flask_cors import CORS
from PIL import Image
import numpy as np
import math

app = Flask(__name__)
CORS(app)

# إعدادات آمنة للماكينة
MAX_SIZE = 400  # أقصى عرض أو ارتفاع بالبيكسل
STITCH_SPACING = 3  # المسافة بين الغرز
JUMP_THRESHOLD = 15  # المسافة لتحويل الغرزة إلى Jump Stitch
MAX_COLORS = 8  # أقصى عدد ألوان للماكينة

# تحويل الصورة إلى نقاط غرز لكل لون
def image_to_points(img: Image.Image):
    img.thumbnail((MAX_SIZE, MAX_SIZE))
    img = img.convert('RGB')

    # تقليل عدد الألوان
    img = img.quantize(colors=MAX_COLORS)
    pixels = np.array(img)
    width, height = img.size
    points_by_color = {}

    for y in range(0, height, STITCH_SPACING):
        for x in range(0, width, STITCH_SPACING):
            color = tuple(pixels[y, x])
            if color not in points_by_color:
                points_by_color[color] = []
            points_by_color[color].append((x, y))
    
    return points_by_color

# ترتيب النقاط لتقليل مسار الإبرة
def nearest_neighbor_sort(points):
    if not points:
        return []
    points = points.copy()
    sorted_points = [points.pop(0)]
    while points:
        last = sorted_points[-1]
        next_point = min(points, key=lambda p: math.hypot(p[0]-last[0], p[1]-last[1]))
        sorted_points.append(next_point)
        points.remove(next_point)
    return sorted_points

# إضافة نقاط الغرز إلى المخطط
def add_points_to_pattern(pattern, points, color=None):
    if color:
        pattern.add_thread(Thread(*color))  # تعيين لون الخيط
    
    sorted_points = nearest_neighbor_sort(points)
    prev = None
    for x, y in sorted_points:
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

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        if 'image' not in request.files:
            return {"error": "يجب رفع صورة PNG أو JPG"}, 400

        img_file = request.files['image']
        img = Image.open(img_file)
        points_by_color = image_to_points(img)

        pattern = EmbPattern()
        for color, points in points_by_color.items():
            add_points_to_pattern(pattern, points, color=color)

        pattern.end()
        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)

        return send_file(buf, download_name="stitch_pattern.pes", mimetype="application/x-pes")
    
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
