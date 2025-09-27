from flask import Flask, request, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, EmbThread, commands
from PIL import Image
import numpy as np
from io import BytesIO
import base64

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # السماح لجميع المواقع

# إنشاء مخطط التطريز الملون
def create_colored_pattern(image):
    image = image.resize((200, 200)).convert("RGB")
    pixels = np.array(image)
    pattern = EmbPattern()
    unique_colors = np.unique(pixels.reshape(-1, 3), axis=0)
    step = 3
    stitch_points = []

    for color in unique_colors[:5]:  # استخدام أول 5 ألوان
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
                stitch_points.append({'x': row_points[0][0], 'y': row_points[0][1]})
                for (x, y) in row_points[1:]:
                    pattern.add_stitch_absolute(x, y)
                    stitch_points.append({'x': x, 'y': y})
    return pattern, stitch_points

# إنشاء معاينة بالصورة كـ Base64
def get_preview_base64(image):
    buf = BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400

        file = request.files['file']
        img = Image.open(file.stream).convert('RGB')
        pattern, stitch_points = create_colored_pattern(img)

        # ملف DST في الذاكرة
        bio = BytesIO()
        write_dst(pattern, bio)
        bio.seek(0)
        dst_b64 = base64.b64encode(bio.getvalue()).decode('utf-8')

        # معاينة الصورة
        preview_b64 = get_preview_base64(img)

        return jsonify({
            'dst_file': dst_b64,
            'preview_image': preview_b64,
            'stitch_points': stitch_points,
            'filename': f"{file.filename.split('.')[0]}.dst"
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
