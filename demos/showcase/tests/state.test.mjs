import test from 'node:test';
import assert from 'node:assert/strict';
import {initialState,reduce} from '../src/state.mjs';
test('play reaches terminal frame, restart and scrub set chapter coherently',()=>{
 let s=reduce(initialState(),{type:'scrub',time:107.99});s=reduce(s,{type:'play'});s=reduce(s,{type:'tick',dt:20});assert.equal(s.time,108);assert.equal(s.playing,false);assert.equal(s.chapter,2);
 s=reduce(s,{type:'restart'});assert.equal(s.time,0);assert.equal(s.chapter,0);assert.equal(s.playing,true);
 s=reduce(s,{type:'scrub',time:50});assert.equal(s.chapter,1);assert.equal(s.playing,false);
});
test('manual orbit pauses guided view and reset restores scene without erasing language',()=>{
 let s=reduce(initialState(),{type:'language',value:'en'});s=reduce(s,{type:'play'});s=reduce(s,{type:'interaction'});assert.equal(s.playing,false);assert.equal(s.cameraManual,true);
 s=reduce(s,{type:'reset'});assert.equal(s.lang,'en');assert.equal(s.cameraManual,false);assert.equal(s.time,0);
});
test('untrusted controls remain bounded and layers immutable',()=>{
 const s=initialState();const n=reduce(s,{type:'layer',key:'forest',value:false});assert.equal(s.layers.forest,true);assert.equal(n.layers.forest,false);
 assert.equal(reduce(s,{type:'scrub',time:-2}).time,0);assert.equal(reduce(s,{type:'scrub',time:Infinity}).time,108);assert.equal(reduce(s,{type:'view',value:'bad'}).view,'cinematic');
});
