from flask import Flask, request, jsonify, send_file
import os, cv2, numpy as np
from pyembroidery import EmbPattern, write_dst

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

stitch_data = []

@app.route("/upload", methods=["POST"])
def upload_image():
    global stitch_data
    stitch_data = []
    file = request.files['image']
    filepath = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(filepath)

    # معالجة الصورة وتحويلها إلى حواف
    img = cv2.imread(filepath)
    img = cv2.resize(img, (500, 500))
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)

    # توليد غرز حول الحواف
    pattern = EmbPattern()
    height, width = edges.shape
    for y in range(0, height, 2):
        for x in range(0, width, 2):
            if edges[y, x] > 0:
                pattern.add_stitch_absolute(x, y)
                stitch_data.append(((x, y), (x+1, y+1), "#000"))

    output_path = os.path.join(UPLOAD_FOLDER, "output.dst")
    write_dst(pattern, output_path)
    return jsonify({"stitches": stitch_data})

@app.route("/download")
def download():
    return send_file(os.path.join(UPLOAD_FOLDER, "output.dst"), as_attachment=True)

if __name__ == "__main__":
    # يمكنك تغيير host وport إذا لزم
    app.run(debug=True)
