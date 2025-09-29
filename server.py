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

def generate_fill_stitches_from_mask(mask, spacing=2.0, scale=1.0, direction='horizontal'):
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return []
    xmin, xmax = xs.min(), xs.max()
    ymin, ymax = ys.min(), ys.max()
    lines = []
    step = max(1, int(spacing/scale))
    if direction == 'vertical':
        for x in range(xmin, xmax+1, step):
            col_y = ys[xs == x]
            if len(col_y) == 0:
                continue
            y_min = int(np.min(col_y))
            y_max = int(np.max(col_y))
            for y in range(y_min, y_max+1, step):
                lines.append((x, y))
    else:  # horizontal
        for y in range(ymin, ymax+1, step):
            row_x = xs[ys == y]
            if len(row_x) == 0:
                continue
            row_min = int(np.min(row_x))
            row_max = int(np.max(row_x))
            for x in range(row_min, row_max+1, step):
                lines.append((x, y))
    return lines

@app.route('/convert_image_with_sample', methods=['POST'])
def convert_image_with_sample():
    try:
        # التأكد من إرسال الملفات
        if 'image' not in request.files or 'sample_pes' not in request.files:
            return jsonify({"error": "أرسل الملفات 'image' و 'sample_pes'"}), 400

        # فتح PES المثال وتحليل أسلوب الغرز
        sample_file = request.files['sample_pes']
        sample_pattern = read(sample_file.stream, 'PES')

        # استخراج بعض الإحصائيات من PES المثال
        # (عدد الغرز الكلي، أبعاد التصميم، عدد الألوان)
        sample_width = sample_pattern.bounds[2] - sample_pattern.bounds[0]
        sample_height = sample_pattern.bounds[3] - sample_pattern.bounds[1]
        sample_colors = len(sample_pattern.threadlist)
        if sample_colors == 0:
            sample_colors = 6  # افتراضي

        # اتجاه الحشو الأساسي (أفقي)
        stitch_direction = 'horizontal'

        # فتح الصورة الجديدة
        img_file = request.files['image']
        img_pil = Image.open(img_file.stream).convert("RGB")
        img_cv = pil_to_cv2(img_pil)

        # تقليل الألوان بناءً على PES المثال
        quant_img, palette = quantize_colors(img_cv, n_colors=sample_colors)

        # ضبط حجم الصورة لتناسب PES المثال
        h_px, w_px = img_cv.shape[:2]
        aspect = w_px / h_px
        if sample_width / sample_height > aspect:
            final_h_mm = sample_height
            final_w_mm = aspect * final_h_mm
        else:
            final_w_mm = sample_width
            final_h_mm = final_w_mm / aspect
        scale_px_per_mm = w_px / final_w_mm
        scale_mm_per_px = 1.0 / scale_px_per_mm

        # إنشاء نمط التطريز
        pattern = EmbPattern()

        for i, color in enumerate(palette):
            mask = mask_from_color(quant_img, color, tol=40)
            num_pixels = cv2.countNonZero(mask)
            if num_pixels < 50:
                continue

            stitches_px = generate_fill_stitches_from_mask(mask, spacing=2.0, scale=scale_mm_per_px, direction=stitch_direction)
            if not stitches_px:
                continue

            for (x_px, y_px) in stitches_px:
                x_mm = x_px * scale_mm_per_px
                y_mm = y_px * scale_mm_per_px
                pattern.add_stitch_absolute(x_mm, y_mm)

        # كتابة ملف PES الناتج
        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)
        return send_file(buf, download_name="converted_with_sample.pes", mimetype="application/octet-stream")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
