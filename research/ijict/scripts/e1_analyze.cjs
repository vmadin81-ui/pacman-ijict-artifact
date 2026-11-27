// E1: deterministic reanalysis of archived timing series, Node.js 22, no dependencies.
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const ROOT=path.resolve(__dirname,'../../..');
const out=path.join(ROOT,'research/ijict/analysis');
const inputs=[
 {id:'search-abc',file:'search-abc-v1.0-browser-ci.json',kind:'search',variants:['A','B','C'],repeats:6,orders:['ABC','BCA','CAB','ACB','CBA','BAC'].map(x=>x.split(''))},
 ...['submit','readback'].map(mode=>({id:'renderer-four-'+mode,file:'renderer-r0123-'+mode+'-v1.0-ci.json',kind:'renderer',mode,variants:['R0','R1','R2','R3'],repeats:8,orders:Array.from({length:8},(_,i)=>{let v=['R0','R1','R2','R3'];if(i>=4)v.reverse();return v.map((_,j)=>v[(i%4+j)%4]);})})),
 ...['submit','readback'].map(mode=>({id:'renderer-two-'+mode,file:'renderer-'+mode+'-v1.0-ci.json',kind:'renderer',mode,variants:['R0','R1'],repeats:8,orders:Array.from({length:8},(_,i)=>i%2?['R1','R0']:['R0','R1'])}))
];
const maps=['Classic','Labyrinth','Crossroads'],pairs={Classic:11025,Labyrinth:10201,Crossroads:12769};
const sorted=a=>a.slice().sort((a,b)=>a-b);
function quantile(a,p){const s=sorted(a),i=(s.length-1)*p,j=Math.floor(i);return s[j]+(s[Math.min(j+1,s.length-1)]-s[j])*(i-j);}
const med=a=>quantile(a,.5);
function stats(a){const q1=quantile(a,.25),q3=quantile(a,.75);return {n:a.length,median:med(a),q1,q3,iqr:q3-q1,min:Math.min(...a),max:Math.max(...a)};}
function bootstrap(ratios){let state=20261125;const rand=()=>{state=(Math.imul(state,1664525)+1013904223)>>>0;return state/4294967296;};const vals=[];for(let b=0;b<20000;b++){const sample=ratios.map(()=>ratios[Math.floor(rand()*ratios.length)]);vals.push(med(sample));}return [quantile(vals,.025),quantile(vals,.975)];}
const near=(a,b)=>Math.abs(a-b)<=1e-8*Math.max(1,Math.abs(a),Math.abs(b));
const report={method:{quantiles:'type 7 / inclusive',bootstrap:'paired block resampling, percentile 95%, conditional exploratory interval',bootstrap_draws:20000,seed:20261125,unit_search:'ms per full query batch',unit_renderer:'microseconds per frame',outliers:'retained',pooling:false},sources:[],descriptive:[],contrasts:[],pairs:[],validation:[]};
for(const input of inputs){
 const raw=fs.readFileSync(path.join(ROOT,'metrics',input.file),'utf8'),d=JSON.parse(raw);
 assert.ok(d.samples.length===maps.length*(input.kind==='search'?2:1)*input.repeats*input.variants.length,input.id);
 if(input.kind==='renderer')assert.equal(d.complete,true);
 report.sources.push({id:input.id,file:input.file,sha256:crypto.createHash('sha256').update(raw).digest('hex'),run_id:d.run_id,commit:d.commit,chromium:d.chromium,platform:d.platform,series:d.samples.length});
 let totalOps=0,checks=0;
 for(const map of maps)for(const condition of (input.kind==='search'?['BFS','A*']:[input.mode])){
  const samples=d.samples.filter(s=>s.map===map&&(s.algorithm??s.mode)===condition);
  const values=Object.fromEntries(input.variants.map(v=>[v,[]]));
  const unit=input.kind==='search'?'ms/batch':'us/frame';
  const opCount=input.kind==='search'?pairs[map]:120;
  for(let repeat=1;repeat<=input.repeats;repeat++){
   const rows=samples.filter(s=>s.repeat===repeat);
   assert.deepEqual(rows.map(s=>s.version),input.orders[repeat-1],input.id+' '+map+' '+condition+' order');
   for(const s of rows){assert.ok(Number.isFinite(s.ms)&&s.ms>0);assert.equal(s.queries??s.frames,opCount);values[s.version].push(input.kind==='search'?s.ms:s.ms*1000/s.frames);totalOps+=opCount;}
  }
  assert.equal(samples.length,input.repeats*input.variants.length);
  const group={dataset:input.id,map,condition,unit};
  const archived=d.summary.find(s=>s.map===map&&(s.algorithm??s.mode)===condition);
  assert.ok(archived);
  for(const v of input.variants){
   const st=stats(values[v]),a=archived[v],scale=input.kind==='search'?1:1000;
   for(const [key,value] of [['median',a.median_ms??a.median_ms_per_frame],['iqr',a.iqr_ms??a.iqr],['min',a.min_ms??a.min],['max',a.max_ms??a.max]]){assert.ok(near(st[key],value*scale),input.id+' '+map+' '+condition+' '+v+' '+key);checks++;}
   report.descriptive.push({...group,variant:v,...st,...(input.kind==='search'?{median_us_per_query:st.median*1000/opCount}:{})});
  }
  for(let i=0;i<input.variants.length;i++)for(let j=i+1;j<input.variants.length;j++){
   const baseline=input.variants[i],candidate=input.variants[j],a=values[baseline],b=values[candidate],ratios=a.map((x,k)=>x/b[k]),ratio=med(a)/med(b),[lo,hi]=bootstrap(ratios);
   const wins=ratios.filter(x=>x>1+1e-10).length,losses=ratios.filter(x=>x<1-1e-10).length;
   report.contrasts.push({...group,baseline,candidate,n:a.length,ratio_of_medians:ratio,reduction_pct:100*(1-1/ratio),paired_median_ratio:med(ratios),paired_ci_low:lo,paired_ci_high:hi,wins,ties:a.length-wins-losses,losses});
   for(let k=0;k<a.length;k++)report.pairs.push({...group,baseline,candidate,repeat:k+1,baseline_time:a[k],candidate_time:b[k],ratio:ratios[k]});
  }
 }
 report.validation.push({dataset:input.id,series:d.samples.length,operations:totalOps,archived_summary_values_matched:checks,balanced_orders:true,complete:true});
}
const csv=rows=>{const keys=[...new Set(rows.flatMap(Object.keys))];const q=v=>v===undefined?'':('"'+String(v).replaceAll('"','""')+'"');return keys.join(',')+'\n'+rows.map(r=>keys.map(k=>q(r[k])).join(',')).join('\n')+'\n';};
const f=(x,n=3)=>x.toFixed(n);
const md=['# E1 — retrospective benchmark statistics','', 'All five archived datasets analyzed separately. Paired bootstrap intervals are exploratory, conditional on these runs; not population confidence or independent replication. All timings retained.','', '## Primary comparisons','', '| Dataset | Map | Condition | Baseline → candidate | Median ratio | Reduction % | Paired median | 95% bootstrap interval | W/T/L |','|---|---|---|---|---:|---:|---:|---|---|',...report.contrasts.filter(r=>r.baseline==='A'&&r.candidate==='C'||r.baseline==='R0'&&r.candidate==='R1').map(r=>'| '+[r.dataset,r.map,r.condition,r.baseline+' → '+r.candidate,f(r.ratio_of_medians),f(r.reduction_pct,2),f(r.paired_median_ratio),f(r.paired_ci_low)+'–'+f(r.paired_ci_high),[r.wins,r.ties,r.losses].join('/')].join(' | ')+' |'),'','## All descriptive statistics','','| Dataset | Map | Condition | Variant | n | Median | Q1 | Q3 | IQR | Min | Max |','|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|',...report.descriptive.map(r=>'| '+[r.dataset,r.map,r.condition,r.variant,r.n,...['median','q1','q3','iqr','min','max'].map(k=>f(r[k]))].join(' | ')+' |'),'','Search: ms per batch; renderer: µs per frame. See JSON and CSV for all contrasts and paired observations.',''].join('\n');
fs.mkdirSync(out,{recursive:true});
for(const [file,content] of [['e1-results.json',JSON.stringify(report,null,2)+'\n'],['e1-descriptive.csv',csv(report.descriptive)],['e1-contrasts.csv',csv(report.contrasts)],['e1-pairs.csv',csv(report.pairs)],['e1-summary.md',md]])fs.writeFileSync(path.join(out,file),content);
console.log(JSON.stringify({validation:report.validation,descriptive:report.descriptive.length,contrasts:report.contrasts.length,pairs:report.pairs.length}));
