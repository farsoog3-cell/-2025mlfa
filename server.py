# pip install flask pyembroidery flask-cors pillow numpy
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyembroidery import read
from io import BytesIO

app = Flask(__name__)
CORS(app)  # يسمح للصفحات بالوصول

@app.route("/extract_dst_info", methods=["POST"])
def extract_dst_info():
    if "file" not in request.files:
        return jsonify({"error":"يرجى رفع ملف DST"}), 400

    f = request.files["file"]
    try:
        # تحويل الملف إلى BytesIO قبل القراءة
        file_bytes = f.read()
        pattern = read(BytesIO(file_bytes))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ألوان الخيوط
    colors = [[th.red, th.green, th.blue] for th in pattern.threadlist]
    if not colors:
        colors = [[0,0,0]]

    # الغرز
    stitches = []
    current_color_idx = 0
    for x, y, cmd in pattern.stitches:
        if cmd & 0x80:
            current_color_idx = (current_color_idx + 1) % len(colors)
            continue
        stitches.append({"x": x, "y": y, "color_idx": current_color_idx})

    return jsonify({
        "colors": colors,
        "stitches": stitches,
        "total_stitches": len(stitches)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
