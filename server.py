# server.py
from flask import Flask, request, send_file
from pyembroidery import EmbPattern, STITCH, write_pes
import io
import math

app = Flask(__name__)

@app.route("/generate_pes", methods=["POST"])
def generate_pes():
    data = request.get_json()
    points = data.get("points", [])

    if not points:
        return "لا توجد نقاط غرز!", 400

    pattern = EmbPattern()
    last_point = None

    for pt in points:
        x, y = pt['x'], pt['y']
        g_type = pt.get('type','fill')
        angle = pt.get('angle',0)

        # إضافة Jump إذا المسافة كبيرة
        if last_point:
            dx = x - last_point[0]
            dy = y - last_point[1]
            distance = math.hypot(dx, dy)
            if distance > 20:
                pattern.add_jump_absolute(x, y)

        # إضافة الغرز حسب نوع المنطقة
        if g_type=='fill':
            pattern.add_stitch_absolute(x, y)
        elif g_type=='edge':
            pattern.add_stitch_absolute(x, y) # يمكن تطوير Satin Edge حقيقي لاحقاً
        elif g_type=='satin':
            # إنشاء خطوط طويلة حسب الزاوية
            length = 6
            x2 = x + length*math.cos(angle)
            y2 = y + length*math.sin(angle)
            pattern.add_stitch_absolute(x, y)
            pattern.add_stitch_absolute(x2, y2)
        else:
            pattern.add_stitch_absolute(x, y)

        last_point = (x, y)

    pattern.end()
    file_stream = io.BytesIO()
    write_pes(pattern, file_stream)
    file_stream.seek(0)

    return send_file(
        file_stream,
        mimetype="application/octet-stream",
        download_name="output.pes"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
