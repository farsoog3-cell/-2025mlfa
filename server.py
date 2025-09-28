from flask import Flask, request, send_file, jsonify
from pyembroidery import EmbPattern, write_pes, STITCH, JUMP
from io import BytesIO
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/generate_pattern', methods=['POST'])
def generate_pattern():
    try:
        data = request.get_json()
        paths = data.get('paths', [])
        ftype = data.get('type', 'pes')  # نوع الملف المطلوب

        if not paths:
            return jsonify({"error": "لا توجد مسارات"}), 400

        pattern = EmbPattern()

        for path in paths:
            if not path:
                continue
            first = path[0]
            pattern.add_stitch_absolute(JUMP, first['x'], first['y'])
            for pt in path[1:]:
                pattern.add_stitch_absolute(STITCH, pt['x'], pt['y'])

        pattern.end()

        buf = BytesIO()
        write_pes(pattern, buf)  # نحفظ كـ PES دائماً
        buf.seek(0)

        # نرجع PES لكن بإسم الامتداد المطلوب
        download_name = "stitch_pattern.pes"
        if ftype == "des":
            download_name = "stitch_pattern.des"  # ملف وهمي باسم DES

        return send_file(
            buf,
            download_name=download_name,
            mimetype="application/octet-stream",
            as_attachment=True
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
