from flask import Flask, request, send_file, jsonify
import io
from PIL import Image
import numpy as np
import cv2
import svgwrite
from pyembroidery import EmbPattern, write_dst, write_dse, STITCH, COLOR_CHANGE

app = Flask(__name__)

@app.route("/")
def index():
    return "خادم التطريز AI جاهز ✅"

def image_to_segments(img, num_colors=5):
    """
    تقسيم الصورة إلى مناطق/ألوان رئيسية باستخدام K-means
    لتسهيل تحويل الصورة إلى تطريز.
    """
    Z = img.reshape((-1,3))
    Z = np.float32(Z)
    
    # K-means لتحديد الألوان الرئيسية
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    K = num_colors
    _, label, center = cv2.kmeans(Z, K, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    
    center = np.uint8(center)
    res = center[label.flatten()]
    segmented_img = res.reshape((img.shape))
    return segmented_img, label.reshape((img.shape[0], img.shape[1])), center

def segmented_to_svg(segmented_img, labels, centers):
    """تحويل الصورة المقسمة إلى SVG مع كل لون كمسار"""
    h, w, _ = segmented_img.shape
    svg = svgwrite.Drawing(size=(w,h))
    
    for i, color in enumerate(centers):
        mask = (labels == i).astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            points = [(p[0][0], p[0][1]) for p in contour]
            if len(points) > 1:
                hex_color = '#%02x%02x%02x' % tuple(color)
                svg.add(svg.polyline(points=points, stroke=hex_color, fill='none', stroke_width=1))
    return svg

def svg_to_pattern(svg):
    """تحويل SVG إلى غرز مع دعم تغييرات اللون لكل منطقة"""
    pattern = EmbPattern()
    last_color = None
    for element in svg.elements:
        if isinstance(element, svgwrite.shapes.Polyline):
            stroke_color = element.stroke
            if last_color != stroke_color:
                pattern.add_stitch_absolute(COLOR_CHANGE, 0, 0)
                last_color = stroke_color
            points = element.points
            for i, (x, y) in enumerate(points):
                pattern.add_stitch_absolute(STITCH, x, y)
    return pattern

@app.route("/convert", methods=["POST"])
def convert():
    if 'file' not in request.files:
        return jsonify({"error": "لم يتم رفع أي ملف"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "لم يتم اختيار ملف"}), 400

    file_type = request.form.get('type', 'dst')

    img = np.array(Image.open(file).convert("RGB"))

    # تقسيم الصورة باستخدام AI (K-means)
    segmented_img, labels, centers = image_to_segments(img, num_colors=8)

    # تحويل الصورة المقسمة إلى SVG
    svg = segmented_to_svg(segmented_img, labels, centers)

    # تحويل SVG إلى غرز رقمية
    pattern = svg_to_pattern(svg)

    out_buffer = io.BytesIO()
    if file_type.lower() == 'dse':
        write_dse(pattern, out_buffer)
    else:
        write_dst(pattern, out_buffer)
    out_buffer.seek(0)

    return send_file(out_buffer, mimetype="application/octet-stream",
                     as_attachment=True,
                     download_name=f'pattern.{file_type.lower()}')

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
