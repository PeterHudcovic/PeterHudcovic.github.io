from pathlib import Path
import json,re,hashlib
from PIL import Image,ImageOps,ImageDraw
from pypdf import PdfReader
import pdfplumber
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'azure-case-study/manifest.json').read_text())
reader=PdfReader(root/'output/pdf/azure-platform-case-study.pdf')
assert len(reader.pages)==manifest['pdfPages']
for c in manifest['chapters']:
 assert (Path('C:/Projects/AZURE_3way_env/azure-appservice-platform-lab')/c['source']).is_file(),c['source']
for e in manifest['screenshots']:
 a=(root/'azure-case-study-evidence'/e['file']).read_bytes()
 b=(root/'azure-case-study/images'/e['file']).read_bytes()
 assert hashlib.sha256(a).digest()==hashlib.sha256(b).digest()
assert not (root/'azure-case-study/images/prod-application-insights-overview.png').exists()
issues=[]
with pdfplumber.open(root/'output/pdf/azure-platform-case-study.pdf') as pdf:
 for i,p in enumerate(pdf.pages):
  for char in p.chars:
   if char['x0'] < 0 or char['x1']>p.width+1 or char['top']<0 or char['bottom']>p.height+1:
    issues.append((i+1,'outside page'))
  if i>=manifest['mainPages']:
   header=[x for x in p.chars if x['size']>=27]
   subtitle=[x for x in p.chars if 10.9<x['size']<11.1]
   if header and subtitle and max(x['bottom'] for x in header)>min(x['top'] for x in subtitle):
    issues.append((i+1,'header reaches subtitle'))
out=root/'tmp/azure-case-study'
paths=sorted(out.glob('page-*.png'),key=lambda p:int(p.stem.split('-')[-1]))
for batch in range(0,len(paths),12):
 sheet=Image.new('RGB',(1600,1200),'#334155');draw=ImageDraw.Draw(sheet)
 for j,path in enumerate(paths[batch:batch+12]):
  im=Image.open(path).convert('RGB');im.thumbnail((390,360))
  x=(j%4)*400;y=(j//4)*400
  sheet.paste(im,(x+(400-im.width)//2,y+22))
  draw.text((x+8,y+5),path.stem,fill='white')
 sheet.save(out/f'contact-{batch//12+1:02}.jpg')
print(json.dumps({'pages':len(reader.pages),'screenshots':len(manifest['screenshots']),'layoutIssues':sorted(set(issues)),'rendered':len(paths)}))
