from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes
from io import BytesIO
from flask_cors import CORS
from PIL import Image
import numpy as np
import math

app = Flask(__name__)
CORS(app)

JUMP_THRESHOLD = 20  # المسافة لتحويل الغرزة إلى Jump Stitch
STITCH_SPACING = 2   # المسافة بين الغرز بالبيكسل

def image_to_points(img: Image.Image):
    """
    تحويل الصورة إلى نقاط غرز لكل لون
    """
    img = img.convert('RGB')
    width, height = img.size
    pixels = np.array(img)
    points_by_color = {}

    for y in range(0, height, STITCH_SPACING):
        for x in range(0, width, STITCH_SPACING):
            color = tuple(pixels[y, x])
            if color not in points_by_color:
                points_by_color[color] = []
            points_by_color[color].append((x, y))
    
    return points_by_color

def nearest_neighbor_sort(points):
    """
    ترتيب النقاط بطريقة تقريبية لتقليل مسار الإبرة
    """
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

def add_points_to_pattern(pattern, points, color=None):
    """
    إضافة نقاط الغرز إلى المخطط مع إدارة Jump Stitch
    """
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

    # إضافة خيط للون (اختياري للمعاينة في برامج تدعم اللون)
    if color:
        pattern.add_thread(color)

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        if 'image' not in request.files:
            return {"error": "يجب رفع صورة PNG أو JPG"}, 400

        img_file = request.files['image']
        img = Image.open(img_file)
        points_by_color = image_to_points(img)

        pattern = EmbPattern()

        # لكل لون، أضف النقاط بعد ترتيبها
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
