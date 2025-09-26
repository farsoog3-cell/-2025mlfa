import os
import uuid
from flask import Flask, request, send_file, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image, ImageOps
import numpy as np
from io import BytesIO
from pyembroidery import EmbPattern, write_dst
from scipy import ndimage

app = Flask(__name__)
CORS(app)

# HTML واجهة مع معاينة
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>ML FA2025 Embroidery</title>
<style>
body { background: #111; color: #eee; font-family: monospace; text-align:center; padding:20px;}
input[type=file] { margin:20px; }
button { padding:10px 20px; margin:10px; background:#2196F3; color:#fff; border:none; cursor:pointer;}
canvas { border:1px solid #555; margin-top:20px;}
</style>
</head>
<body>
<h1>ML FA2025 Embroidery Converter</h1>
<p>ارفع الصورة لتحويلها إلى قالب تطريز DST</p>
<input type="file" id="fileInput" onchange="previewImage(this)">
<button onclick="upload()">رفع وتحويل</button>
<canvas id="preview" width="300" height="300"></canvas>
<script>
let imgData = null;
function previewImage(input) {
    if (input.files && input.files[0]) {
        let reader = new FileReader();
        reader.onload = function(e){
            let img = new Image();
            img.onload = function(){
                let canvas = document.getElementById('preview');
                let ctx = canvas.getContext('2d');
                ctx.clearRect(0,0,canvas.width,canvas.height);
                // fit image
                let scale = Math.min(canvas.width/img.width, canvas.height/img.height);
                let w = img.width*scale, h=img.height*scale;
                ctx.drawImage(img,0,0,w,h);
                imgData = ctx.getImageData(0,0,w,h);
            }
            img.src = e.target.result;
        }
        reader.readAsDataURL(input.files[0]);
    }
}

function upload() {
    var file = document.getElementById('fileInput').files[0];
    if(!file) return alert('اختر صورة');
    var form = new FormData();
    form.append('file', file);
    fetch('/upload', { method:'POST', body:form })
    .then(res => res.blob())
    .then(blob => {
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'pattern.dst';
        a.click();
        alert('تم تنزيل ملف DST جاهز للماكينة');
    }).catch(e=>alert('خطأ: '+e));
}
</script>
</body>
</html>
"""

def remove_background(image):
    img = image.convert("RGBA")
    arr = np.array(img)
    r,g,b,a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    mask = (r>240) & (g>240) & (b>240)
    arr[mask] = [255,255,255,0]
    return Image.fromarray(arr)

def image_to_stitches_advanced(image):
    img = image.convert("L")
    max_dim = 200
    if img.width>max_dim or img.height>max_dim:
        img.thumbnail((max_dim,max_dim), Image.LANCZOS)
    arr = np.array(img)
    threshold = 200
    binary = arr < threshold
    labeled, ncomponents = ndimage.label(binary)
    pattern = EmbPattern()
    step_satin = 2
    step_fill = 4
    for i in range(1,ncomponents+1):
        coords = np.argwhere(labeled==i)
        if len(coords)<50:
            # منطقة صغيرة -> Satin
            for y,x in coords[::step_satin]:
                pattern.add_stitch_absolute(x,y)
        else:
            # منطقة كبيرة -> Fill
            for y,x in coords[::step_fill]:
                pattern.add_stitch_absolute(x,y)
    if len(pattern.stitches)==0:
        # غرزة تجريبية
        pattern.add_stitch_absolute(0,0)
        pattern.add_stitch_absolute(10,0)
        pattern.add_stitch_absolute(10,10)
        pattern.add_stitch_absolute(0,10)
    return pattern

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}),400
    f = request.files['file']
    img = Image.open(f.stream).convert("RGB")
    img = remove_background(img)
    pattern = image_to_stitches_advanced(img)
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return send_file(bio, download_name='pattern.dst', mimetype='application/octet-stream')

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
