from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes, STITCH, JUMP
from io import BytesIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # السماح للصفحة بالاتصال من دومين آخر

@app.route('/generate_pes', methods=['POST'])
def generate_pes():
    try:
        data = request.get_json()
        paths = data.get('paths', [])

        if not paths:
            return {"error": "لا توجد مسارات غرز"}, 400

        # إنشاء نمط التطريز
        pattern = EmbPattern()
        for path in paths:
            if not path:
                continue
            # أول نقطة: JUMP (تحريك الإبرة دون خياطة)
            first = path[0]
            pattern.add_stitch_absolute(JUMP, first['x'], first['y'])

            # باقي النقاط: STITCH (غرز متصلة)
            for pt in path[1:]:
                pattern.add_stitch_absolute(STITCH, pt['x'], pt['y'])

        # إنهاء التصميم
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
