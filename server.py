# smart_server.py
from flask import Flask, request, jsonify, send_file, url_for
from pyembroidery import EmbPattern, write_pes
from PIL import Image, ImageOps
import cv2
import numpy as np
import io, os, math, uuid, base64

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def remove_background(img):
    """ إزالة الخلفية البيضاء وتحويلها شفافة """
    img = img.convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        if item[0] > 200 and item[1] > 200 and item[2] > 200:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)
    img.putdata(newData)
    return img

def preprocess_image(img, option="none"):
    """ تنفيذ معالجة الصورة حسب الاختيار """
    if option in ["remove_bg", "both"]:
        img = remove_background(img)
    if option in ["bw", "both"]:
        img = img.convert("L")
    return img

def analyze_stitches(img):
    """ تحليل الصورة واستخراج نقاط الغرز الذكية """
    if img.mode != "L":
        gray = img.convert("L")
    else:
        gray = img

    # تحويل إلى numpy array
    np_img = np.array(gray)
    # استخدام Canny لاكتشاف الحواف
    edges = cv2.Canny(np_img, 100, 200)
    height, width = edges.shape
    stitchPoints = []

    step = 4
    for y in range(0, height, step):
        rowPoints = []
        for x in range(0, width, step):
            if edges[y, x] > 0:
                rowPoints.append({'x': int(x), 'y': int(y), 'type': 'fill'})
        if (y // step) % 2 == 1:
            rowPoints.reverse()
        stitchPoints.extend(rowPoints)
    return stitchPoints

@app.route("/process_image", methods=["POST"])
def process_image():
    try:
        if 'image' not in request.files:
            return "لا توجد صورة!", 400
        file = request.files['image']
        img = Image.open(file)

        processing_option = request.form.get('processing', 'none')

        # حفظ الصورة الأصلية Base64
        original_io = io.BytesIO()
        img.save(original_io, format='PNG')
        original_io.seek(0)
        original_data = "data:image/png;base64," + base64.b64encode(original_io.getvalue()).decode()

        # معالجة ذكية
        img_processed = preprocess_image(img, processing_option)

        # حفظ الصورة بعد المعالجة Base64
        processed_io = io.BytesIO()
        img_processed.save(processed_io, format='PNG')
        processed_io.seek(0)
        processed_data = "data:image/png;base64," + base64.b64encode(processed_io.getvalue()).decode()

        # استخراج نقاط الغرز
        stitchPoints = analyze_stitches(img_processed)

        # إنشاء ملف PES ذكي
        pattern = EmbPattern()
        last_point = None
        for pt in stitchPoints:
            x, y = pt['x'], pt['y']
            if last_point:
                distance = math.hypot(x - last_point[0], y - last_point[1])
                if distance > 20:
                    pattern.add_jump_absolute(int(x), int(y))
            pattern.add_stitch_absolute(int(x), int(y))
            last_point = (x, y)
        pattern.end()

        # حفظ الملف PES مؤقتًا
        pes_filename = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4()) + ".pes")
        write_pes(pattern, pes_filename)

        return jsonify({
            'original': original_data,
            'processed': processed_data,
            'stitchPoints': stitchPoints,
            'pes': url_for('get_file', filename=os.path.basename(pes_filename))
        })

    except Exception as e:
        import traceback
        print("Error in /process_image:", e)
        traceback.print_exc()
        return f"حدث خطأ أثناء المعالجة: {str(e)}", 500

@app.route('/file/<filename>')
def get_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
