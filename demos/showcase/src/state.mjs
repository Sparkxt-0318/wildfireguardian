export const DURATION = 108;
export function initialState(reducedMotion=false) {
  return {time:0,chapter:0,playing:false,compare:false,view:'cinematic',layers:{forest:true,fire:true},lowEffects:reducedMotion,lang:'ko',mode:'fixture',error:'',reducedMotion,importStatus:'',cameraManual:false};
}
export function reduce(state,action) {
 const next={...state,layers:{...state.layers}};
 switch(action.type){
  case 'play': next.playing=true;if(next.time>=DURATION)next.time=0;next.cameraManual=false;break;
  case 'pause': next.playing=false;break;
  case 'restart': next.time=0;next.playing=true;next.cameraManual=false;next.view='cinematic';break;
  case 'chapter': next.time=Math.min(2,Math.max(0,Number(action.index)||0))*36;next.playing=false;next.cameraManual=false;next.view='cinematic';break;
  case 'scrub': next.time=Math.max(0,Math.min(DURATION,Number(action.time)||0));next.playing=false;next.cameraManual=false;break;
  case 'compare': next.compare=!!action.value;break;
  case 'view': if(['cinematic','follow','overview'].includes(action.value)){next.view=action.value;next.cameraManual=false;}break;
  case 'reset': return {...initialState(state.reducedMotion),lang:state.lang,lowEffects:state.lowEffects,mode:state.mode,importStatus:state.importStatus};
  case 'lowEffects': next.lowEffects=!!action.value;break;
  case 'language': next.lang=action.value==='en'?'en':'ko';break;
  case 'layer': if(['forest','fire'].includes(action.key))next.layers[action.key]=!!action.value;break;
  case 'interaction': next.playing=false;next.cameraManual=true;break;
  case 'tick': if(next.playing)next.time=Math.min(DURATION,next.time+Math.max(0,Math.min(.1,action.dt||0)));if(next.time>=DURATION)next.playing=false;break;
 }
 next.chapter=Math.min(2,Math.floor(next.time/36));return next;
}
