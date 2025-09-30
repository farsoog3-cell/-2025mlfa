# app.py
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, read
from PIL import Image
import numpy as np
import cv2
from io import BytesIO
import json
from sklearn.cluster import KMeans

app = Flask(__name__)
CORS(app)

# ملف DST نموذجي لتحديد لوحة الألوان ومقياس التصميم
SAMPLE_DST_FILE = "sample.dst"

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def extract_palette_from_sample(sample_path):
    """يستخرج قائمة الألوان ومقياس التصميم من ملف DST/PES"""
    pattern = read(sample_path, 'DST')
    palette = []
    try:
        for th in pattern.threadlist:
            palette.append([int(th.red), int(th.green), int(th.blue)])
    except Exception:
        palette = [[0,0,0]]
    try:
        w_mm = pattern.bounds[2] - pattern.bounds[0]
        if w_mm <= 0:
            w_mm = 100.0
    except Exception:
        w_mm = 100.0
    return palette, w_mm

def quantize_image_to_palette(img_cv, palette):
    """يقلل ألوان الصورة إلى أقرب ألوان في اللوحة ويولد أقنعة لكل لون"""
    h,w = img_cv.shape[:2]
    n_colors = len(palette)
    pixels = img_cv.reshape(-1,3).astype(np.float32)
    if len(pixels) == 0:
        return []
    k = min(n_colors, 8)
    kmeans = KMeans(n_clusters=k, random_state=0, n_init=4)
    labels = kmeans.fit_predict(pixels)
    centers = np.uint8(kmeans.cluster_centers_)
    masks = []
    for i, center in enumerate(centers):
        dists = np.linalg.norm(np.array(palette) - center, axis=1)
        nearest_idx = int(np.argmin(dists))
        mapped_color = palette[nearest_idx]
        mask = (labels.reshape(h,w) == i).astype(np.uint8) * 255
        masks.append({
            "mapped_color_idx": nearest_idx,
            "mapped_color_rgb": mapped_color,
            "mask": mask,
            "pixels_count": int(np.sum(mask>0))
        })
    return masks

def generate_hatch_stitches_from_mask(mask, step=6):
    """يولد نقاط الغرز داخل القناع بطريقة hatch مرتبة"""
    ys, xs = np.where(mask>0)
    if len(xs) == 0:
        return []
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    stitches = []
    for y in range(y_min, y_max+1, step):
        row_xs = xs[ys == y]
        if len(row_xs) == 0:
            row_xs = np.where(mask[y,:] > 0)[0]
            if len(row_xs) == 0:
                continue
        x_start = int(row_xs.min())
        x_end = int(row_xs.max())
        for x in range(x_start, x_end+1, step):
            if mask[y, x] > 0:
                stitches.append((x, y))
    return stitches

@app.route("/generate_dst_from_image", methods=["POST"])
def generate_dst_from_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error":"يرجى رفع الصورة"}), 400

        palette, sample_width_mm = extract_palette_from_sample(SAMPLE_DST_FILE)
        img_pil = Image.open(request.files['image'].stream).convert("RGB")
        img_cv = pil_to_cv2(img_pil)
        h, w = img_cv.shape[:2]
        masks = quantize_image_to_palette(img_cv, palette)
        pattern = EmbPattern()
        scale_mm_per_px = float(sample_width_mm) / float(max(w,1))
        colors_info = []

        for entry in masks:
            mapped_rgb = entry["mapped_color_rgb"]
            mask = entry["mask"]
            pixel_count = entry["pixels_count"]
            density_factor = max(3, min(12, int(np.clip(20000.0 / (pixel_count+1), 3, 12))))
            stitches_px = generate_hatch_stitches_from_mask(mask, step=density_factor)

            try:
                pattern.add_color_change()
            except Exception:
                pass

            for (x_px, y_px) in stitches_px:
                x_mm = x_px * scale_mm_per_px
                y_mm = y_px * scale_mm_per_px
                pattern.add_stitch_absolute(float(x_mm), float(y_mm))

            colors_info.append({
                "hex": '#{:02x}{:02x}{:02x}'.format(int(mapped_rgb[0]), int(mapped_rgb[1]), int(mapped_rgb[2])),
                "stitches": len(stitches_px)
            })

        buf = BytesIO()
        write_dst(pattern, buf)
        buf.seek(0)

        response = send_file(buf, download_name="ai_stitch.dst", mimetype="application/octet-stream")
        response.headers['X-Colors-Info'] = json.dumps(colors_info)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
