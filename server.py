from flask import Flask, request, send_file, jsonify
from pyembroidery import read, EmbPattern, write_pes
from flask_cors import CORS
from PIL import Image
import numpy as np
import cv2
from io import BytesIO
from sklearn.cluster import KMeans

app = Flask(__name__)
CORS(app)

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def quantize_colors(img_cv, n_colors=6):
    h, w = img_cv.shape[:2]
    samples = img_cv.reshape(-1, 3).astype(np.float32)
    kmeans = KMeans(n_clusters=n_colors, random_state=0).fit(samples)
    labels = kmeans.labels_
    palette = np.uint8(kmeans.cluster_centers_)
    quant = palette[labels].reshape((h, w, 3))
    return quant, palette

def mask_from_color(img_cv, color_rgb, tol=30):
    low = np.clip(color_rgb - tol, 0, 255).astype(np.uint8)
    high = np.clip(color_rgb + tol, 0, 255).astype(np.uint8)
    mask = cv2.inRange(img_cv, low, high)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def analyze_sample_pattern(pattern):
    # استخراج معلومات متقدمة لكل لون
    color_data = []
    for i, thread in enumerate(pattern.threadlist):
        color_info = {
            "color_index": i,
            "color_rgb": np.array([thread.red, thread.green, thread.blue]),
            "density": 2.0,  # الافتراضي، يمكن تحسينه لاحقًا
            "direction": 'horizontal'  # الافتراضي، يمكن تعديل حسب الغرز
        }
        color_data.append(color_info)
    return {
        "width": pattern.bounds[2]-pattern.bounds[0],
        "height": pattern.bounds[3]-pattern.bounds[1],
        "colors": color_data
    }

def generate_stitches(mask, scale_mm_per_px, density_mm, direction='horizontal'):
    ys, xs = np.where(mask>0)
    if len(xs)==0:
        return []
    step = max(1,int(density_mm/scale_mm_per_px))
    lines = []
    if direction=='vertical':
        for x in range(np.min(xs), np.max(xs)+1, step):
            col_y = ys[xs==x]
            for y in range(np.min(col_y), np.max(col_y)+1, step):
                lines.append((x,y))
    else:
        for y in range(np.min(ys), np.max(ys)+1, step):
            row_x = xs[ys==y]
            for x in range(np.min(row_x), np.max(row_x)+1, step):
                lines.append((x,y))
    return lines

@app.route('/convert_image_with_ai_advanced', methods=['POST'])
def convert_image_with_ai_advanced():
    try:
        if 'image' not in request.files or 'sample_pes' not in request.files:
            return jsonify({"error":"يرجى إرسال الصورة وملف PES المثال"}),400

        # قراءة PES المثال
        sample_pattern = read(request.files['sample_pes'].stream,'PES')
        sample_info = analyze_sample_pattern(sample_pattern)

        # قراءة الصورة الجديدة
        img_cv = pil_to_cv2(Image.open(request.files['image'].stream).convert("RGB"))
        h_px, w_px = img_cv.shape[:2]
        aspect = w_px/h_px
        max_w = sample_info["width"]
        max_h = sample_info["height"]
        if max_w/max_h>aspect:
            final_h_mm=max_h
            final_w_mm=aspect*final_h_mm
        else:
            final_w_mm=max_w
            final_h_mm=final_w_mm/aspect
        scale_px_per_mm=w_px/final_w_mm
        scale_mm_per_px=1.0/scale_px_per_mm

        pattern=EmbPattern()

        for color_data in sample_info["colors"]:
            mask = mask_from_color(img_cv, color_data["color_rgb"], tol=40)
            stitches_px = generate_stitches(mask, scale_mm_per_px, color_data["density"], color_data["direction"])
            for x_px,y_px in stitches_px:
                x_mm = x_px*scale_mm_per_px
                y_mm = y_px*scale_mm_per_px
                pattern.add_stitch_absolute(x_mm,y_mm)

        buf=BytesIO()
        write_pes(pattern,buf)
        buf.seek(0)
        return send_file(buf,download_name="ai_advanced.pes",mimetype="application/octet-stream")

    except Exception as e:
        return jsonify({"error":str(e)}),500

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
