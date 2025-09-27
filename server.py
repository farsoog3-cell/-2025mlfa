from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, EmbThread, commands
from PIL import Image
import numpy as np
from io import BytesIO
import matplotlib.pyplot as plt

app = Flask(__name__)
CORS(app)


def create_colored_pattern(image):
    image = image.resize((200, 200)).convert("RGB")
    pixels = np.array(image)

    pattern = EmbPattern()

    # استخرج الألوان الرئيسية من الصورة
    unique_colors = np.unique(pixels.reshape(-1, 3), axis=0)

    step = 3  # دقة الغرز (كل 3 بكسلات)

    for color in unique_colors[:5]:  # نحدد 5 ألوان فقط عشان البساطة
        # إضافة خيط جديد بنفس اللون
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
                # قفزة قبل بداية الغرز الجديدة
                pattern.add_command(commands.CMD_JUMP)
                pattern.add_stitch_absolute(*row_points[0])

                # رسم الغرز المتصلة
                for (x, y) in row_points[1:]:
                    pattern.add_stitch_absolute(x, y)

    return pattern


def save_previews(image, pattern):
    # صورة المعاينة بالألوان
    img_np = np.array(image.convert("RGB"))
    plt.figure(figsize=(6, 6))
    plt.imshow(img_np)
    plt.title("Preview of Embroidery")
    plt.axis("off")
    plt.savefig("preview.png")
    plt.close()

    # صورة مسار الغرز (المخطط)
    xs, ys = [], []
    for st in pattern.stitches:
        xs.append(st[0])
        ys.append(st[1])

    plt.figure(figsize=(6, 6))
    plt.imshow(img_np)
    plt.plot(xs, ys, color="red", linewidth=0.8)
    plt.title("Stitch Path (Needle Movement)")
    plt.axis("off")
    plt.savefig("stitch_path.png")
    plt.close()


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    img = Image.open(file.stream).convert('RGB')

    # إنشاء المخطط
    pattern = create_colored_pattern(img)

    # حفظ صور المعاينة
    save_previews(img, pattern)

    # كتابة ملف DST في الذاكرة
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)

    return send_file(
        bio,
        as_attachment=True,
        download_name='pattern.dst',
        mimetype='application/octet-stream'
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
