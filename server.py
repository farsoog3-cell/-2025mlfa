import os
import uuid
from flask import Flask, request, send_file, jsonify, render_template_string
from flask_cors import CORS
from PIL import Image, ImageOps
import numpy as np
from io import BytesIO
from pyembroidery import EmbPattern, write_dst
from scipy import ndimage
import cv2

app = Flask(__name__)
CORS(app)

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
let stitchData = [];
let currentKey = '';
function previewImage(input) {
    if (input.files && input.files[0]) {
        let reader = new FileReader();
        reader.onload = function(e){
            let img = new Image();
            img.onload = function(){
                let canvas = document.getElementById('preview');
                let ctx = canvas.getContext('2d');
                ctx.clearRect(0,0,canvas.width,canvas.height);
                let scale = Math.min(canvas.width/img.width, canvas.height/img.height);
                let w = img.width*scale, h=img.height*scale;
                ctx.drawImage(img,0,0,w,h);
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
    .then(res => res.json())
    .then(data=>{
        currentKey = data.key;
        stitchData = data.stitches;
        drawStitches();
        downloadDST();
    }).catch(e=>alert('خطأ: '+e));
}

function drawStitches() {
    let canvas = document.getElementById('preview');
    let ctx = canvas.getContext('2d');
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = '#00FF00';
    for(let s of stitchData) {
        ctx.fillRect(s[0], s[1], 1, 1);
    }
}

function downloadDST() {
    fetch('/download_dst', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({key: currentKey})
    })
    .then(res=>res.blob())
    .then(blob=>{
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'pattern.dst';
        a.click();
        alert('تم تنزيل ملف DST جاهز للماكينة');
    });
}
</script>
</body>
</html>
"""

def crop_to_content(image):
    # تحويل الصورة لرمادي
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    # Threshold لتحديد المحتوى
    _, thresh = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return image
    x,y,w,h = cv2.boundingRect(coords)
    cropped = image.crop((x,y,x+w,y+h))
    return cropped

def remove_background(image):
    img = image.convert("RGBA")
    arr = np.array(img)
    r,g,b,a = arr[:,:,0], arr[:,:,1], arr[:,:,2], arr[:,:,3]
    mask = (r>240) & (g>240) & (b>240)
    arr[mask] = [255,255,255,0]
    return Image.fromarray(arr)

def binarize_image(image):
    img_gray = image.convert("L")
    arr = np.array(img_gray)
    arr_bin = (arr < 128).astype(np.uint8)*255
    return Image.fromarray(arr_bin)

def image_to_stitches_advanced(image):
    img = image.convert("L")
    max_dim = 200
    if img.width>max_dim or img.height>max_dim:
        img.thumbnail((max_dim,max_dim), Image.LANCZOS)
    arr = np.array(img)
    binary = arr < 128
    labeled, ncomponents = ndimage.label(binary)
    pattern = EmbPattern()
    step_satin = 2
    step_fill = 4
    stitch_list = []
    for i in range(1,ncomponents+1):
        coords = np.argwhere(labeled==i)
        if len(coords)<50:
            # Satin
            for y,x in coords[::step_satin]:
                pattern.add_stitch_absolute(x,y)
                stitch_list.append([x,y])
        else:
            # Fill
            for y,x in coords[::step_fill]:
                pattern.add_stitch_absolute(x,y)
                stitch_list.append([x,y])
    if len(pattern.stitches)==0:
        pattern.add_stitch_absolute(0,0)
        pattern.add_stitch_absolute(10,0)
        pattern.add_stitch_absolute(10,10)
        pattern.add_stitch_absolute(0,10)
        stitch_list = [[0,0],[10,0],[10,10],[0,10]]
    return pattern, stitch_list

# تخزين مؤقت للملفات
stitch_cache = {}

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error':'No file uploaded'}),400
    f = request.files['file']
    img = Image.open(f.stream).convert("RGB")
    img = crop_to_content(img)        # قص الحواف
    img = binarize_image(img)        # أبيض وأسود
    img = remove_background(img)     # إزالة الخلفية
    pattern, stitches = image_to_stitches_advanced(img)
    key = str(uuid.uuid4())
    stitch_cache[key] = pattern
    return jsonify({'key': key, 'stitches': stitches})

@app.route('/download_dst', methods=['POST'])
def download_dst():
    data = request.get_json()
    key = data.get('key')
    if key not in stitch_cache:
        return jsonify({'error':'Invalid key'}),400
    pattern = stitch_cache[key]
    bio = BytesIO()
    write_dst(pattern, bio)
    bio.seek(0)
    return send_file(bio, download_name='pattern.dst', mimetype='application/octet-stream')

if __name__=="__main__":
    app.run(host="0.0.0.0", port=5000)
