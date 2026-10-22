import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
// Run with Node.js from any directory: node planner/research-map/tests/demo-reliability.mjs
// Pure isolated source tests: no browser, network, account or scientific engine.
const html=fs.readFileSync(new URL('../site/index.html',import.meta.url),'utf8');
const results=[];
const section=(a,b)=>{const start=html.indexOf(a);assert(start>=0,a);const end=html.indexOf(b,start+a.length);assert(end>=0,b);return html.slice(start,end);};
const test=async(name,fn)=>{try{await fn();results.push({name,status:'PASS'});}catch(e){results.push({name,status:'FAIL',error:e.stack});}};
await test('All executable inline scripts parse',()=>{
 let n=0;for(const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)){if(/\bsrc\s*=/.test(m[1])||/type=["'](?:application\/json|text\/plain)/.test(m[1]))continue;new vm.Script(m[2]);n++;}assert(n>0);
});
function navigation(){
 let now=0,next=0;const queue=new Map(),allCallbacks=[],elements=new Map();
 const label={remove(){elements.delete('navReplayLb');},innerHTML:''};
 const NAV={on:true,ci:0,pol:'full',view:'2d',rpToken:0}; const state={t:0,playing:false};
 const sandbox={NAV,state,REC:[0],CASES:[{k:0,r:{t0:10},pol:{full:{dep:0,dense:[]}}}],
 $:id=>id==='speed'?{value:'1'}:id==='navReplayLb'?elements.get(id):{innerHTML:'',setAttribute(){}},
 mapEl:{appendChild(x){elements.set(x.id,x);}},document:{createElement:()=>label},performance:{now:()=>now},Math,Number,
 requestAnimationFrame:fn=>{const id=++next;queue.set(id,fn);allCallbacks.push(fn);return id;},cancelAnimationFrame:id=>queue.delete(id),
 clamp:(x,a,b)=>Math.max(a,Math.min(x,b)),rangeLo:()=>0,rangeHi:()=>100,
 setDetail(){sandbox.navCancelReplay();},navView(){sandbox.navCancelReplay();},navSteps:()=>[],navSvSamples:()=>[],navResolve(){},buildRouteMeshes(){},navPanel(){},navFit(){},navMarks(){},navMapRoute(){},navAuto(){},navSvGo(){},tr:(ko,en)=>en,navDate:()=>'',navClock:()=>''};
 vm.createContext(sandbox);
 vm.runInContext(section('function setTime(t,','$(\'play\').onclick')+section('function navRoute(pol)','// the recorded spread, fast:')+section('function navCancelReplay()','// a label on the map'),sandbox);
 return{...sandbox,queue,allCallbacks,frame(at){now=at;const ent=queue.entries().next().value;assert(ent,'queued replay frame');queue.delete(ent[0]);ent[1](at);},setNow(at){now=at;}};
}
await test('Replay starts and advances despite setup cancellation',()=>{const n=navigation();n.navReplay();n.frame(3000);assert.equal(n.state.t,2);assert.equal(n.queue.size,1);});
await test('Restart cancels replay and already captured callback cannot overwrite time',()=>{const n=navigation();n.navReplay();n.frame(3000);const stale=n.allCallbacks.at(-1);n.navRoute('full');const t=n.state.t;assert.equal(n.queue.size,0);stale(4000);assert.equal(n.state.t,t);assert.equal(t,10);});
await test('Manual timeline change cancels replay and stale callback',()=>{const n=navigation();n.navReplay();n.frame(3000);const stale=n.allCallbacks.at(-1);n.setTime(7);stale(4000);assert.equal(n.state.t,7);assert.equal(n.queue.size,0);});
await test('Playback stop cancels replay',()=>{const n=navigation();n.navReplay();n.frame(3000);const stale=n.allCallbacks.at(-1);n.setPlaying(false);const t=n.state.t;stale(5000);assert.equal(n.state.t,t);assert.equal(n.queue.size,0);});
await test('Replay naturally completes and restarts chosen recorded journey',()=>{const n=navigation();n.navReplay();n.frame(15000);assert.equal(n.state.t,10);assert.equal(n.state.playing,true);assert.equal(n.queue.size,0);});
await test('Roadview Space stops auto and cannot be reversed by next frame',()=>{
 const listeners=[],state={playing:false},NAV={on:true,street:true,auto:true,sv:null};
 const s={state,NAV,Math,addEventListener:(k,fn)=>listeners.push(fn),$:()=>({click:()=>{state.playing=!state.playing;}}),navCancelReplay(){},navAuto:v=>{NAV.auto=v;},setPlaying:v=>{state.playing=v;},navSvFire(){},navMini(){}};
 vm.createContext(s);vm.runInContext(section("addEventListener('keydown', e => {\n  if (e.target.closest('input,select,textarea,button",'let prevRec')+section('function navSvFrame(t, p, s, q)','// inset map, heading up'),s);
 const event={code:'Space',repeat:false,target:{closest:()=>null},preventDefault(){}};listeners[0](event);assert.equal(NAV.auto,false);assert.equal(state.playing,false);s.navSvFrame(0,{},0,{});assert.equal(NAV.auto,false);listeners[0](event);assert.equal(NAV.auto,true);
 NAV.auto=false;listeners[0]({...event,repeat:true});assert.equal(NAV.auto,false);listeners[0]({...event,target:{closest:()=>({})}});assert.equal(NAV.auto,false);
});
function clock(){let id=0;const timers=new Map();return{timers,setTimeout:fn=>{const k=++id;timers.set(k,fn);return k;},clearTimeout:k=>timers.delete(k),run(){const batch=[...timers.values()];timers.clear();for(const f of batch)f();}};}
await test('Regional loader success clears deadline and resolves once',async()=>{
 const c=clock(),scripts=[];const s={...c,Promise,document:{getElementById:()=>null,createElement:()=>({remove(){this.removed=true;}}),head:{appendChild:x=>scripts.push(x)}}};vm.createContext(s);vm.runInContext(section('const load = (name, timeout','window.__wfgLoad = load;')+'globalThis.subject=load;',s);
 const p=s.subject('x.js');const onload=scripts[0].onload;onload();assert.equal(await p,true);assert.equal(c.timers.size,0);assert.equal(scripts[0].onerror,null);
});
await test('Regional loader deadline resolves false and removes failed script',async()=>{
 const c=clock(),scripts=[];const s={...c,Promise,document:{getElementById:()=>null,createElement:()=>({remove(){this.removed=true;}}),head:{appendChild:x=>scripts.push(x)}}};vm.createContext(s);vm.runInContext(section('const load = (name, timeout','window.__wfgLoad = load;')+'globalThis.subject=load;',s);
 const p=s.subject('x.js');const late=scripts[0].onload;c.run();assert.equal(await p,false);assert.equal(scripts[0].removed,true);late();assert.equal(scripts[0].onload,null);
});
await test('Deadline wrapper handles resolve, reject and indefinite pending work',async()=>{
 const c=clock(),s={...c,Promise};vm.createContext(s);vm.runInContext(section('const withDeadline =','function startupError')+'globalThis.subject=withDeadline;',s);
 assert.equal(await s.subject(Promise.resolve(5),1,null),5);assert.equal(await s.subject(Promise.reject(Error('expected')),1,null),null);const p=s.subject(new Promise(()=>{}),1,99);c.run();assert.equal(await p,99);
});
const report={evidence:'Independent isolated exact-source control-flow tests; not browser or solver evidence',source_sha256:crypto.createHash('sha256').update(html).digest('hex'),checks:results,pass:results.every(x=>x.status==='PASS')};
console.log(JSON.stringify(report,null,2));if(!report.pass)process.exitCode=1;
