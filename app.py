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

# --- معالجة الصورة واستخراج الحواف ---
def detect_edges(file_path, threshold=128, log=[]):
    log.append("جاري تحويل الصورة إلى رمادية واستخراج الحواف...")
    img = Image.open(file_path).convert("L")
    w,h = img.size
    scale = min(1, 300/max(w,h))
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
                    if nx<0 or nx>=w or ny<0 or ny>=h or binary[ny,nx]==0:
                        is_edge=True
                        break
                if is_edge:
                    points.append({'x':x,'y':y})
    log.append(f"تم استخراج {len(points)} نقطة للحواف.")
    return points,img.size

def generate_embroidery_path(points, log=[], epsilon=1.0):
    if not points:
        log.append("لا توجد نقاط لإنشاء مسار الإبرة.")
        return []
    sorted_points = sorted(points,key=lambda p:(p['y'],p['x']))
    path=[[p['x'],p['y']] for p in sorted_points]
    simplified=rdp(path,epsilon=epsilon)
    simplified_points=[{'x':p[0],'y':p[1]} for p in simplified]
    log.append(f"تم تبسيط مسار الإبرة إلى {len(simplified_points)} نقطة.")
    return simplified_points

# --- تصدير الملفات ---
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

    points,size=detect_edges(filepath,log=log)
    path_points=generate_embroidery_path(points,log=log,epsilon=float(request.form.get("epsilon",1.0)))

    base=os.path.splitext(filename)[0]
    csv_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.stitches.csv")
    dst_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.dst")
    dse_path=os.path.join(app.config['UPLOAD_FOLDER'],f"{base}.dse.json")

    export_format=request.form.get("format","dse")
    if export_format=="csv":
        export_csv(path_points,csv_path)
    elif export_format=="dst":
        export_dst(path_points,dst_path)
    else:
        export_dse(path_points,dse_path,meta={'source':file.filename,'size':size})

    log.append(f"تم تصدير المخطط بصيغة {export_format.upper()}.")

    files_dict={
        'csv':f"/uploads/{base}.stitches.csv",
        'dst':f"/uploads/{base}.dst",
        'dse':f"/uploads/{base}.dse.json"
    }

    return jsonify({
        'message':'تمت المعالجة بنجاح!',
        'files':files_dict,
        'log':log,
        'previewPoints': path_points
    })

if __name__=='__main__':
    app.run(debug=True)
