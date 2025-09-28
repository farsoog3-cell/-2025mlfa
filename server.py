from flask import Flask, request, send_file, jsonify
from pyembroidery import EmbPattern, write_pes, STITCH, JUMP, COLOR_CHANGE, TRIM
from io import BytesIO
from flask_cors import CORS
import traceback

app = Flask(__name__)
CORS(app)

CMD_MAP = {
    "STITCH": STITCH,
    "JUMP": JUMP,
    "COLOR_CHANGE": COLOR_CHANGE,
    "TRIM": TRIM
}

@app.route('/generate_pattern', methods=['POST'])
def generate_pattern():
    try:
        data = request.get_json()
        # يمكن استقبال إما: commands: [ {cmd, x, y, color?}, ... ]
        # أو: paths: [ [ {x,y}, ... ], ... ] (سيحوّل لستيتشات مع JUMP)
        commands = data.get('commands')
        paths = data.get('paths', [])
        requested_type = data.get('type', 'pes')

        if not commands and not paths:
            return jsonify({"error": "لا توجد بيانات غرز (commands أو paths)"}), 400

        # بناء قائمة أوامر موحدة
        unified = []
        if commands:
            unified = commands
        else:
            # تحويل paths -> commands: لكل path نعمل JUMP إلى النقطة الأولى ثم STITCH لباقي النقاط
            for path in paths:
                if not path: 
                    continue
                first = path[0]
                unified.append({"cmd": "JUMP", "x": first["x"], "y": first["y"]})
                for pt in path[1:]:
                    unified.append({"cmd": "STITCH", "x": pt["x"], "y": pt["y"]})

        # إنشاء pattern
        pattern = EmbPattern()

        # ترقيم خيوط/ألوان إذا وُجدت
        current_color = None
        for item in unified:
            cmd = item.get("cmd", "STITCH")
            x = float(item.get("x", 0))
            y = float(item.get("y", 0))
            # تحويل اسم الأمر إلى قيمة ثابتة إن وُجد
            if cmd == "COLOR_CHANGE":
                # بعض الملفات تتطلب تغيير لون بدون إحداثيات
                # لكن pyembroidery يسمح بإضافة COLOR_CHANGE كتعليمة
                pattern.add_stitch_absolute(COLOR_CHANGE, x, y)
                current_color = item.get("color")
            elif cmd == "TRIM":
                # trim: سنستخدم الأمر TRIM إن وُجد في المكتبة
                pattern.add_stitch_absolute(TRIM, x, y)
            else:
                # STITCH أو JUMP
                mapped = CMD_MAP.get(cmd, STITCH)
                pattern.add_stitch_absolute(mapped, x, y)

        # إنهاء النمط
        pattern.end()

        # اكتب PES في الذاكرة
        buf = BytesIO()
        write_pes(pattern, buf)
        buf.seek(0)

        download_name = "stitch_pattern.pes"
        if requested_type == "des":
            # نعيد PES لكن بإسم .des لتسهيل التسمية - التحويل الحقيقي يحتاج برنامج خارجي.
            download_name = "stitch_pattern.des"

        return send_file(
            buf,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/octet-stream"
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
