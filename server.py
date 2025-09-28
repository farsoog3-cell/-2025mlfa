# server.py
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from io import BytesIO
import numpy as np
import cv2
from pyembroidery import EmbPattern, write_pes, STITCH, JUMP, COLOR_CHANGE
import traceback
import math

app = Flask(__name__)
CORS(app)

# إعدادات افتراضية
DEFAULTS = {
    "stitch_length": 6.0,
    "fill_spacing": 6,
    "satin_width": 12,
    "min_contour_area": 100,
    "scale": 1.0
}

# تبسيط الكونتور لمسار غرز
def contour_to_path(contour, stitch_len=6.0):
    pts = contour.reshape(-1,2)
    path = []
    for i in range(len(pts)):
        p0 = pts[i]
        p1 = pts[(i+1) % len(pts)]
        dx = p1[0]-p0[0]
        dy = p1[1]-p0[1]
        seg_len = math.hypot(dx,dy)
        if seg_len == 0: continue
        t = 0.0
        while t <= seg_len:
            x = p0[0] + (dx/seg_len)*t
            y = p0[1] + (dy/seg_len)*t
            path.append({"x": float(x), "y": float(y)})
            t += stitch_len
    return path

# ملء الكونتور بخطوط Zig-Zag
def fill_contour_zigzag(contour, spacing=6):
    pts = contour.reshape(-1,2)
    xs = pts[:,0]; ys = pts[:,1]
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    fill_paths = []
    direction = 1
    for y in range(y_min, y_max+1, spacing):
        intersections = []
        for i in range(len(pts)):
            x1,y1 = pts[i]
            x2,y2 = pts[(i+1)%len(pts)]
            if (y1 <= y < y2) or (y2 <= y < y1):
                if y2 == y1: continue
                t = (y - y1) / (y2 - y1)
                x = x1 + t*(x2 - x1)
                intersections.append(x)
        intersections.sort()
        for i2 in range(0, len(intersections)-1, 2):
            x_start = int(intersections[i2])
            x_end = int(intersections[i2+1])
            if x_end <= x_start: continue
            if direction == 1:
                pts_line = [{"x": float(x), "y": float(y)} for x in range(x_start, x_end+1, max(1,int(spacing/2)))]
            else:
                pts_line = [{"x": float(x), "y": float(y)} for x in range(x_end, x_start-1, -max(1,int(spacing/2)))]
            if pts_line: fill_paths.append(pts_line)
        direction *= -1
    return fill_paths

# تحويل أوامر الغرز إلى EmbPattern
def commands_to_pattern(commands, scale=1.0):
    pattern = EmbPattern()
    for cmd in commands:
        c = cmd.get("cmd", "STITCH").upper()
        x = float(cmd.get("x", 0)) * scale
        y = float(cmd.get("y", 0)) * scale
        if c == "COLOR_CHANGE":
            pattern.add_stitch_absolute(COLOR_CHANGE, x, y)
        elif c == "JUMP":
            pattern.add_stitch_absolute(JUMP, x, y)
        else:
            pattern.add_stitch_absolute(STITCH, x, y)
    pattern.end()
    return pattern

@app.route('/image_to_pes', methods=['POST'])
def image_to_pes():
    try:
        if 'image' not in request.files:
            return jsonify({"error": "يرجى رفع صورة باسم الحقل 'image'"}), 400
        f = request.files['image']

        stitch_length = float(request.form.get('stitch_length', DEFAULTS["stitch_length"]))
        fill_spacing = int(request.form.get('fill_spacing', DEFAULTS["fill_spacing"]))
        min_area = int(request.form.get('min_contour_area', DEFAULTS["min_contour_area"]))
        scale = float(request.form.get('scale', DEFAULTS["scale"]))

        data = np.frombuffer(f.read(), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        if img is None:
            return jsonify({"error": "فشل قراءة الصورة"}), 400

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        blur = cv2.GaussianBlur(gray, (3,3), 0)
        _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if np.mean(th) > 127: th = 255 - th

        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=lambda c: cv2.contourArea(c), reverse=True)

        all_commands = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area: continue
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.01 * peri, True)
            if area > 2500:
                fill_paths = fill_contour_zigzag(approx, spacing=fill_spacing)
                for p in fill_paths:
                    all_commands.append({"cmd":"JUMP", "x": p[0]["x"], "y": p[0]["y"]})
                    for pt in p[1:]:
                        all_commands.append({"cmd":"STITCH", "x": pt["x"], "y": pt["y"]})
            else:
                path = contour_to_path(approx, stitch_len=stitch_length)
                if len(path) > 1:
                    all_commands.append({"cmd":"JUMP", "x": path[0]["x"], "y": path[0]["y"]})
                    for pt in path[1:]:
                        all_commands.append({"cmd":"STITCH", "x": pt["x"], "y": pt["y"]})

        if not all_commands:
            return jsonify({"error": "لم يتم استخراج أي غرز"}), 400

        pattern = commands_to_pattern(all_commands, scale=scale)
        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="output.pes", mimetype="application/octet-stream")

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
