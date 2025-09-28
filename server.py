from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes, END, STITCH
from io import BytesIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        data = request.get_json()
        points = data.get('points', [])

        if not points:
            return {"error": "لا توجد نقاط غرز"}, 400

        # إنشاء نمط التطريز
        pattern = EmbPattern()

        scale = 0.2  # تصغير الحجم من بكسلات إلى مليمترات تقريبياً
        first = True
        for pt in points:
            x = pt.get('x', 0) * scale
            y = pt.get('y', 0) * scale
            if first:
                # أول غرزة كبداية
                pattern.add_stitch_absolute(STITCH, x, y)
                first = False
            else:
                # باقي الغرز
                pattern.add_stitch_absolute(STITCH, x, y)

        # إنهاء الملف بشكل صحيح
        pattern.end()

        # إنشاء ملف PES في الذاكرة
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
