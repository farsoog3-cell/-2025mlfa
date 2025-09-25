from pyembroidery import EmbPattern, write_dst
from PIL import Image
import numpy as np
import cv2
from io import BytesIO
from flask import Flask, request, send_file, jsonify

app = Flask(__name__)

def remove_background(image):
    image_np = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(image_np, cv2.COLOR_RGB2GRAY)
    _, mask = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    image_np[mask==0] = [255, 255, 255]
    return Image.fromarray(image_np)

def create_embroidery(image):
    pattern = EmbPattern()
    image = image.convert('L').resize((200,200))
    pixels = np.array(image)
    for y in range(0, pixels.shape[0], 5):
        for x in range(0, pixels.shape[1], 5):
            if pixels[y,x] < 128:
                pattern.add_stitch_absolute(x, y)
    bio = BytesIO()
    write_dst(pattern, bio)  # فقط DST متاح
    bio.seek(0)
    return bio

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}), 400
    file = request.files['file']
    img = Image.open(file.stream).convert('RGB')
    img = remove_background(img)
    embroidery_file = create_embroidery(img)
    return send_file(
        embroidery_file,
        download_name='pattern.dst',
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
