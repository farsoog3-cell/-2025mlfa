# server.py
from flask import Flask, request, send_file
from pyembroidery import EmbPattern, STITCH, SATIN, write_pes
import io

app = Flask(__name__)

@app.route("/generate_pes", methods=["POST"])
def generate_pes():
    data = request.get_json()
    points = data.get("points", [])
    pattern = EmbPattern()
    
    last_type = None
    for pt in points:
        x, y, g_type = pt['x'], pt['y'], pt.get('type', 'fill')

        if g_type == 'fill':
            if last_type != 'fill':
                pattern.add_satin(x, y)  # بداية منطقة Fill
            else:
                pattern.add_stitch_absolute(x, y)
        elif g_type == 'edge':
            pattern.add_satin(x, y)
        else:
            pattern.add_stitch_absolute(x, y)

        last_type = g_type

    file_stream = io.BytesIO()
    write_pes(pattern, file_stream)
    file_stream.seek(0)
    return send_file(file_stream, mimetype="application/octet-stream", download_name="output.pes")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
