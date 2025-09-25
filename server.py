from flask import Flask, request, send_file, jsonify
from pyembroidery import EmbPattern, write_dst, write_dse
from PIL import Image
import numpy as np
import cv2
from io import BytesIO

app = Flask(__name__)

# --- إزالة الخلفية تلقائيًا ---
def remove_background(image):
    image_np = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    image_np[mask==0] = [255, 255, 255]
    return Image.fromarray(image_np)

# --- إنشاء القالب DST/DSE ---
def create_embroidery(image, format='DST'):
    pattern = EmbPattern()
    image = image.convert('L').resize((200,200))
    pixels = np.array(image)
    for y in range(0, pixels.shape[0], 5):
        for x in range(0, pixels.shape[1], 5):
            if pixels[y,x] < 128:
                pattern.add_stitch_absolute(x, y)
    bio = BytesIO()
    if format.upper() == 'DST':
        write_dst(pattern, bio)
    else:
        write_dse(pattern, bio)
    bio.seek(0)
    return bio

# --- نقطة النهاية API للرفع ---
@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400
    file = request.files['file']
    format_type = request.form.get('format', 'DST')
    img = Image.open(file.stream).convert('RGB')
    img = remove_background(img)
    embroidery_file = create_embroidery(img, format=format_type)
    return send_file(
        embroidery_file,
        download_name=f'pattern.{format_type.lower()}',
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    app.run(debug=True)
