/** Deterministic exhibition data. Scene units are illustrative, never metres. */
export function heightAt(x,z) {
  const peak=(cx,cz,sx,sz,a)=>a*Math.exp(-((x-cx)**2/(sx*sx)+(z-cz)**2/(sz*sz)));
  const ridge=2.1*Math.sin(x*.079+z*.039)+1.05*Math.sin(x*.21-z*.087);
  return Math.max(1.2,3.7+peak(-38,-20,20,34,15)+peak(5,-32,20,22,17)+peak(48,18,21,30,13)+peak(-10,26,19,15,7)+ridge);
}
function spline(anchors,steps=12) {
  const out=[];
  for(let i=0;i<anchors.length-1;i++) {
    const p0=anchors[Math.max(0,i-1)],p1=anchors[i],p2=anchors[i+1],p3=anchors[Math.min(anchors.length-1,i+2)];
    for(let s=0;s<steps;s++) {
      const t=s/steps,t2=t*t,t3=t2*t;
      out.push([0,1].map(k=>Number((.5*((2*p1[k])+(-p0[k]+p2[k])*t+(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t2+(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t3)).toFixed(4))));
    }
  }
  return [...out,[...anchors.at(-1)]];
}
const selected=spline([[-58,32],[-45,36],[-31,34],[-18,27],[-6,30],[10,31],[25,23],[38,15],[43,7],[39,-7],[45,-22],[49,-35]]);
const comparator=spline([[-58,32],[-46,22],[-32,12],[-24,7],[-12,2],[0,-2],[10,-3],[21,-8],[30,-16],[42,-27],[49,-35]]);
export const demoData={
  version:1,mode:'fixture',title:{ko:'돌아갈 길을 잇다',en:'A way through the fire'},duration:108,
  roads:[{id:'southern-pass',points:selected},{id:'valley-road',points:comparator},{id:'ridge-access',points:spline([[-60,-26],[-49,-20],[-40,-10],[-32,12]])},{id:'east-access',points:spline([[21,-8],[32,-4],[48,-2],[59,-10]])},{id:'western-spur',points:spline([[-31,34],[-32,22],[-43,7],[-54,0]])}],
  routes:{selected,comparator},fire:{center:[8,-3],radius:12},start:[-58,32],destination:[49,-35],deviceTrace:selected,
  provenance:{terrain:'illustrative',roads:'illustrative',fire:'illustrative',routes:'scripted',track:'scripted',device:'owner-cad-study',source:'Deterministic exhibition fixture, authored 2026-10-11. No measured geography, forecast, route guarantee, or physical device validation.'}
};
export function pointAlong(points,t) {
  if(!Array.isArray(points)||!points.length) return [0,0];
  if(points.length===1) return [...points[0]];
  const fraction=Number.isFinite(t)?Math.max(0,Math.min(1,t)):0;
  if(fraction===0)return [...points[0]];if(fraction===1)return [...points.at(-1)];
  const lengths=[];let total=0;
  for(let i=1;i<points.length;i++){const n=Math.hypot(points[i][0]-points[i-1][0],points[i][1]-points[i-1][1]);lengths.push(n);total+=n;}
  if(total===0)return [...points[0]];
  let distance=total*fraction;
  for(let i=0;i<lengths.length;i++){if(distance<=lengths[i]&&lengths[i]>0){const f=distance/lengths[i];return [points[i][0]+(points[i+1][0]-points[i][0])*f,points[i][1]+(points[i+1][1]-points[i][1])*f];}distance-=lengths[i];}
  return [...points.at(-1)];
}
const own=(obj,key)=>Object.prototype.hasOwnProperty.call(obj,key);
const object=v=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&(Object.getPrototypeOf(v)===Object.prototype||Object.getPrototypeOf(v)===null);
const keyPoint=p=>`${p[0]},${p[1]}`;
const edgeKey=(a,b)=>[keyPoint(a),keyPoint(b)].sort().join('|');
function keys(value,allowed,label,errors){if(!object(value)){errors.push(`${label} must be an object.`);return false;}for(const k of Object.keys(value))if(!allowed.includes(k))errors.push(`${label}.${k} is not supported.`);return true;}
function text(value,max=500){return typeof value==='string'&&value.trim().length>0&&value.length<=max&&!/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(value);}
function timestamp(value){
  if(!text(value,40))return false;
  const m=/^(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.exec(value);
  if(!m||!Number.isFinite(Date.parse(value)))return false;
  const year=Number(m[1]),month=Number(m[2]),day=Number(m[3]);
  const days=[31,year%4===0&&(year%100!==0||year%400===0)?29:28,31,30,31,30,31,31,30,31,30,31];
  return month>=1&&month<=12&&day>=1&&day<=days[month-1];
}
function point(p){return Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)&&Math.abs(p[0])<=64&&Math.abs(p[1])<=46;}
function path(p){return Array.isArray(p)&&p.length>=2&&p.length<=4000&&p.every(point);}
function same(a,b){return point(a)&&point(b)&&a[0]===b[0]&&a[1]===b[1];}
/** Strict exhibition scene contract; format validation is not scientific verification. */
export function validateArtifact(value) {
  const errors=[];
  if(!keys(value,['version','mode','title','duration','roads','routes','fire','start','destination','deviceTrace','provenance'],'artifact',errors))return {ok:false,errors};
  if(value.version!==1)errors.push('version must be 1.');
  if(!['fixture','artifact','recorded'].includes(value.mode))errors.push('mode must be fixture, artifact, or recorded.');
  if(!keys(value.title,['ko','en'],'title',errors)||!text(value.title?.ko,120)||!text(value.title?.en,120))errors.push('title requires ko and en strings (1–120 characters).');
  if(value.duration!==108)errors.push('duration must be the 108-second presentation timeline.');
  let total=0;const edges=new Set();const roadIds=new Set();
  if(!Array.isArray(value.roads)||value.roads.length<1||value.roads.length>128)errors.push('roads must contain 1–128 roads.');
  else for(const road of value.roads){
    if(!keys(road,['id','points'],'road',errors))continue;
    if(!text(road.id,80)||roadIds.has(road.id))errors.push('Road identifiers must be unique strings (1–80 characters).');roadIds.add(road.id);
    if(!path(road.points)){errors.push('Each road needs 2–4000 finite [x,z] points within x ±64, z ±46.');continue;}
    total+=road.points.length;
    for(let i=1;i<road.points.length;i++)edges.add(edgeKey(road.points[i-1],road.points[i]));
  }
  if(total>30000)errors.push('Roads exceed the combined 30,000-point limit.');
  if(keys(value.routes,['selected','comparator'],'routes',errors))for(const name of ['selected','comparator']){
    const route=value.routes[name];if(!path(route)){errors.push(`routes.${name} needs 2–4000 bounded points.`);continue;}
    if(!same(route[0],value.start)||!same(route.at(-1),value.destination))errors.push(`routes.${name} must connect start to destination.`);
    for(let i=1;i<route.length;i++)if(!edges.has(edgeKey(route[i-1],route[i]))){errors.push(`routes.${name} must reuse exact adjacent road points.`);break;}
  }
  if(!point(value.start)||!point(value.destination))errors.push('start and destination must be bounded [x,z] points.');
  if(!keys(value.fire,['center','radius'],'fire',errors)||!point(value.fire?.center)||!Number.isFinite(value.fire?.radius)||value.fire.radius<0||value.fire.radius>30)errors.push('fire requires a bounded center and radius from 0 to 30.');
  if(!path(value.deviceTrace))errors.push('deviceTrace needs 2–4000 bounded points.');
  if(keys(value.provenance,['terrain','roads','fire','routes','track','device','source'],'provenance',errors)){
    const p=value.provenance;
    for(const k of ['terrain','fire'])if(p[k]!=='illustrative')errors.push(`provenance.${k} must be illustrative: this viewer does not ingest elevation or forecast rasters.`);
    if(!['illustrative','imported-artifact'].includes(p.roads))errors.push('provenance.roads requires illustrative or imported-artifact.');
    if(!['scripted','imported-artifact'].includes(p.routes))errors.push('provenance.routes requires scripted or imported-artifact.');
    if(!['scripted','recorded-user-supplied'].includes(p.track))errors.push('provenance.track requires scripted or recorded-user-supplied.');
    if(p.device!=='owner-cad-study')errors.push('provenance.device must identify the displayed owner-cad-study.');
    if(!text(p.source,2000))errors.push('provenance.source requires a source description (1–2000 characters).');
    if(value.mode==='fixture'&&([p.terrain,p.roads,p.fire].some(v=>v!=='illustrative')||p.track!=='scripted'||p.routes!=='scripted'))errors.push('fixture requires illustrative terrain/roads/fire and scripted routes/track.');
    if(value.mode==='recorded'&&(p.track!=='recorded-user-supplied'||p.terrain!=='illustrative'||p.roads!=='illustrative'||p.fire!=='illustrative'||p.routes!=='scripted'))errors.push('recorded mode is a user-supplied track on an illustrative scene.');
  }
  return {ok:errors.length===0,errors:errors.slice(0,30)};
}
/** WGS84 local import: user assertion of recording is retained, never authenticated. */
export function adaptRecordedTrack(value) {
  const errors=[];
  if(!keys(value,['version','kind','title','coordinates','source','recordedAt'],'track',errors))throw new Error(errors.join(' '));
  if(value.version!==1||value.kind!=='recorded-track')errors.push('Expected version 1, kind recorded-track.');
  if(!text(value.title,120)||!text(value.source,1000))errors.push('Track title and source are required.');
  if(!timestamp(value.recordedAt))errors.push('recordedAt requires an ISO 8601 timestamp with timezone.');
  const p=value.coordinates;
  if(!Array.isArray(p)||p.length<2||p.length>4000||!p.every(c=>Array.isArray(c)&&c.length===2&&c.every(Number.isFinite)&&Math.abs(c[0])<=180&&Math.abs(c[1])<85))errors.push('coordinates needs 2–4000 WGS84 [longitude,latitude] pairs, latitude inside ±85°.');
  if(errors.length)throw new Error(errors.join(' '));
  const lonMin=Math.min(...p.map(c=>c[0])),lonMax=Math.max(...p.map(c=>c[0])),latMin=Math.min(...p.map(c=>c[1])),latMax=Math.max(...p.map(c=>c[1]));
  if(lonMax-lonMin>2||latMax-latMin>2)throw new Error('Track spans more than two degrees; this local visualization adapter does not support that extent or dateline crossing.');
  const lat=(latMin+latMax)/2,lon=(lonMin+lonMax)/2,c=Math.cos(lat*Math.PI/180);
  const dx=(lonMax-lonMin)*c,dz=latMax-latMin,scale=Math.min(112/Math.max(dx,1e-12),78/Math.max(dz,1e-12));
  if(Math.max(dx,dz)<1e-7)throw new Error('Track has no resolvable spatial extent.');
  const points=p.map(v=>[Number(((v[0]-lon)*c*scale).toFixed(5)),Number((-(v[1]-lat)*scale).toFixed(5))]);
  return {version:1,mode:'recorded',title:{ko:value.title,en:value.title},duration:108,roads:[{id:'uploaded-track',points}],routes:{selected:points,comparator:points},fire:{center:[8,-3],radius:0},start:points[0],destination:points.at(-1),deviceTrace:points,provenance:{terrain:'illustrative',roads:'illustrative',fire:'illustrative',routes:'scripted',track:'recorded-user-supplied',device:'owner-cad-study',source:`User-supplied track: ${value.source}. Recorded-at claim: ${value.recordedAt}. Longitude/latitude normalized by local equirectangular projection into arbitrary scene units; elevation and playback timing are illustrative; recording authenticity is not checked. Fire is hidden. This is a track replay, not a computed escape route.`}};
}
export async function loadArtifact(file) {
  if(!file||typeof file.text!=='function'||!Number.isFinite(file.size)||file.size<2||file.size>5*1024*1024)throw new Error('Choose a local JSON file from 2 bytes to 5 MiB.');
  let value;try{value=JSON.parse(await file.text());}catch{throw new Error('The selected file is not valid JSON.');}
  if(object(value)&&own(value,'kind')&&value.kind==='recorded-track')value=adaptRecordedTrack(value);
  const result=validateArtifact(value);if(!result.ok)throw new Error(result.errors.join(' '));
  return value;
}
