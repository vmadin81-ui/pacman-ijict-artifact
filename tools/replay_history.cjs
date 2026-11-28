// Reproduce deterministic historical experiments without modifying archived data.
const fs=require('node:fs');
const assert=require('node:assert/strict');
const {execFileSync}=require('node:child_process');
const read=p=>JSON.parse(fs.readFileSync('metrics/'+p,'utf8'));
const report={checks:[],complete:false};
const save=()=>fs.writeFileSync('metrics/historical-replay-v1.0.json',JSON.stringify(report,null,2)+'\n');
function run(tool){return execFileSync(process.execPath,['tools/'+tool],{encoding:'utf8',maxBuffer:64*1024*1024,timeout:480000});}
function exact(tool,archives,partition){
 const actual=JSON.parse(run(tool));
 let expected=archives.flatMap(p=>read(p).rows);
 // Canonical ordering: archived partitions may be arranged differently.
 const key=x=>JSON.stringify([x.version??'',x.id??'',x.map??'',x.order??'',x.level??'',x.mode,x.seed]);
 const sort=x=>x.slice().sort((a,b)=>key(a).localeCompare(key(b)));
 assert.deepEqual(sort(actual),sort(expected));
 report.checks.push({tool,archives,rows:actual.length,steps:actual.reduce((s,r)=>s+r.steps,0),matched:true});
 save();console.log('PASS '+tool+' '+actual.length);
}
function paired(tool,archive,rows){
 const output=run(tool).trim().split(/\r?\n/).map(line=>{const [level,n,steps]=line.trim().split(/\s+/);return {level,n:Number(n),steps:Number(steps)};});
 const expected=rows.map(x=>({level:x.level,n:x.pairs??x.sessions,steps:x.steps}));
 assert.deepEqual(output,expected);
 report.checks.push({tool,archives:[archive],pairs:expected.reduce((s,x)=>s+x.n,0),stepsPerVersion:expected.reduce((s,x)=>s+x.steps,0),matched:true,comparison:'exact paired records within runner; archived counts and steps'});
 save();console.log('PASS '+tool);
}
const tasks=[
 ['balance_v010.cjs',['balance-v0.10.json']],
 ['balance_v0111.cjs',['balance-v0.11.1.json']],
 ['balance_expert_repeat.cjs',['balance-expert-repeat-v0.11.1.json']],
 ['balance_expert_sweep.cjs',['balance-expert-sweep-v0.11.1.json']],
 ['balance_expert_validation.cjs',['balance-expert-validation-v0.11.1.json']],
 ['balance_levels_v0111.cjs',['balance-levels-v0.11.1.json']],
 ['test_campaign.cjs',['campaign-v0.12.0.json']],
 ['balance_maps_v0120.cjs',['map-classic-v0.12.0.json','map-crossroads-v0.12.0.json','map-labyrinth-v0.12.0.json']],
 ['balance_campaign_order_v0120.cjs',['campaign-order-a-v0.12.0.json','campaign-order-b-v0.12.0.json','campaign-order-c-v0.12.0.json']]
];
for(const [tool,archives] of tasks){try{exact(tool,archives);}catch(e){report.checks.push({tool,matched:false,error:String(e).slice(0,3000)});save();console.error('FAIL '+tool+' '+e.message.slice(0,300));}}
for(const [tool,archive,field] of [['audio_regression_v0121.cjs','audio-regression-v0.12.1.json','rows'],['records_regression_v0122.cjs','records-regression-v0.12.2.json','summary']]){try{paired(tool,archive,read(archive)[field]);}catch(e){report.checks.push({tool,matched:false,error:String(e).slice(0,3000)});save();}}
report.complete=true;save();console.log(JSON.stringify(report));if(report.checks.some(x=>!x.matched))process.exitCode=1;
