from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst, write_dse
from PIL import Image
import numpy as np
from io import BytesIO

app = Flask(__name__)
CORS(app)

def remove_background(image):
    # إزالة الخلفية البيضاء
    image_np = np.array(image.convert('RGB'))
    mask = np.all(image_np > 240, axis=2)
    image_np[mask] = [255,255,255]
    return Image.fromarray(image_np)

def create_embroidery(image):
    # تحويل الصورة إلى grayscale
    image = image.convert('L')
    image = image.resize((200,200))
    pixels = np.array(image)

    pattern = EmbPattern()

    # تحويل البكسلات الداكنة إلى نقاط تطريز
    for y in range(0, pixels.shape[0], 2):
        for x in range(0, pixels.shape[1], 2):
            if pixels[y,x] < 128:
                pattern.add_stitch_absolute(x, y)

    # تحقق من وجود نقاط
    if len(pattern.stitches) == 0:
        # إذا لم توجد نقاط، أعد المعالجة بتعديل threshold
        for y in range(0, pixels.shape[0], 2):
            for x in range(0, pixels.shape[1], 2):
                if pixels[y,x] < 200:
                    pattern.add_stitch_absolute(x, y)

    return pattern

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400

    file = request.files['file']
    format_type = request.form.get('format','DST')  # DST أو DSE
    img = Image.open(file.stream).convert('RGB')
    img = remove_background(img)
    pattern = create_embroidery(img)

    bio = BytesIO()
    if format_type.upper() == 'DSE':
        write_dse(pattern, bio)
    else:
        write_dst(pattern, bio)
    bio.seek(0)

    filename = f'pattern.{format_type.lower()}'
    return send_file(
        bio,
        download_name=filename,
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
