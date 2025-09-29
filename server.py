from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_pes, read
from PIL import Image
import numpy as np
import cv2
from io import BytesIO

app = Flask(__name__)
CORS(app)

# ملف PES النموذجي لتعليم أسلوب التطريز
SAMPLE_PES_FILE = "sample.pes"

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def extract_colors_and_mask(img_cv, num_colors=3):
    img_data = img_cv.reshape((-1,3))
    img_data = np.float32(img_data)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(img_data, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    labels = labels.flatten()
    masks=[]
    for i, color in enumerate(centers):
        mask = (labels == i).reshape(img_cv.shape[:2]).astype(np.uint8)*255
        masks.append({
            "color_rgb": color,
            "mask": mask,
            "stitches": int(np.sum(mask>0)/10)
        })
    return masks

def generate_stitches(mask, step=5):
    ys, xs = np.where(mask>0)
    stitches=[]
    for x,y in zip(xs,ys):
        if x%step==0 and y%step==0:
            stitches.append((x,y))
    return stitches

@app.route("/generate_pes_from_image", methods=["POST"])
def generate_pes_from_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error":"يرجى رفع الصورة"}),400

        img_pil = Image.open(request.files['image'].stream).convert("RGB")
        img_cv = pil_to_cv2(img_pil)
        h, w = img_cv.shape[:2]

        # قراءة ملف PES النموذجي لتعليم أسلوب التطريز
        sample_pattern = read(SAMPLE_PES_FILE, 'PES')
        sample_width = sample_pattern.bounds[2] - sample_pattern.bounds[0]
        scale_mm_per_px = sample_width / w if w else 1.0

        masks = extract_colors_and_mask(img_cv, num_colors=3)

        pattern = EmbPattern()

        # توليد الغرز طبقًا لنمط sample.pes
        for item in masks:
            mask = item['mask']
            stitches_px = generate_stitches(mask, step=5)
            for x_px,y_px in stitches_px:
                x_mm = x_px * scale_mm_per_px
                y_mm = y_px * scale_mm_per_px
                pattern.add_stitch_absolute(x_mm, y_mm)

        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)

        colors_info = [{"hex": '#{:02x}{:02x}{:02x}'.format(*item["color_rgb"]),
                        "stitches": item["stitches"]} for item in masks]

        response = send_file(buf, download_name="ai_stitch.pes", mimetype="application/octet-stream")
        response.headers['X-Colors-Info'] = str(colors_info)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}),500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
