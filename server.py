from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pyembroidery import EmbPattern, write_dst
from PIL import Image
import numpy as np
from io import BytesIO

app = Flask(__name__)
CORS(app)

def remove_background(image):
    image_np = np.array(image.convert('RGB'))
    mask = np.all(image_np > 240, axis=2)
    image_np[mask] = [255,255,255]
    return Image.fromarray(image_np)

def create_embroidery(image):
    image = image.convert('L').resize((200,200))
    pixels = np.array(image)
    pattern = EmbPattern()
    for y in range(0, pixels.shape[0], 2):
        for x in range(0, pixels.shape[1], 2):
            if pixels[y,x] < 128:
                pattern.add_stitch_absolute(x, y)
    if len(pattern.stitches) == 0:
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
    img = Image.open(file.stream).convert('RGB')
    img = remove_background(img)
    pattern = create_embroidery(img)
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return send_file(
        bio,
        download_name='pattern.dst',
        mimetype='application/octet-stream'
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
