"""Fetch the immutable evaluated routing inputs; standard library only."""
import argparse,hashlib,json,shutil,tempfile,urllib.request,zipfile
from pathlib import Path
TAG='research-final-20261015'
SHA='d7e0a5fcdd8b968b2542d221b1c4fe6cb6a958681ea69546cd0b92f950882202'
URL='https://github.com/Sparkxt-0318/wildfireguardian/releases/download/'+TAG+'/WFG-evaluated-routing-inputs-20261015.zip'
def digest(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--archive',type=Path,help='Use a previously downloaded archive instead of the network')
 ap.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1]/'data/routing')
 a=ap.parse_args();a.out=a.out.resolve()
 if a.out.exists():raise SystemExit('Output exists; choose a new --out rather than overwrite inputs: '+str(a.out))
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='wfg_inputs_',dir=a.out.parent) as td:
  td=Path(td);archive=a.archive
  if archive is None:
   archive=td/'inputs.zip';urllib.request.urlretrieve(URL,archive)
  if digest(archive)!=SHA:raise SystemExit('Archive SHA-256 mismatch; nothing extracted')
  staging=td/'unpacked';staging.mkdir()
  with zipfile.ZipFile(archive) as z:
   names=z.namelist()
   if len(names)!=len(set(names)) or z.testzip() is not None:raise SystemExit('Invalid archive')
   for info in z.infolist():
    p=Path(info.filename)
    if p.is_absolute() or '..' in p.parts or (info.external_attr >> 16)&0o170000==0o120000:raise SystemExit('Unsafe archive member')
   z.extractall(staging)
  rows=json.loads((staging/'INPUT_FILES.json').read_text())
  for row in rows:
   p=staging/row['path']
   if not p.is_file() or digest(p)!=row['sha256']:raise SystemExit('Input identity mismatch: '+row['path'])
  shutil.move(str(staging),str(a.out))
 print('Verified '+str(len(rows))+' frozen input files at '+str(a.out))
if __name__=='__main__':main()
