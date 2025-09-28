from flask import Flask, request, send_file
from flask_cors import CORS
from pyembroidery import EmbPattern, write_pes
import cv2
import numpy as np
from io import BytesIO

app = Flask(__name__)
CORS(app)

def process_image_to_stitches(image_bytes, step=3, threshold=127):
    # قراءة الصورة من الذاكرة
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

    # تحويل الصورة إلى أبيض وأسود
    _, bw = cv2.threshold(img, threshold, 255, cv2.THRESH_BINARY_INV)

    # استخراج Contours
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # إنشاء نمط التطريز
    pattern = EmbPattern()

    # تحويل Contours إلى نقاط غرز
    for contour in contours:
        contour = contour.reshape(-1, 2)
        for i in range(0, len(contour), step):
            x, y = contour[i]
            pattern.add_stitch_absolute(x, y)

    # إنهاء الغرز
    pattern.add_command("END")
    return pattern

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        if 'image' not in request.files:
            return {"error": "يرجى رفع صورة"}, 400

        image_file = request.files['image']
        image_bytes = image_file.read()

        pattern = process_image_to_stitches(image_bytes)

        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)

        return send_file(
            buf,
            download_name="stitch_pattern.pes",
            mimetype="application/octet-stream"
        )

    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    
