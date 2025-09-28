# server.py
from flask import Flask, request, send_file
from pyembroidery import EmbPattern, write_pes
import io

app = Flask(__name__)

@app.route("/generate_pes", methods=["POST"])
def generate_pes():
    data = request.get_json()
    points = data.get("points", [])
    pattern = EmbPattern()
    
    for pt in points:
        x, y = pt['x'], pt['y']
        pattern.add_stitch_absolute(x, y)  # غرزة واحدة لكل نقطة
    
    file_stream = io.BytesIO()
    write_pes(pattern, file_stream)
    file_stream.seek(0)
    return send_file(file_stream, mimetype="application/octet-stream", download_name="output.pes")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
