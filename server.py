from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, EmbThread, commands
from PIL import Image
import numpy as np
from io import BytesIO
import base64

app = Flask(__name__)
CORS(app)

# إنشاء مخطط التطريز الملون
def create_colored_pattern(image):
    image = image.resize((200, 200)).convert("RGB")
    pixels = np.array(image)
    pattern = EmbPattern()

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

# إنشاء معاينة بالصور مباشرة كـ Base64
def get_previews_base64(image, pattern):
    # معاينة التطريز الملون
    preview_buf = BytesIO()
    image.save(preview_buf, format="PNG")
    preview_b64 = base64.b64encode(preview_buf.getvalue()).decode('utf-8')

    # مخطط مسار الإبرة
    import matplotlib.pyplot as plt
    xs, ys = [], []
    for st in pattern.stitches:
        xs.append(st[0])
        ys.append(st[1])

    plt.figure(figsize=(6,6))
    plt.imshow(np.array(image.convert("RGB")))
    plt.plot(xs, ys, color="red", linewidth=0.8)
    plt.axis("off")

    path_buf = BytesIO()
    plt.savefig(path_buf, format="PNG", bbox_inches='tight')
    plt.close()
    path_b64 = base64.b64encode(path_buf.getvalue()).decode('utf-8')

    return preview_b64, path_b64

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    img = Image.open(file.stream).convert('RGB')
    base_name = file.filename.split('.')[0]

    # إنشاء المخطط
    pattern = create_colored_pattern(img)

    # توليد معاينات Base64
    preview_b64, path_b64 = get_previews_base64(img, pattern)

    # ملف DST في الذاكرة
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    dst_b64 = base64.b64encode(bio.getvalue()).decode('utf-8')

    return jsonify({
        'dst_file': dst_b64,
        'preview_image': preview_b64,
        'stitch_path': path_b64,
        'filename': f"{base_name}.dst"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
