const {readFileSync}=require('node:fs');
const vm=require('node:vm');
const assert=require('node:assert/strict');
const source=readFileSync('src/orchid_studio/studio.js','utf8');
const snippet=source.slice(source.indexOf('function installStudioSpacebar('),source.indexOf('// End Studio-wide Space transport.'));
const handlers={};let toggles=0,paused=true,playing=true,starts=0,commands=[];
const context={window:{addEventListener:(name,fn,capture)=>{handlers[name]=fn;if(name!=='blur')assert.equal(capture,true);}},
 command:async({command})=>{commands.push(command);await Promise.resolve();if(command==='status')return{playing,tempo:{paused},looper:{record_slot:null}};if(command==='pause')paused=true;if(command==='resume')paused=false;return{status:'ok'};},
 action:async(fn)=>fn(),loopStart:async(record)=>{assert.equal(record,false);starts++;playing=true;paused=false;},state:null};
vm.createContext(context);vm.runInContext(snippet,context);
function target(type){return{type,isContentEditable:type==='editable',closest(selector){if(selector.startsWith('textarea'))return type==='textarea'||type==='textbox'?this:null;if(selector==='input')return['text','number','range','checkbox','search'].includes(type)?this:null;return null;}};}
function event(type,extra={}){return{code:'Space',key:' ',target:target(type),preventDefault(){this.prevented=true;},stopPropagation(){this.stopped=true;},...extra};}
(async()=>{
 for(const type of ['range','checkbox','select','button','number','slider']){
  const before=paused,e=event(type);handlers.keydown(e);assert(e.prevented&&e.stopped);
  const repeat=event(type,{repeat:true});handlers.keydown(repeat);assert(repeat.prevented);
  const up=event(type);handlers.keyup(up);assert(up.prevented);
  await vm.runInContext('studioTransportQueue',context);assert.equal(paused,!before,type);
 }
 const before=commands.length;
 for(const type of ['text','search','textarea','textbox','editable']){
  const e=event(type);handlers.keydown(e);assert(!e.prevented,type);handlers.keyup(event(type));
 }
 handlers.keydown(event('button',{ctrlKey:true}));handlers.keydown(event('button',{isComposing:true}));
 await vm.runInContext('studioTransportQueue',context);assert.equal(commands.length,before);
 // Two fast complete presses must invert the actual state twice, serially.
 const original=paused;
 for(let i=0;i<2;i++){handlers.keydown(event('button'));handlers.keyup(event('button'));}
 await vm.runInContext('studioTransportQueue',context);assert.equal(paused,original);
 playing=false;handlers.keydown(event('select'));handlers.keyup(event('select'));
 await vm.runInContext('studioTransportQueue',context);assert.equal(starts,1);
 console.log('Space shortcut checks passed: control focus, typing, repeats, rapid presses, stopped start');
})().catch(e=>{console.error(e);process.exitCode=1;});
