/** Owner-authored CAD housing exterior; no PCB, battery, antennas, or sensor internals. */
export function createDevice(THREE) {
  const group=new THREE.Group();group.name='Owner housing CAD study';
  const model=new THREE.Group();group.add(model);
  const materials=[
    new THREE.MeshStandardMaterial({color:0x101c24,roughness:.3,metalness:.46}),
    new THREE.MeshStandardMaterial({color:0x33444d,roughness:.27,metalness:.38}),
    new THREE.MeshStandardMaterial({color:0xb49363,roughness:.3,metalness:.55})
  ];
  group.userData={source:'owner-cad-study',assetState:'loading',physicalFit:'unverified',internals:'not shown',artDirection:'Recoloured exterior; Window DEMO trace and illumination are illustrative, not actual device telemetry.'};
  let disposed=false, displayTexture=null, displayContext=null, displayFrame=-1;
  function paintDisplay(seconds){
    if(!displayContext)return;
    const frame=Math.floor(seconds*12);if(frame===displayFrame)return;displayFrame=frame;
    const ctx=displayContext;ctx.fillStyle='#081c24';ctx.fillRect(0,0,168,288);
    ctx.strokeStyle='#16323b';ctx.lineWidth=1;
    for(let x=12;x<168;x+=24){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,288);ctx.stroke();}
    for(let y=12;y<288;y+=24){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(168,y);ctx.stroke();}
    ctx.fillStyle='#8ccbd0';ctx.font='bold 17px sans-serif';ctx.fillText('WFG',17,31);
    ctx.fillStyle='#80a3a8';ctx.font='11px monospace';ctx.fillText('DEMO',112,30);
    const route=[[32,238],[39,201],[86,187],[95,147],[69,111],[117,75]];
    ctx.lineWidth=3;ctx.lineJoin='round';ctx.strokeStyle='#65e7dd';ctx.beginPath();route.forEach((p,i)=>i?ctx.lineTo(...p):ctx.moveTo(...p));ctx.stroke();
    const t=(seconds*.12)%1,segment=Math.min(4,Math.floor(t*5)),f=t*5-segment;
    const a=route[segment],b=route[segment+1];ctx.fillStyle='#ffffff';ctx.beginPath();ctx.arc(a[0]+(b[0]-a[0])*f,a[1]+(b[1]-a[1])*f,5,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle='#a6eabd';ctx.beginPath();ctx.arc(117,75,8,0,Math.PI*2);ctx.stroke();
    ctx.fillStyle='#8bb0b4';ctx.font='10px monospace';ctx.fillText('TRACE / REPLAY',20,271);displayTexture.needsUpdate=true;
  }
  const placeholder=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(6.66,18,5.08)),new THREE.LineBasicMaterial({color:0x6cccd2,transparent:true,opacity:.18}));
  model.add(placeholder);
  const scale=18/81.1;
  function surfaceGeometry(buffer) {
    const view=new DataView(buffer);if(buffer.byteLength<84)throw new Error('Truncated STL.');
    const triangles=view.getUint32(80,true);
    if(triangles<1||triangles>20000||buffer.byteLength!==84+triangles*50)throw new Error('Unexpected exterior STL geometry.');
    const position=new Float32Array(triangles*9);
    for(let t=0;t<triangles;t++)for(let vertex=0;vertex<3;vertex++){
      const from=84+t*50+12+vertex*12,to=t*9+vertex*3;
      const x=view.getFloat32(from,true),y=view.getFloat32(from+4,true),z=view.getFloat32(from+8,true);
      if(![x,y,z].every(Number.isFinite))throw new Error('Invalid STL coordinate.');
      position[to]=-y*scale;position[to+1]=(x-28.75)*scale;position[to+2]=(z+4.651)*scale;
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(position,3));geometry.computeVertexNormals();geometry.computeBoundingSphere();return geometry;
  }
  const names=['WFG_logger_housing_bottom_v1.stl','WFG_logger_housing_top_v1.stl','WFG_logger_plunger_user_v1.stl'];
  const ready=Promise.allSettled(names.map(async(name,index)=>{
    const response=await fetch(new URL(`../public/assets/device/${name}`,import.meta.url),{cache:'force-cache'});if(!response.ok)throw new Error(`CAD asset ${response.status}`);
    const geometry=surfaceGeometry(await response.arrayBuffer());
    const mesh=new THREE.Mesh(geometry,materials[index]);mesh.castShadow=true;mesh.receiveShadow=true;return mesh;
  })).then(results=>{
    const meshes=results.filter(r=>r.status==='fulfilled').map(r=>r.value);
    if(results.some(r=>r.status==='rejected')){meshes.forEach(m=>m.geometry.dispose());if(!disposed)group.userData.assetState='outline-fallback';return false;}
    if(disposed){meshes.forEach(m=>m.geometry.dispose());return false;}
    model.remove(placeholder);placeholder.geometry.dispose();placeholder.material.dispose();
    meshes.forEach(mesh=>model.add(mesh));group.userData.assetState='owner-cad-loaded';
    // Decorative light at the documented display window, not a measured screen or internals.
    const display=document.createElement('canvas');display.width=168;display.height=288;displayContext=display.getContext('2d');displayTexture=new THREE.CanvasTexture(display);displayTexture.colorSpace=THREE.SRGBColorSpace;paintDisplay(0);
    const panel=new THREE.Mesh(new THREE.PlaneGeometry(14*scale,23.5*scale),new THREE.MeshBasicMaterial({map:displayTexture,color:0xadd9df,toneMapped:false}));
    panel.position.set(0,(23.6-28.75)*scale,(4.5+4.651)*scale);model.add(panel);
    return true;
  }).catch(()=>{if(!disposed)group.userData.assetState='outline-fallback';return false;});
  return {group,ready,update(seconds){paintDisplay(seconds);model.rotation.y=.24+Math.sin(seconds*.12)*.12;model.rotation.z=-.085;},dispose(){
    disposed=true;displayTexture?.dispose();const geometries=new Set(),mats=new Set();group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>mats.add(m));});materials.forEach(m=>mats.add(m));geometries.forEach(g=>g.dispose());mats.forEach(m=>m.dispose());
  }};
}
