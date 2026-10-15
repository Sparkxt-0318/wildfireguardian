import { heightAt, pointAlong } from './data.mjs';
export function createFallback(host,data,onInteraction){
 const canvas=document.createElement('canvas');canvas.setAttribute('aria-label','2D illustrative terrain and road journey');host.append(canvas);
 const ctx=canvas.getContext('2d');if(!ctx)throw new Error('Canvas unavailable');
 const base=document.createElement('canvas'), b=base.getContext('2d');
 let w=1,h=1,dpr=1,frame=0,lastLayers='',lastState=null;
 const xy=([x,z])=>{const scale=Math.max(1,Math.min(w/170,(h-130)/124));return [w*.55+x*scale,h*.51+z*scale];};
 const line=(points,color,width,dash=[])=>{ctx.beginPath();points.forEach((p,i)=>{const [x,y]=xy(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});ctx.strokeStyle=color;ctx.lineWidth=width;ctx.setLineDash(dash);ctx.stroke();ctx.setLineDash([]);};
 function rebuild(){
  b.clearRect(0,0,w,h);b.fillStyle='#07131b';b.fillRect(0,0,w,h);
  const cell=2;
  for(let z=-52;z<52;z+=cell)for(let x=-70;x<70;x+=cell){
   const y=heightAt(x,z), light=(heightAt(x-1,z)-heightAt(x+1,z))*3+12+y*.32;
   b.fillStyle=`hsl(${185-y*.55} 22% ${Math.max(7,Math.min(22,light))}%)`;
   const [px,pz]=xy([x,z]); const [nx,nz]=xy([x+cell,z+cell]);b.fillRect(px,pz,nx-px+1,nz-pz+1);
  }
  b.strokeStyle='rgba(160,207,207,.18)';b.lineWidth=.7;
  for(let level=4;level<=24;level+=2){b.beginPath();
   for(let z=-52;z<52;z+=2)for(let x=-70;x<70;x+=2){
    const corners=[[x,z],[x+2,z],[x+2,z+2],[x,z+2]],cuts=[];
    for(let e=0;e<4;e++){const a=corners[e],c=corners[(e+1)%4],ha=heightAt(...a),hc=heightAt(...c);if((ha<level)!==(hc<level)){const t=(level-ha)/(hc-ha);cuts.push(xy([a[0]+(c[0]-a[0])*t,a[1]+(c[1]-a[1])*t]));}}
    for(let k=1;k<cuts.length;k+=2){b.moveTo(...cuts[k-1]);b.lineTo(...cuts[k]);}
   }b.stroke();
  }
  b.strokeStyle='rgba(126,170,182,.12)';b.lineWidth=.5;
  for(let x=0;x<w;x+=48){b.beginPath();b.moveTo(x,0);b.lineTo(x,h);b.stroke();}
  for(let y=0;y<h;y+=48){b.beginPath();b.moveTo(0,y);b.lineTo(w,y);b.stroke();}
 }
 function resize(){const r=host.getBoundingClientRect();w=Math.max(1,r.width);h=Math.max(1,r.height);dpr=Math.min(2,devicePixelRatio||1);canvas.width=w*dpr;canvas.height=h*dpr;canvas.style.cssText='width:100%;height:100%;display:block;touch-action:pan-y';ctx.setTransform(dpr,0,0,dpr,0,0);base.width=w;base.height=h;rebuild();}
 function update(state,dt){
  lastState=state;frame++;ctx.clearRect(0,0,w,h);ctx.drawImage(base,0,0,w,h);
  if(state.layers.forest){b.fillStyle='#234d42';for(let i=0;i<220;i++){const x=Math.sin(i*123.7)*65,z=Math.sin(i*66.87)*48;const [px,py]=xy([x,z]);ctx.fillStyle='rgba(40,83,68,.5)';ctx.beginPath();ctx.arc(px,py,1.8,0,Math.PI*2);ctx.fill();}}
  data.roads.forEach(r=>{line(r.points,'#10272f',5);line(r.points,'#82969a',1.1);});
  if(state.layers.fire&&data.fire.radius>0){const [fx,fy]=xy(data.fire.center),radius=data.fire.radius*(1+state.time/250)*w/170;const glow=ctx.createRadialGradient(fx,fy,0,fx,fy,radius*1.8);glow.addColorStop(0,'rgba(255,91,33,.6)');glow.addColorStop(.55,'rgba(224,75,23,.25)');glow.addColorStop(1,'rgba(220,44,15,0)');ctx.fillStyle=glow;ctx.fillRect(fx-radius*2,fy-radius*2,radius*4,radius*4);ctx.strokeStyle='#ff904b';ctx.fillStyle='rgba(129,49,20,.5)';ctx.beginPath();for(let i=0;i<=90;i++){const a=i/90*Math.PI*2,rr=radius*(.82+Math.sin(a*5)*.12);const x=fx+Math.cos(a)*rr,y=fy+Math.sin(a)*rr*.68;i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.fill();ctx.stroke();}
  if(state.compare)line(data.routes.comparator,'#efad70',2,[4,5]);
  ctx.shadowColor='#54e4f3';ctx.shadowBlur=state.lowEffects?0:12;line(data.routes.selected,'#60e4ec',3);ctx.shadowBlur=0;
  const [sx,sy]=xy(data.start),[dx,dy]=xy(data.destination);for(const [x,y,c] of [[sx,sy,'#d9f5f7'],[dx,dy,'#8af4bd']]){ctx.strokeStyle=c;ctx.fillStyle=c;ctx.beginPath();ctx.arc(x,y,8,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();}
  const progress=Math.max(0,Math.min(1,(state.time-30)/65));const [mx,my]=xy(pointAlong(state.chapter===2?data.deviceTrace:data.routes.selected,progress));ctx.fillStyle='#edffff';ctx.shadowColor='#8cf5ff';ctx.shadowBlur=16;ctx.beginPath();ctx.arc(mx,my,4,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;
  ctx.font='10px monospace';ctx.fillStyle='#a0bfc7';ctx.fillText(state.lang==='ko'?'2D 지형 개요 · 일러스트':'2D TERRAIN OVERVIEW · ILLUSTRATIVE',24,30);
  ctx.fillStyle='#90e9bc';ctx.fillText(state.lang==='ko'?'도착 지점':'DESTINATION',dx+14,dy+4);
  ctx.fillStyle='#a7c4cf';ctx.fillText('N ↑',w-46,30);
 }
 const ro=new ResizeObserver(resize);ro.observe(host);resize();
 return {update,resize,setView(){},reset(){},getDiagnostics:()=>({renderer:'Canvas 2D fallback',frames:frame,width:w,height:h}),dispose(){ro.disconnect();canvas.remove();}};
}
