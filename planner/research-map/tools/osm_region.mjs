// usage: node osm_region.mjs <pmtiles> <W> <S> <E> <N> <zoom> <out.json>
// Reads the planner's offline basemap with the planner's own node_modules (run `npm ci` in planner/ first).
import { createRequire } from 'module';
import { fileURLToPath, pathToFileURL } from 'url';
const PLANNER = fileURLToPath(new URL('../../', import.meta.url));
const require = createRequire(PLANNER + 'package.json');
const { PMTiles } = await import(pathToFileURL(PLANNER + 'node_modules/pmtiles/dist/esm/index.js').href);
const { VectorTile } = require('@mapbox/vector-tile'); const Pbf = require('pbf').default || require('pbf');
import fs from 'fs'; import zlib from 'zlib';
class FileSource { constructor(p){this.fd=fs.openSync(p,'r');this.p=p;} getKey(){return this.p;}
  async getBytes(o,l){const b=Buffer.alloc(l);fs.readSync(this.fd,b,0,l,o);return {data:b.buffer.slice(b.byteOffset,b.byteOffset+l)};}}
const [pmPath, w, s, e, n, z, outPath] = process.argv.slice(2);
const pm = new PMTiles(new FileSource(pmPath));
const [W,S,E,N]=[+w,+s,+e,+n], Z=+z;
const lon2x=(lon,z)=>Math.floor((lon+180)/360*2**z), lat2y=(lat,z)=>{const r=lat*Math.PI/180;return Math.floor((1-Math.log(Math.tan(r)+1/Math.cos(r))/Math.PI)/2*2**z);};
const out={}; const r5=v=>Math.round(v*1e5)/1e5;
for(let x=lon2x(W,Z);x<=lon2x(E,Z);x++) for(let y=lat2y(N,Z);y<=lat2y(S,Z);y++){
  const t=await pm.getZxy(Z,x,y); if(!t) continue;
  let buf=Buffer.from(t.data); try{buf=zlib.gunzipSync(buf);}catch{}
  const vt=new VectorTile(new Pbf(buf));
  for(const ln of Object.keys(vt.layers)){ const L=vt.layers[ln];
    if(!['roads','water','landuse','landcover','earth','pois','places'].includes(ln)) continue;
    for(let i=0;i<L.length;i++){ const f=L.feature(i); const p=f.properties;
      if(ln==='pois' && p.kind!=='peak') continue;
      const g=f.toGeoJSON(x,y,Z).geometry; const rnd=c=>typeof c[0]==='number'?[r5(c[0]),r5(c[1])]:c.map(rnd);
      (out[ln]??=[]).push({k:p.kind||'',d:p.kind_detail||'',n:p['name:ko']||p.name||undefined,ne:p['name:en']||undefined,e:p.elevation,r:p.min_zoom,t:g.type,c:rnd(g.coordinates)});
    }}
}
fs.writeFileSync(outPath,JSON.stringify(out));
const kinds={}; for(const f of out.water||[]) kinds[f.k+'/'+f.t]=(kinds[f.k+'/'+f.t]||0)+1;
console.error(outPath, Object.fromEntries(Object.entries(out).map(([k,v])=>[k,v.length])), 'water kinds', JSON.stringify(kinds));
