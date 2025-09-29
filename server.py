from flask import Flask, request, jsonify, send_file, url_for
from pyembroidery import EmbPattern, STITCH, JUMP, write_pes
from PIL import Image, ImageFilter
import io, os, uuid, math, base64
import numpy as np

app = Flask(__name__)
UPLOAD_FOLDER = "/tmp"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# فتح الصورة بأمان
def safe_open_image(file):
    try:
        img = Image.open(file).convert("RGBA")
        return img
    except Exception as e:
        raise ValueError(f"فشل فتح الصورة: {e}")

# معالجة الصورة تلقائيًا
def process_image_ai(img):
    try:
        data = np.array(img)
        r,g,b,a = data[:,:,0], data[:,:,1], data[:,:,2], data[:,:,3]
        mask = (r>200)&(g>200)&(b>200)
        data[:,:,3][mask] = 0
        img = Image.fromarray(data)
        gray = img.convert("L").filter(ImageFilter.GaussianBlur(1))
        arr = np.array(gray)
        threshold = np.mean(arr)
        bw_arr = np.where(arr<threshold,0,255).astype(np.uint8)
        return Image.fromarray(bw_arr)
    except Exception as e:
        raise ValueError(f"فشل المعالجة: {e}")

# تقسيم الصورة إلى مناطق
def segment_colors(img, max_colors=3):
    img_small = img.resize((max(1,img.width//4), max(1,img.height//4)))
    arr = np.array(img_small)
    if len(arr.shape)!=3:
        arr = np.stack([arr]*3, axis=-1)
    colors = np.unique(arr.reshape(-1, arr.shape[2]), axis=0)
    if len(colors)>max_colors:
        colors = colors[:max_colors]
    regions=[]
    for color in colors:
        mask=np.all(arr==color,axis=2)
        y_idx,x_idx=np.where(mask)
        points=[{'x':int(x*4),'y':int(y*4),'color':tuple(color)} for x,y in zip(x_idx,y_idx)]
        regions.append(points)
    return regions

# توليد مسارات الغرز
def generate_stitch_pattern(regions):
    pattern = EmbPattern()
    for region in regions:
        last_point = None
        for pt in region:
            x,y = pt['x'], pt['y']
            if last_point:
                dist = math.hypot(x-last_point[0],y-last_point[1])
                if dist>20:
                    pattern.add_command(JUMP, x, y)
            pattern.add_command(STITCH, x, y)
            last_point = (x,y)
    pattern.end()
    return pattern

@app.route("/process_image", methods=["POST"])
def process_image_route():
    log_steps=[]
    try:
        if 'image' not in request.files:
            return jsonify({'error':'لا توجد صورة!','log':[]}),400
        file = request.files['image']
        img = safe_open_image(file)
        log_steps.append("تم فتح الصورة بنجاح")

        processed_img = process_image_ai(img)
        log_steps.append("تمت معالجة الصورة")

        # حفظ الصورة المعالجة
        processed_io = io.BytesIO()
        processed_img.save(processed_io, format='PNG')
        processed_io.seek(0)
        processed_data = "data:image/png;base64," + base64.b64encode(processed_io.getvalue()).decode()

        # تحليل المناطق
        regions = segment_colors(processed_img)
        stitch_points = []
        for region in regions:
            stitch_points.extend(region)
        log_steps.append(f"تم تحديد مناطق الغرز وعدد الغرز: {len(stitch_points)}")

        # توليد ملف PES
        pattern = generate_stitch_pattern(regions)
        pes_filename = os.path.join(UPLOAD_FOLDER, str(uuid.uuid4())+".pes")
        write_pes(pattern, pes_filename)
        log_steps.append(f"تم إنشاء ملف PES: {os.path.basename(pes_filename)}")

        return jsonify({
            'processed': processed_data,
            'stitchPoints': stitch_points,
            'pes': url_for('get_file', filename=os.path.basename(pes_filename)),
            'log': log_steps
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error':f"حدث خطأ أثناء المعالجة: {str(e)}",'log':log_steps}),500

@app.route('/file/<filename>')
def get_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
