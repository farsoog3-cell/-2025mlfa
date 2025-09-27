from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from werkzeug.utils import secure_filename
import os, cv2
from datetime import datetime
from pyembroidery import EmbPattern, EmbThread, write_dst, write_exp
from PIL import Image, ImageDraw

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/embroidery', methods=['POST'])
def embroidery():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    file = request.files['file']
    fmt = request.form.get('format', 'dst').lower()
    emb_type = request.form.get('embType', 'outline')

    # حفظ الصورة المرفوعة
    img_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(img_path)

    # معالجة الصورة
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    img = cv2.resize(img, (300, 300))
    _, thresh = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)

    pattern = EmbPattern()
    thread = EmbThread()
    thread.set_color(0, 0, 0)
    pattern.add_thread(thread)

    preview = Image.new("RGB", (300, 300), "white")
    draw = ImageDraw.Draw(preview)

    if emb_type in ["outline", "both"]:
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            if len(contour) < 2:
                continue
            for i, pt in enumerate(contour):
                x, y = pt[0]
                if i == 0:
                    pattern.add_stitch_absolute("JUMP", x, y)
                else:
                    pattern.add_stitch_absolute("STITCH", x, y)
            draw.line([tuple(p[0]) for p in contour], fill="black", width=1)

    if emb_type in ["fill", "both"]:
        step = 5
        for y in range(0, img.shape[0], step):
            row = []
            for x in range(img.shape[1]):
                if thresh[y, x] == 255:
                    row.append((x, y))
            if row:
                pattern.add_stitch_absolute("JUMP", row[0][0], row[0][1])
                for pt in row:
                    pattern.add_stitch_absolute("STITCH", pt[0], pt[1])
                draw.line(row, fill="black", width=1)

    pattern.end()

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    if fmt == "dst":
        filename = f"pattern_{timestamp}.dst"
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "wb") as f:
            write_dst(f, pattern)
    else:
        filename = f"pattern_{timestamp}.exp"
        with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "wb") as f:
            write_exp(f, pattern)

    preview_name = f"preview_{timestamp}.png"
    preview.save(os.path.join(app.config['UPLOAD_FOLDER'], preview_name))

    return jsonify({
        "success": True,
        "preview_url": url_for("uploaded_file", filename=preview_name),
        "download_url": url_for("uploaded_file", filename=filename)
    })

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
