from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst
from PIL import Image, ImageOps
import numpy as np
from io import BytesIO
from sklearn.cluster import KMeans
import os

app = Flask(__name__)
CORS(app)

def remove_background(image, threshold=240):
    """إزالة الخلفية الفاتحة من الصورة"""
    image_np = np.array(image.convert('RGB'))
    mask = np.all(image_np > threshold, axis=2)
    image_np[mask] = [255, 255, 255]
    return Image.fromarray(image_np)

def nearest_neighbor_order(points):
    """ترتيب النقاط بطريقة أقرب جار لتقليل حركة الإبرة"""
    if not points:
        return []
    ordered = [points.pop(0)]
    while points:
        last = ordered[-1]
        distances = [((p[0]-last[0])**2 + (p[1]-last[1])**2, idx) for idx, p in enumerate(points)]
        _, idx_min = min(distances)
        ordered.append(points.pop(idx_min))
    return ordered

def quantize_colors(image, max_colors=8):
    """تحديد أفضل عدد ألوان تلقائي للصورة مع dithering"""
    img_small = image.resize((200, 200), Image.Resampling.LANCZOS)
    img_dithered = img_small.convert('P', palette=Image.ADAPTIVE, colors=max_colors)
    img_rgb = img_dithered.convert('RGB')
    return img_rgb

def get_color_layers(image, num_colors=8):
    """تقسيم الصورة إلى طبقات ألوان باستخدام K-Means"""
    img_np = np.array(image)
    pixels = img_np.reshape(-1, 3)
    kmeans = KMeans(n_clusters=num_colors, random_state=42, n_init=5).fit(pixels)
    labels = kmeans.labels_.reshape(img_np.shape[0], img_np.shape[1])
    centers = np.uint8(kmeans.cluster_centers_)
    layers = []
    for i, color in enumerate(centers):
        points = [(x, y) for y in range(labels.shape[0]) for x in range(labels.shape[1]) if labels[y, x] == i]
        layers.append({'color': tuple(color), 'points': points})
    return layers

def create_embroidery(image, width=None, height=None, stitch_step=2, max_colors=8):
    """إنشاء قالب تطريز متعدد الألوان مع مسار إبرة ذكي لكل لون"""
    if width and height:
        image = image.resize((width, height), Image.Resampling.LANCZOS)

    pattern = EmbPattern()
    img_quantized = quantize_colors(image, max_colors=max_colors)
    layers = get_color_layers(img_quantized, num_colors=max_colors)

    for layer in layers:
        color = layer['color']  # tuple RGB مباشرة
        points = [(x, y) for x, y in layer['points'] if x % stitch_step == 0 and y % stitch_step == 0]
        ordered_points = nearest_neighbor_order(points)
        pattern.add_thread(color)  # استخدام tuple RGB مباشرة
        for x, y in ordered_points:
            pattern.add_stitch_absolute(x, y)

    pattern.end()
    return pattern

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400

    file = request.files['file']
    width = request.form.get('width', type=int)
    height = request.form.get('height', type=int)
    stitch_step = request.form.get('stitch_step', 2, type=int)
    max_colors = request.form.get('colors', 8, type=int)

    img = Image.open(file.stream).convert('RGB')
    img = remove_background(img)
    pattern = create_embroidery(img, width=width, height=height, stitch_step=stitch_step, max_colors=max_colors)

    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return send_file(
        bio,
        download_name='pattern.dst',
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Replit أو Render يحدد PORT تلقائيًا
    app.run(host="0.0.0.0", port=port)
