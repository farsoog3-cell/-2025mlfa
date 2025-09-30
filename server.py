from flask import Flask, request, send_file, jsonify
from pyembroidery import EmbPattern, write_dst
from PIL import Image
import numpy as np
import cv2
from io import BytesIO
import json

app = Flask(__name__)

# ملف التطريز الأصلي (JSON) لتعلم الأسلوب
STYLE_FILE = "stitches_style.json"

def load_style():
    with open(STYLE_FILE, "r") as f:
        return json.load(f)

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def extract_masks(img_cv, num_colors=3):
    """ استخراج أهم الألوان وتقسيم الصورة إلى أقنعة """
    img_data = img_cv.reshape((-1,3)).astype(np.float32)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(img_data, num_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    centers = np.uint8(centers)
    labels = labels.flatten()

    masks=[]
    for i, color in enumerate(centers):
        mask = (labels == i).reshape(img_cv.shape[:2]).astype(np.uint8)*255
        masks.append({"color_rgb": color, "mask": mask})
    return masks

def generate_stitches_from_mask(mask, step=5):
    """ إنشاء نقاط الغرز على أساس القناع """
    ys, xs = np.where(mask>0)
    stitches=[]
    for x,y in zip(xs,ys):
        if x%step==0 and y%step==0:
            stitches.append((x,y))
    return stitches

@app.route("/generate_dst_from_image", methods=["POST"])
def generate_dst_from_image():
    try:
        if 'image' not in request.files:
            return jsonify({"error":"يرجى رفع صورة"}), 400
        
        img_pil = Image.open(request.files['image'].stream).convert("RGB")
        img_cv = pil_to_cv2(img_pil)
        h, w = img_cv.shape[:2]

        # تحميل أسلوب التطريز
        style = load_style()

        # استخراج الأقنعة
        masks = extract_masks(img_cv, num_colors=len(style["colors"]))

        # إنشاء النمط الجديد
        pattern = EmbPattern()
        for idx, item in enumerate(masks):
            mask = item["mask"]
            stitches_px = generate_stitches_from_mask(mask, step=5)
            for x_px, y_px in stitches_px:
                # هنا نحاكي أسلوب التطريز من JSON (مثلاً التدرج والمسافة)
                x_mm = x_px  # يمكن تعديل القياس حسب الحاجة
                y_mm = y_px
                pattern.add_stitch_absolute(x_mm, y_mm)

        # إنشاء ملف DST في الذاكرة
        buf = BytesIO()
        write_dst(pattern, buf)
        buf.seek(0)

        return send_file(buf, download_name="ai_stitch.dst", mimetype="application/octet-stream")

    except Exception as e:
        return jsonify({"error": str(e)}),500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
