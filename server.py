from flask import Flask, request, send_file, render_template
from flask_cors import CORS
from PIL import Image
import numpy as np
import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import os

app = Flask(__name__)
CORS(app)

# ألوان DMC تجريبية
DMC_COLORS = {
    (255, 0, 0): "DMC 666 – أحمر",
    (0, 0, 255): "DMC 3843 – أزرق",
    (0, 255, 0): "DMC 702 – أخضر",
    (0, 0, 0): "DMC 310 – أسود",
    (255, 255, 255): "DMC Blanc – أبيض",
}

def closest_color(rgb):
    return min(DMC_COLORS.keys(), key=lambda c: sum((sc - rc)**2 for sc, rc in zip(c, rgb)))

def remove_background(img):
    """إزالة الخلفية البيضاء تلقائيًا"""
    img = img.convert("RGBA")
    data = np.array(img)
    r, g, b, a = data.T
    white_areas = (r > 240) & (g > 240) & (b > 240)
    data[..., :-1][white_areas.T] = (255, 255, 255)
    data[..., -1][white_areas.T] = 0
    img2 = Image.fromarray(data)
    return img2

def generate_stitch_map(img, grid_size):
    """إنشاء خريطة الإبرة تلقائيًا"""
    img_small = img.convert("RGB").resize((grid_size, grid_size), Image.NEAREST)
    return img_small

def generate_pdf(pattern_img_buf, colors_used, grid_size, stitch_type, fabric_type):
    """إنشاء PDF مع كل المعلومات والأدوات"""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # رسم الصورة
    img_w = 12 * cm
    img_h = 12 * cm
    c.drawInlineImage(pattern_img_buf, 3 * cm, height - (img_h + 4 * cm), img_w, img_h)

    # معلومات القالب
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

    # الألوان المستخدمة
    c.setFont("Helvetica-Bold", 14)
    c.drawString(3 * cm, y, "الألوان المطلوبة:")
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    for col in colors_used:
        name = DMC_COLORS.get(col, f"RGB{col}")
        c.drawString(4 * cm, y, f"- {name}")
        y -= 0.7 * cm

    # الأدوات الموصى بها
    y -= 1 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(3 * cm, y, "📌 قائمة الأدوات الموصى بها:")
    y -= 1 * cm
    c.setFont("Helvetica", 12)

    tools = [
        "إطار تطريز (Embroidery Hoop)",
        "إبرة تطريز مناسبة",
        "خيط التطريز",
        "مقص صغير ودقيق",
        "إبرة لإزالة الغرز (Seam Ripper)",
        "دبوس أو مشبك لتثبيت القماش",
        "قطعة قماش حسب الاختيار (Aida / Linen / Felt)",
        "شريط لاصق لتثبيت حواف القماش",
        "مسطرة أو أداة قياس مربعات",
        "علامة أقمشة قابلة للمسح",
        "دليل الغرز (Stitch Guide)",
        "بطاقة ألوان (Color Card)",
        "لوحة لتثبيت الخيوط",
        "مصباح صغير للضوء المباشر",
        "مكبر بصري إذا كان العمل دقيقًا",
        "منضدة عمل أو لوحة مستقرة"
    ]
    for tool in tools:
        c.drawString(4 * cm, y, f"- {tool}")
        y -= 0.7 * cm

    c.showPage()
    c.save()
    buf.seek(0)
    return buf

@app.route("/", methods=["GET"])
def index_page():
    return render_template("index.html")

@app.route("/upload_preview", methods=["POST"])
def upload_preview():
    if "image" not in request.files:
        return "No image", 400
    image_file = request.files["image"]
    grid_size = int(request.form.get("grid_size", 40))
    remove_bg = request.form.get("remove_bg") == "true"

    img = Image.open(image_file)
    if remove_bg:
        img = remove_background(img)
    pattern_img = generate_stitch_map(img, grid_size)
    buf_img = io.BytesIO()
    pattern_img.save(buf_img, format="PNG")
    buf_img.seek(0)
    return send_file(buf_img, mimetype="image/png")

@app.route("/upload", methods=["POST"])
def upload_route():
    if "image" not in request.files:
        return "لم يتم رفع أي صورة", 400

    image_file = request.files["image"]
    grid_size = int(request.form.get("grid_size", 40))
    stitch_type = request.form.get("stitch_type", "cross")
    fabric_type = request.form.get("fabric_type", "Aida")
    remove_bg = request.form.get("remove_bg") == "true"

    img = Image.open(image_file)
    if remove_bg:
        img = remove_background(img)
    pattern_img = generate_stitch_map(img, grid_size)

    buf_img = io.BytesIO()
    pattern_img.save(buf_img, format="PNG")
    buf_img.seek(0)

    # استخراج الألوان المستخدمة
    pixels = np.array(pattern_img)
    used_colors = set()
    for row in pixels:
        for pix in row:
            col = closest_color(tuple(pix))
            used_colors.add(col)

    pdf_buf = generate_pdf(buf_img, used_colors, grid_size, stitch_type, fabric_type)
    return send_file(pdf_buf, mimetype="application/pdf")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
