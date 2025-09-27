import os
from flask import Flask, request, render_template, send_from_directory, jsonify
from PIL import Image
import numpy as np
from rdp import rdp
import json
import struct

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- معالجة الصورة ---
def image_to_binary_points(file_path, resize_max=300, threshold=128, log=[]):
    log.append("جاري قراءة الصورة...")
    img = Image.open(file_path).convert("L")
    w,h = img.size
    scale = min(1, resize_max/max(w,h))
    if scale < 1:
        img = img.resize((int(w*scale), int(h*scale)))
        log.append(f"تم تصغير الصورة إلى {img.size[0]}x{img.size[1]}")
    arr = np.array(img)
    binary = (arr < threshold).astype(np.uint8)

    points=[]
    neighbors=[(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    h,w=binary.shape
    for y in range(h):
        for x in range(w):
            if binary[y,x]==1:
                is_edge=False
                for dx,dy in neighbors:
                    nx,ny=x+dx,y+dy
                    if nx<0 or nx>=w or ny<0 or ny>=h:
                        is_edge=True
                        break
                    if binary[ny,nx]==0:
                        is_edge=True
                        break
                if is_edge:
                    points.append({'x':x,'y':y})
    log.append(f"تم تحديد {len(points)} نقطة على شكل مخطط التطريز.")
    return points, img.size

def generate_paths(points, log=[]):
    if not points:
        log.append("لا توجد نقاط لإنشاء مسار.")
        return []
    rows={}
    for p in points:
        rows.setdefault(p['y'], []).append(p['x'])
    path=[]
    for y in sorted(rows.keys()):
        xs=rows[y]
        avg_x=sum(xs)/len(xs)
        path.append([avg_x,y])
    simplified=rdp(path, epsilon=1.0)
    simplified_points=[{'x':p[0],'y':p[1]} for p in simplified]
    log.append("تم تبسيط المسار باستخدام rdp.")
    return simplified_points

def export_csv(points,path):
    with open(path,'w') as f:
        for p in points:
            f.write(f"{int(p['x'])},{int(p['y'])}\n")

def export_dst(points,path):
    with open(path,'wb') as f:
        for p in points:
            f.write(struct.pack('<ii',int(p['x']),int(p['y'])))

def export_dse(points,path,meta={}):
    data={'points':[{'x':int(p['x']),'y':int(p['y'])} for p in points],'meta':meta}
    with open(path,'w') as f:
        json.dump(data,f,indent=2)

# --- Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    log=[]
    if 'image' not in request.files:
        return jsonify({'error':'لم يتم رفع ملف','log':log})
    file=request.files['image']
    if file.filename=='':
        return jsonify({'error':'لم يتم اختيار ملف','log':log})
    filename=f"{int(np.random.rand()*1e9)}-{file.filename}"
    filepath=os.path.join(app.config['UPLOAD_FOLDER'],filename)
    file.save(filepath)
    log.append(f"تم رفع الملف: {file.filename}")

    points,size=image_to_binary_points(filepath,log=log)
    path_points=generate_paths(points,log=log)

    base=os.path.splitext(filename)[0]
    csv_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.stitches.csv")
    dst_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.dst")
    dse_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.dse.json")

    export_csv(path_points,csv_path)
    export_dst(path_points,dst_path)
    export_dse(path_points,dse_path,meta={'source':file.filename,'size':size})
    log.append("تم تصدير جميع ملفات التطريز (CSV, DST, DSE).")

    return jsonify({
        'message':'تمت المعالجة بنجاح!',
        'files':{
            'stitches_csv':f"/uploads/{base}.stitches.csv",
            'dst':f"/uploads/{base}.dst",
            'dse':f"/uploads/{base}.dse.json"
        },
        'log':log,
        'previewPoints': path_points
    })

if __name__=='__main__':
    app.run(debug=True)
