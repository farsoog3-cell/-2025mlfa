from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, EmbThread, commands
from PIL import Image
import numpy as np
from io import BytesIO
import matplotlib.pyplot as plt
import os

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# إنشاء مخطط التطريز الملون
def create_colored_pattern(image):
    image = image.resize((200, 200)).convert("RGB")
    pixels = np.array(image)
    pattern = EmbPattern()
    # استخراج الألوان الرئيسية (حتى 5 ألوان)
    unique_colors = np.unique(pixels.reshape(-1, 3), axis=0)

    step = 3
    for color in unique_colors[:5]:
        thread = EmbThread()
        thread.set_color(int(color[0]), int(color[1]), int(color[2]))
        thread.description = f"Thread {color}"
        pattern.add_thread(thread)

        for y in range(0, pixels.shape[0], step):
            row_points = []
            for x in range(0, pixels.shape[1], step):
                if np.allclose(pixels[y, x], color, atol=40):
                    row_points.append((x, y))
            if row_points:
                pattern.add_command(commands.CMD_JUMP)
                pattern.add_stitch_absolute(*row_points[0])
                for (x, y) in row_points[1:]:
                    pattern.add_stitch_absolute(x, y)
    return pattern

# حفظ صور المعاينة
def save_previews(image, pattern, base_name):
    img_np = np.array(image.convert("RGB"))

    preview_path = os.path.join(UPLOAD_FOLDER, f"{base_name}_preview.png")
    path_path = os.path.join(UPLOAD_FOLDER, f"{base_name}_stitch_path.png")

    # صورة التطريز الملون
    plt.figure(figsize=(6,6))
    plt.imshow(img_np)
    plt.axis("off")
    plt.savefig(preview_path, bbox_inches='tight')
    plt.close()

    # مخطط مسار الإبرة
    xs, ys = [], []
    for st in pattern.stitches:
        xs.append(st[0])
        ys.append(st[1])

    plt.figure(figsize=(6,6))
    plt.imshow(img_np)
    plt.plot(xs, ys, color="red", linewidth=0.8)
    plt.axis("off")
    plt.savefig(path_path, bbox_inches='tight')
    plt.close()

    return preview_path, path_path

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    img = Image.open(file.stream).convert('RGB')

    base_name = os.path.splitext(file.filename)[0]

    # إنشاء مخطط التطريز
    pattern = create_colored_pattern(img)

    # حفظ الصور
    preview_path, path_path = save_previews(img, pattern, base_name)

    # إنشاء ملف DST في الذاكرة
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)

    return send_file(
        bio,
        as_attachment=True,
        download_name=f'{base_name}.dst',
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
