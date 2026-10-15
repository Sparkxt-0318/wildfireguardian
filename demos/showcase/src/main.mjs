import {demoData,loadArtifact} from './data.mjs';
import {mountUI} from './ui.mjs';
import {initialState,reduce} from './state.mjs';
import {createFallback} from './fallback.mjs';
let data=demoData;
let state=initialState(matchMedia('(prefers-reduced-motion: reduce)').matches);
state.data=data;
const query=new URLSearchParams(location.search);
if(query.get('lang')==='en')state.lang='en';
if(query.get('low')==='1')state.lowEffects=true;
const ui=mountUI(document.querySelector('#app'),state,dispatch);
const host=document.querySelector('#scene-host');
let viewer=null,raf=0,last=0,lastUI=0,frameTimes=[],errorLog=[],initializing=false;
let status='';
let qualityChosen=false,slowFrames=0;
window.addEventListener('error',e=>errorLog.push(String(e.message)));
window.addEventListener('unhandledrejection',e=>errorLog.push(String(e.reason)));
async function initViewer(forceFallback=false){
 initializing=true;viewer?.dispose();viewer=null;
 try{
  if(forceFallback||query.get('fallback')==='1')throw new Error('2D mode requested');
  const {createScene}=await import('./scene.mjs');
  viewer=await createScene(host,data,()=>dispatch({type:'interaction'}));
  const canvas=host.querySelector('canvas');
  canvas?.addEventListener('webglcontextlost',e=>{e.preventDefault();state.playing=false;initViewer(true);},{once:true});
  status='';state.fallback=false;
 }catch(e){
  host.querySelectorAll('canvas').forEach(c=>c.remove());
  viewer=createFallback(host,data,()=>dispatch({type:'interaction'}));
  state.fallback=true;status='';
  if(!forceFallback&&query.get('fallback')!=='1')errorLog.push(`WebGL fallback: ${e.message}`);
 }
 initializing=false;ui.update(state);ui.setStatus(status);window.__WFG__.ready=true;last=0;
 if(!document.hidden&&!raf)raf=requestAnimationFrame(tick);
}
async function dispatch(action){
 if(action.type==='import'){
  if(!action.file)return;
  try{const incoming=await loadArtifact(action.file);data=incoming;state.data=data;state.mode=data.mode;state.time=0;state.chapter=0;state.playing=false;state.compare=false;state.error='';state.importStatus=state.lang==='ko'?'자료를 불러왔습니다':'Local data imported';await initViewer(state.fallback);}
  catch(e){state.error=String(e.message);state.importStatus=(state.lang==='ko'?'불러오기 실패: ':'Import rejected: ')+e.message;ui.update(state);}
  return;
 }
 if(action.type==='info')return;
 if(action.type==='lowEffects')qualityChosen=true;
 state={...reduce(state,action),data,fallback:state.fallback};
 if(action.type==='reset')viewer?.reset();
 if(action.type==='view')viewer?.setView(state.view);
 if(['play','restart','chapter'].includes(action.type))viewer?.setView(state.view);
 ui.update(state);
}
function tick(now){
 raf=0;if(document.hidden||initializing||!viewer){last=0;return;}
 const elapsed=last?Math.min(.1,(now-last)/1000):0; if(last&&now-last<1000){frameTimes.push(now-last);if(frameTimes.length>600)frameTimes.shift();}last=now;
 state={...reduce(state,{type:'tick',dt:elapsed}),data};
 if(!qualityChosen&&!state.lowEffects&&elapsed>.042){slowFrames++;}else{slowFrames=Math.max(0,slowFrames-1);}
 if(slowFrames>90){state.lowEffects=true;qualityChosen=true;ui.update(state);}
 viewer.update(state,state.reducedMotion&&!state.playing?0:elapsed);
 if(now-lastUI>80){ui.update(state);lastUI=now;}
 raf=requestAnimationFrame(tick);
}
document.addEventListener('visibilitychange',()=>{if(document.hidden){cancelAnimationFrame(raf);raf=0;last=0;}else if(!raf){last=0;raf=requestAnimationFrame(tick);}});
window.addEventListener('pagehide',()=>{cancelAnimationFrame(raf);raf=0;viewer?.dispose();});
window.__WFG__={ready:false,getState:()=>({...state,data:{version:data.version,mode:data.mode,provenance:data.provenance}}),diagnostics:()=>({scene:viewer?.getDiagnostics(),frameSamples:frameTimes.length,medianFrameMs:frameTimes.length?[...frameTimes].sort((a,b)=>a-b)[Math.floor(frameTimes.length/2)]:null,errors:[...errorLog],hidden:document.hidden,rafActive:!!raf}),version:'1.0.0'};
initViewer();
