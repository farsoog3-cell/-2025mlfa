# server.py
from flask import Flask, request, jsonify, send_file, url_for
from pyembroidery import EmbPattern, STITCH, write_pes
from PIL import Image, ImageOps
import io
import os
import math
import uuid
import base64

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def remove_background(img):
    """
    إزالة الخلفية البيضاء من الصورة
    """
    img = img.convert("RGBA")
    datas = img.getdata()
    newData = []
    for item in datas:
        # إذا كانت البيكسلات فاتحة جدًا، اجعلها شفافة
        if item[0]>200 and item[1]>200 and item[2]>200:
            newData.append((255,255,255,0))
        else:
            newData.append(item)
    img.putdata(newData)
    return img

@app.route("/process_image", methods=["POST"])
def process_image():
    if 'image' not in request.files:
        return "لا توجد صورة!", 400

    file = request.files['image']
    img = Image.open(file)

    # حفظ الصورة الأصلية مؤقتًا
    original_io = io.BytesIO()
    img.save(original_io, format='PNG')
    original_io.seek(0)
    original_data = "data:image/png;base64," + base64.b64encode(original_io.getvalue()).decode()

    # إزالة الخلفية
    img_no_bg = remove_background(img)

    # تحويل أبيض وأسود
    bw = img_no_bg.convert("L")  # تحويل إلى Grayscale فقط

    processed_io = io.BytesIO()
    bw.save(processed_io, format='PNG')
    processed_io.seek(0)
    processed_data = "data:image/png;base64," + base64.b64encode(processed_io.getvalue()).decode()

    # تحليل الغرز (zig-zag)
    stitchPoints = []
    step = 4
    width, height = bw.size

    for y in range(0,height,step):
        rowPoints=[]
        for x in range(0,width,step):
            gray = bw.getpixel((x,y))  # int، لأن الصورة الآن Grayscale
            if gray < 128:
                rowPoints.append({'x':x,'y':y,'type':'fill'})
        if (y//step)%2 == 1:
            rowPoints.reverse()  # ترتيب zig-zag لتقليل القفزات
        stitchPoints.extend(rowPoints)

    # إنشاء ملف PES
    pattern = EmbPattern()
    last_point = None
    for pt in stitchPoints:
        x,y = pt['x'], pt['y']
        if last_point:
            distance = math.hypot(x-last_point[0], y-last_point[1])
            if distance > 20:
                pattern.add_jump_absolute(x, y)
        pattern.add_stitch_absolute(x, y)
        last_point = (x, y)
    pattern.end()

    pes_filename = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4())+".pes")
    write_pes(pattern, pes_filename)

    return jsonify({
        'original': original_data,
        'processed': processed_data,
        'stitchPoints': stitchPoints,
        'pes': url_for('get_file', filename=os.path.basename(pes_filename))
    })

@app.route('/file/<filename>')
def get_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
