import test from 'node:test';
import assert from 'node:assert/strict';
import {demoData,validateArtifact,loadArtifact,pointAlong,adaptRecordedTrack} from '../src/data.mjs';
const copy=()=>JSON.parse(JSON.stringify(demoData));
test('bundled fixture is valid and every route follows declared roads',()=>assert.deepEqual(validateArtifact(demoData),{ok:true,errors:[]}));
test('invalid geometry and undeclared route segments are rejected',()=>{
 for(const mutation of [x=>x.routes.selected[10]=[63,45],x=>x.roads[0].points[0][0]=NaN,x=>x.destination=[999,2],x=>x.fire.radius=Infinity,x=>x.duration=3600,x=>x.mode='live']){const x=copy();mutation(x);assert.equal(validateArtifact(x).ok,false);}
});
test('distance interpolation obeys corners and degenerate segments',()=>{
 assert.deepEqual(pointAlong([[0,0],[10,0],[10,30]],.5),[10,10]);assert.deepEqual(pointAlong([[3,3],[3,3]],1),[3,3]);assert.deepEqual(pointAlong([[0,0],[10,0]],-1),[0,0]);
});
test('recorded adapter preserves source distinction and suppresses invented incident',()=>{
 const data=adaptRecordedTrack({version:1,kind:'recorded-track',title:'Test recording',source:'Synthetic unit test only',recordedAt:'2026-10-11T00:00:00+08:00',coordinates:[[129,37],[129.001,37.002],[129.003,37.004]]});
 assert.equal(data.mode,'recorded');assert.equal(data.fire.radius,0);assert.equal(data.provenance.terrain,'illustrative');assert.equal(data.provenance.track,'recorded-user-supplied');assert.deepEqual(validateArtifact(data),{ok:true,errors:[]});
});
test('invalid payloads reject before rendering',async()=>{
 await assert.rejects(loadArtifact({size:10,text:async()=>'{broken'}));await assert.rejects(loadArtifact({size:6*1024*1024,text:async()=>JSON.stringify(demoData)}));
 assert.throws(()=>adaptRecordedTrack({version:1,kind:'recorded-track',title:'x',source:'x',recordedAt:'bad',coordinates:[[0,0],[0,0]]}));
});
