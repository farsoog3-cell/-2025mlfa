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
CORS(app)  # يسمح بطلبات من الواجهات

# اسم ملف DST النموذجي الموجود في نفس المجلد
SAMPLE_DST_FILE = "sample.dst"

def pil_to_cv2(img_pil):
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

def extract_palette_from_sample(sample_path):
    """
    يقرأ ملف DST/ PES النموذجي ويستخرج قائمة الخيوط (RGB).
    يعيد قائمة من القيم [ [r,g,b], ... ] وقياس عرض التصميم بالمليمتر (تقديري).
    """
    pattern = read(sample_path, 'DST')  # إذا كان لديك PES بدّل 'DST' إلى 'PES'
    palette = []
    try:
        for th in pattern.threadlist:
            # pyembroidery يخزن خصائص الخيط كـ attributes red, green, blue
            palette.append([int(th.red), int(th.green), int(th.blue)])
    except Exception:
        # fallback: إن لم يوجد threadlist، استخدم لون افتراضي
        palette = [[0,0,0]]

    # استخراج مقاس عرض التصميم (bounds)، إذا لم يتوفر استخدم قيمة افتراضية 100 مم
    try:
        w_mm = pattern.bounds[2] - pattern.bounds[0]
        if w_mm <= 0:
            w_mm = 100.0
    except Exception:
        w_mm = 100.0

    return palette, w_mm

def quantize_image_to_palette(img_cv, palette):
    """
    يقلل ألوان الصورة إلى عدد ألوان مساوي لعدد الـ palette (أو أقل إذا palette كبيرة).
    ثم يعيد أقنعة لكل لون في palette بعد مطابقة كل مركز لون إلى أقرب لون في palette.
    """
    h,w = img_cv.shape[:2]
    n_colors = len(palette)
    # نفعل KMeans على الصورة للحصول على مراكز لونية
    pixels = img_cv.reshape(-1,3).astype(np.float32)
    if len(pixels) == 0:
        return []
    k = min(n_colors, 8)  # حد أعلى لسرعة المعالجة (يمكن زيادته)
    kmeans = KMeans(n_clusters=k, random_state=0, n_init=4)
    labels = kmeans.fit_predict(pixels)
    centers = np.uint8(kmeans.cluster_centers_)

    # لكل مركز، نجد أقرب لون في palette ونبني قناع
    masks = []
    for i, center in enumerate(centers):
        # نحسب أقرب لون من palette
        dists = np.linalg.norm(np.array(palette) - center, axis=1)
        nearest_idx = int(np.argmin(dists))
        mapped_color = palette[nearest_idx]
        # بناء القناع لمركز i
        mask = (labels.reshape(h,w) == i).astype(np.uint8) * 255
        masks.append({
            "mapped_color_idx": nearest_idx,
            "mapped_color_rgb": mapped_color,
            "mask": mask,
            "pixels_count": int(np.sum(mask>0))
        })
    return masks

def generate_hatch_stitches_from_mask(mask, step=6):
    """
    يولد نقاط غرز (x,y) داخل القناع باستخدام نمط hatch بسيط.
    step: البكسلات بين الغرز (كلما صغر أصبحت الكثافة أعلى)
    """
    ys, xs = np.where(mask>0)
    if len(xs) == 0:
        return []
    x_min, x_max = int(xs.min()), int(xs.max())
    y_min, y_max = int(ys.min()), int(ys.max())
    stitches = []
    # نقوم بمسح صفوف بفرق step ونضيف نقاط داخل القناع
    for y in range(y_min, y_max+1, step):
        row_xs = xs[ys == y]
        if len(row_xs) == 0:
            # وجد أي بكسل صحيح في هذا الصف؟ نستعمل البحث المحلي:
            row_xs = np.where(mask[y,:] > 0)[0]
            if len(row_xs) == 0:
                continue
        x_start = int(row_xs.min())
        x_end = int(row_xs.max())
        # نضيف نقاط من x_start إلى x_end بخطوة step
        for x in range(x_start, x_end+1, step):
            if mask[y, x] > 0:
                stitches.append((x, y))
    return stitches

@app.route("/generate_dst_from_image", methods=["POST"])
def generate_dst_from_image():
    try:
        # التحقق من وجود الصورة
        if 'image' not in request.files:
            return jsonify({"error":"يرجى رفع الصورة"}), 400

        # قراءة ملف العَيّنة لاستخراج palette وقياس العرض
        palette, sample_width_mm = extract_palette_from_sample(SAMPLE_DST_FILE)

        # قراءة الصورة المرفوعة
        img_pil = Image.open(request.files['image'].stream).convert("RGB")
        img_cv = pil_to_cv2(img_pil)
        h, w = img_cv.shape[:2]

        # نقوم بتقليل ألوان الصورة وتطابقها مع palette
        masks = quantize_image_to_palette(img_cv, palette)

        # نركب النمط الجديد
        pattern = EmbPattern()

        # مقياس التحويل: مم لكل بكسل بناء على sample_width_mm
        scale_mm_per_px = float(sample_width_mm) / float(max(w,1))

        # نولد الغرز لكل قناع بلون mapped_color
        colors_info = []
        for entry in masks:
            mapped_rgb = entry["mapped_color_rgb"]
            mask = entry["mask"]
            pixel_count = entry["pixels_count"]
            # اختيار كثافة بناءً على pixel_count — قاعدة بسيطة: أكثر بكسلات => كثافة أعلى (صغيرة):
            # نقيس step (البكسلات بين الغرز) بالعلاقة العكسية
            # step min = 3 (كثافة عالية)، max = 12 (كثافة منخفضة)
            density_factor = max(3, min(12, int(np.clip(20000.0 / (pixel_count+1), 3, 12))))
            stitches_px = generate_hatch_stitches_from_mask(mask, step=density_factor)

            # أضف غرز: نضيف تغيير لون (إن أمكن) قبل البدء باللون الجديد
            # pyembroidery قد يملك طريقة لإضافة تغيير اللون؛ إن لم تتوفر، سنستمر فقط بالغرزة
            try:
                # إذا كانت مكتبة pyembroidery تدعم add_color_change:
                pattern.add_color_change()
            except Exception:
                # تجاهل إن لم توجد
                pass

            # أضف غرز متسلسلة
            for (x_px, y_px) in stitches_px:
                x_mm = x_px * scale_mm_per_px
                y_mm = y_px * scale_mm_per_px
                pattern.add_stitch_absolute(float(x_mm), float(y_mm))

            # سجل معلومات اللون للواجهة
            colors_info.append({
                "hex": '#{:02x}{:02x}{:02x}'.format(int(mapped_rgb[0]), int(mapped_rgb[1]), int(mapped_rgb[2])),
                "stitches": len(stitches_px)
            })

        # اكتب الملف DST في الذاكرة وأعده
        buf = BytesIO()
        write_dst(pattern, buf)
        buf.seek(0)

        # أرسل الملف مع هيدر JSON بالألوان
        response = send_file(buf, download_name="ai_stitch.dst", mimetype="application/octet-stream")
        response.headers['X-Colors-Info'] = json.dumps(colors_info)
        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
