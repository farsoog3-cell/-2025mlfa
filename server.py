# server.py
from flask import Flask, request, jsonify
from pyembroidery import read

app = Flask(__name__)

@app.route("/extract_dst_info", methods=["POST"])
def extract_dst_info():
    if "file" not in request.files:
        return jsonify({"error":"يرجى رفع ملف DST"}), 400
    f = request.files["file"]
    pattern = read(f.stream)
    
    # ألوان الخيوط
    colors = [[th.red, th.green, th.blue] for th in pattern.threadlist]
    
    # الغرز
    stitches = []
    current_color_idx = 0
    for x,y,cmd in pattern.stitches:
        if cmd & 0x80:
            current_color_idx = (current_color_idx + 1) % len(colors)
            continue
        stitches.append({"x":x, "y":y, "color_idx":current_color_idx})
    
    return jsonify({"colors": colors, "stitches": stitches, "total_stitches": len(stitches)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
