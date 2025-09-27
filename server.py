const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const Jimp = require('jimp');
const simplify = require('simplify-js');

const app = express();
const PORT = process.env.PORT || 3000;

const uploadDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadDir)) fs.mkdirSync(uploadDir);

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, uploadDir),
  filename: (req, file, cb) => {
    const safeName = Date.now() + '-' + file.originalname.replace(/\s+/g, '_');
    cb(null, safeName);
  }
});
const upload = multer({ storage });

app.use(express.static(path.join(__dirname, 'public')));
app.use('/uploads', express.static(uploadDir));

// --- معالجة الصور ---
async function imageToBinaryPoints(filePath, resizeMax = 300, threshold = 128, log=[]) {
  log.push("جاري قراءة الصورة...");
  const img = await Jimp.read(filePath);
  const scale = Math.min(1, resizeMax / Math.max(img.bitmap.width, img.bitmap.height));
  if (scale < 1) {
    img.resize(Math.round(img.bitmap.width * scale), Math.round(img.bitmap.height * scale));
    log.push(`تم تصغير الصورة إلى ${img.bitmap.width}x${img.bitmap.height}`);
  }
  img.grayscale();
  log.push("تم تحويل الصورة إلى رمادي.");

  const width = img.bitmap.width;
  const height = img.bitmap.height;
  const binary = new Uint8Array(width * height);

  img.scan(0, 0, width, height, function (x, y, idx) {
    const v = this.bitmap.data[idx];
    binary[y * width + x] = v < threshold ? 1 : 0;
  });
  log.push("تم استخراج النقاط الثنائية (Binary Points).");

  const points = [];
  const neighbors = [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]];
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = y * width + x;
      if (binary[idx] === 1) {
        let isEdge = false;
        for (const [dx,dy] of neighbors) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height) { isEdge = true; break; }
          if (binary[ny * width + nx] === 0) { isEdge = true; break; }
        }
        if (isEdge) points.push({ x, y });
      }
    }
  }
  log.push(`تم تحديد ${points.length} نقطة على شكل مخطط التطريز.`);
  return { points, width, height };
}

function generatePathsFromPoints(points, width, height, log=[]) {
  if (!points || points.length === 0) {
    log.push("لا توجد نقاط لإنشاء مسار.");
    return [];
  }

  const rows = new Map();
  for (const p of points) {
    if (!rows.has(p.y)) rows.set(p.y, []);
    rows.get(p.y).push(p.x);
  }
  const path = [];
  const sortedY = Array.from(rows.keys()).sort((a,b)=>a-b);
  for (const y of sortedY) {
    const xs = rows.get(y);
    const avgX = xs.reduce((a,b)=>a+b,0)/xs.length;
    path.push({ x: avgX, y });
  }

  const simplified = simplify(path, 1.0, true);
  log.push("تم تبسيط المسار (Simplify Path).");
  return [ simplified ];
}

function exportStitchesCSV(pathPoints, outPath) {
  const lines = pathPoints.map(p => `${Math.round(p.x)},${Math.round(p.y)}`);
  fs.writeFileSync(outPath, lines.join('\n'), 'utf8');
}

function exportFakeDST(pathPoints, outPath) {
  const bufArr = [];
  for (const p of pathPoints) {
    const x = Math.round(p.x);
    const y = Math.round(p.y);
    const b = Buffer.alloc(8);
    b.writeInt32LE(x, 0);
    b.writeInt32LE(y, 4);
    bufArr.push(b);
  }
  const finalBuf = Buffer.concat(bufArr);
  fs.writeFileSync(outPath, finalBuf);
}

function exportDSE(pathPoints, outPath, meta = {}) {
  const payload = {
    points: pathPoints.map(p => ({ x: Math.round(p.x), y: Math.round(p.y) })),
    meta
  };
  fs.writeFileSync(outPath, JSON.stringify(payload, null, 2), 'utf8');
}

app.post('/upload', upload.single('image'), async (req, res) => {
  const log = [];
  try {
    if (!req.file) return res.status(400).json({ error: 'لم يتم رفع ملف.' });
    log.push(`تم رفع الملف: ${req.file.originalname}`);

    const filePath = req.file.path;
    const { points, width, height } = await imageToBinaryPoints(filePath, 300, 128, log);
    const paths = generatePathsFromPoints(points, width, height, log);

    if (paths.length === 0) return res.json({ message: 'لا توجد نقاط كافية.', files: [], log });

    const combinedPath = [];
    for (const p of paths) combinedPath.push(...p);

    const base = path.parse(req.file.filename).name;
    const csvPath = path.join(uploadDir, `${base}.stitches.csv`);
    const dstPath = path.join(uploadDir, `${base}.dst`);
    const dsePath = path.join(uploadDir, `${base}.dse.json`);

    exportStitchesCSV(combinedPath, csvPath);
    exportFakeDST(combinedPath, dstPath);
    exportDSE(combinedPath, dsePath, { source: req.file.originalname, width, height });
    log.push("تم تصدير جميع ملفات التطريز (CSV, DST, DSE).");

    res.json({
      message: 'تمت المعالجة بنجاح!',
      files: {
        stitches_csv: `/uploads/${path.basename(csvPath)}`,
        dst: `/uploads/${path.basename(dstPath)}`,
        dse: `/uploads/${path.basename(dsePath)}`
      },
      log,
      previewPoints: combinedPath
    });

  } catch (err) {
    console.error(err);
    log.push('حدث خطأ أثناء المعالجة.');
    res.status(500).json({ error: 'حدث خطأ أثناء المعالجة.', log });
  }
});

app.listen(PORT, () => console.log(`MLFA Server running on port ${PORT}`));
