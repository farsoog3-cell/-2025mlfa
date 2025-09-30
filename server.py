from flask import Flask, request, send_file, render_template
from flask_cors import CORS
from PIL import Image
import numpy as np
import io
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import os

app = Flask(__name__)
CORS(app)

# قائمة ألوان DMC تجريبية
DMC_COLORS = {
    (255, 0, 0): "DMC 666 – أحمر",
    (0, 0, 255): "DMC 3843 – أزرق",
    (0, 255, 0): "DMC 702 – أخضر",
    (0, 0, 0): "DMC 310 – أسود",
    (255, 255, 255): "DMC Blanc – أبيض",
}

def closest_color(rgb):
    return min(DMC_COLORS.keys(), key=lambda c: sum((sc - rc) ** 2 for sc, rc in zip(c, rgb)))

def generate_pattern(image_stream, grid_size):
    img = Image.open(image_stream).convert("RGB")
    img = img.resize((grid_size, grid_size), Image.NEAREST)
    pixels = np.array(img)

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(pixels)
    ax.set_xticks(range(grid_size))
    ax.set_yticks(range(grid_size))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.grid(True, color="black")

    buf_img = io.BytesIO()
    plt.savefig(buf_img, format="png", bbox_inches="tight")
    buf_img.seek(0)

    unique = set()
    for row in pixels:
        for pix in row:
            col = closest_color(tuple(pix))
            unique.add(col)

    plt.close(fig)  # 🔴 مهم عشان ما يستهلك RAM على Render
    return buf_img, unique

def generate_pdf(pattern_img_buf, colors_used, grid_size, stitch_type, fabric_type):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    img = Image.open(pattern_img_buf)
    img_w = 12 * cm
    img_h = 12 * cm
    img_buf = io.BytesIO()
    img = img.resize((int(img_w), int(img_h)))
    img.save(img_buf, format="PNG")
    img_buf.seek(0)
    c.drawInlineImage(img_buf, 3 * cm, height - (img_h + 4 * cm), img_w, img_h)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(3 * cm, height - 2 * cm, "قالب التطريز")

    c.setFont("Helvetica", 12)
    y = height - (img_h + 4 * cm) - 1 * cm
    c.drawString(3 * cm, y, f"حجم الشبكة: {grid_size} × {grid_size}")
    y -= 0.8 * cm
    c.drawString(3 * cm, y, f"نوع الغرز: {stitch_type}")
    y -= 0.8 * cm
    c.drawString(3 * cm, y, f"نوع القماش: {fabric_type}")
    y -= 1 * cm

    c.setFont("Helvetica-Bold", 14)
    c.drawString(3 * cm, y, "الألوان المطلوبة:")
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    for col in colors_used:
        name = DMC_COLORS.get(col, f"RGB{col}")
        c.drawString(4 * cm, y, f"- {name}")
        y -= 0.7 * cm

    y -= 1 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(3 * cm, y, "الأدوات الموصى بها:")
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    c.drawString(4 * cm, y, "- قماش " + fabric_type)
    y -= 0.8 * cm
    c.drawString(4 * cm, y, "- إبرة تطريز مناسبة")
    y -= 0.8 * cm
    c.drawString(4 * cm, y, "- إطار تطريز")
    y -= 0.8 * cm
    c.drawString(4 * cm, y, "- مقص صغير")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

@app.route("/", methods=["GET"])
def index_page():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_route():
    if "image" not in request.files:
        return "لم يتم رفع أي صورة", 400

    image_file = request.files["image"]
    grid_size = int(request.form.get("grid_size", 40))
    stitch_type = request.form.get("stitch_type", "cross")
    fabric_type = request.form.get("fabric_type", "Aida")

    pattern_buf, used_colors = generate_pattern(image_file, grid_size)
    pdf_buf = generate_pdf(pattern_buf, used_colors, grid_size, stitch_type, fabric_type)

    return send_file(pdf_buf, mimetype="application/pdf")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
