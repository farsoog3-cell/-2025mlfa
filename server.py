# ai_embroidery_server_updated.py
from flask import Flask, request, jsonify, send_file, url_for
from pyembroidery import EmbPattern, write_pes
from PIL import Image, ImageOps, ImageFilter
import io, os, math, uuid, base64
import numpy as np

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def ai_remove_background(img):
    """إزالة الخلفية البيضاء بطريقة ذكية"""
    img = img.convert("RGBA")
    data = np.array(img)
    r, g, b, a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
    mask = (r > 200) & (g > 200) & (b > 200)
    data[:,:,3][mask] = 0
    return Image.fromarray(data)

def ai_convert_bw(img):
    """تحويل ذكي إلى أبيض وأسود"""
    gray = img.convert("L").filter(ImageFilter.GaussianBlur(1))
    arr = np.array(gray)
    threshold = np.mean(arr)
    bw_arr = np.where(arr < threshold, 0, 255).astype(np.uint8)
    return Image.fromarray(bw_arr)

@app.route("/process_image", methods=["POST"])
def process_image():
    try:
        if 'image' not in request.files:
            return "لا توجد صورة!", 400
        file = request.files['image']
        img = Image.open(file)

        # حفظ الصورة الأصلية
        original_io = io.BytesIO()
        img.save(original_io, format='PNG')
        original_io.seek(0)
        original_data = "data:image/png;base64," + base64.b64encode(original_io.getvalue()).decode()

        # خيارات المعالجة
        processing = request.form.get('processing', 'both')  # default 'both'
        log_steps = []

        if processing in ['remove_bg', 'both']:
            img = ai_remove_background(img)
            log_steps.append("تم إزالة الخلفية باستخدام الذكاء الصناعي")
        if processing in ['bw', 'both']:
            img = ai_convert_bw(img)
            log_steps.append("تم تحويل الصورة إلى أبيض وأسود باستخدام الذكاء الصناعي")
        if processing == 'none':
            log_steps.append("لم يتم تطبيق أي معالجة على الصورة (none)")

        # حفظ الصورة المعالجة
        processed_io = io.BytesIO()
        img.save(processed_io, format='PNG')
        processed_io.seek(0)
        processed_data = "data:image/png;base64," + base64.b64encode(processed_io.getvalue()).decode()

        # استخراج نقاط الغرز
        step = 4
        width, height = img.size
        stitchPoints = []
        bw_img = img.convert("L")
        arr = np.array(bw_img)
        for y in range(0, height, step):
            rowPoints = []
            for x in range(0, width, step):
                gray = arr[y, x] if len(arr.shape)==2 else arr[y,x,0]
                if gray < 128:
                    rowPoints.append({'x': int(x), 'y': int(y), 'type': 'fill'})
            if (y//step)%2 == 1:
                rowPoints.reverse()
            stitchPoints.extend(rowPoints)
        log_steps.append(f"تم استخراج نقاط الغرز. عدد الغرز: {len(stitchPoints)}")

        # إنشاء ملف PES
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
        pes_filename = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4())+".pes")
        write_pes(pattern, pes_filename)
        log_steps.append(f"تم إنشاء ملف PES: {os.path.basename(pes_filename)}")

        return jsonify({
            'original': original_data,
            'processed': processed_data,
            'stitchPoints': stitchPoints,
            'pes': url_for('get_file', filename=os.path.basename(pes_filename)),
            'log': log_steps
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
