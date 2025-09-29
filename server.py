from flask import Flask, request, send_file, jsonify
from pyembroidery import read, EmbPattern, write_pes
from flask_cors import CORS
from PIL import Image
import numpy as np
import cv2
from io import BytesIO

app = Flask(__name__)
CORS(app)

# ملف التطريز الحقيقي المخزن على السيرفر
SAMPLE_PES_FILE = "sample.pes"

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def mask_from_color(img_cv, color_rgb, tol=40):
    low = np.clip(color_rgb - tol, 0, 255).astype(np.uint8)
    high = np.clip(color_rgb + tol, 0, 255).astype(np.uint8)
    mask = cv2.inRange(img_cv, low, high)
    kernel = np.ones((3,3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask

def generate_stitches(mask, scale_mm_per_px, density_mm, direction='horizontal'):
    ys, xs = np.where(mask>0)
    if len(xs)==0:
        return []
    step = max(1,int(density_mm/scale_mm_per_px))
    stitches=[]
    if direction=='vertical':
        for x in range(np.min(xs), np.max(xs)+1, step):
            col_y = ys[xs==x]
            for y in range(np.min(col_y), np.max(col_y)+1, step):
                stitches.append((x,y))
    else:
        for y in range(np.min(ys), np.max(ys)+1, step):
            row_x = xs[ys==y]
            for x in range(np.min(row_x), np.max(row_x)+1, step):
                stitches.append((x,y))
    return stitches

@app.route('/generate_pes_from_image', methods=['POST'])
def generate_pes_from_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error":"يرجى رفع الصورة"}),400

        # قراءة ملف PES المخزن
        sample_pattern = read(SAMPLE_PES_FILE,'PES')
        colors_data = []
        for thread in sample_pattern.threadlist:
            colors_data.append({
                "color_rgb": np.array([thread.red, thread.green, thread.blue]),
                "density": 2.0,
                "direction": 'horizontal'
            })
        # قراءة الصورة المرفوعة
        img_cv = pil_to_cv2(Image.open(request.files['image'].stream).convert("RGB"))
        h_px, w_px = img_cv.shape[:2]
        # إعداد التحجيم بناءً على PES المخزن
        sample_width = sample_pattern.bounds[2]-sample_pattern.bounds[0]
        sample_height = sample_pattern.bounds[3]-sample_pattern.bounds[1]
        scale_px_per_mm = w_px / sample_width
        scale_mm_per_px = 1.0 / scale_px_per_mm

        pattern=EmbPattern()

        for color in colors_data:
            mask = mask_from_color(img_cv, color["color_rgb"], tol=40)
            stitches_px = generate_stitches(mask, scale_mm_per_px, color["density"], color["direction"])
            for x_px,y_px in stitches_px:
                x_mm = x_px*scale_mm_per_px
                y_mm = y_px*scale_mm_per_px
                pattern.add_stitch_absolute(x_mm,y_mm)

        buf=BytesIO()
        write_pes(pattern,buf)
        buf.seek(0)
        return send_file(buf,download_name="ai_stitch.pes",mimetype="application/octet-stream")

    except Exception as e:
        return jsonify({"error":str(e)}),500

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
