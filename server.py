from flask import Flask, request, jsonify
from flask_cors import CORS
from pyembroidery import read
import os
import tempfile

app = Flask(__name__)
CORS(app)  # يسمح لأي صفحة بالوصول

@app.route("/extract_dst_info", methods=["POST"])
def extract_dst_info():
    if "file" not in request.files:
        return jsonify({"error":"يرجى رفع ملف DST/PES"}), 400

    f = request.files["file"]

    try:
        # حفظ الملف مؤقتًا على الخادم
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f.filename)
        f.save(temp_path)

        # قراءة الملف بواسطة pyembroidery
        pattern = read(temp_path)

        # حذف الملف المؤقت بعد القراءة
        os.remove(temp_path)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # استخراج ألوان الخيوط
    colors = [[th.red, th.green, th.blue] for th in pattern.threadlist]
    if not colors:
        colors = [[0,0,0]]

    # استخراج الغرز
    stitches = []
    current_color_idx = 0
    for x, y, cmd in pattern.stitches:
        if cmd & 0x80:  # تغيير لون
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
