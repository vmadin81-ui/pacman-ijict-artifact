"""Exhaustive search comparison and paired browser benchmark for the archived heap candidate."""
import json
import os
import platform
import statistics
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
def source(path):
    html=(ROOT/path).read_text(encoding='utf-8')
    return html.split('<script>',1)[1].split('</script>',1)[0].split('const game = new Game(',1)[0]+'\nreturn {PathSearch,Maze,LevelManager,CONFIG};'
CHECK=r"""({oldSource,newSource})=>{
 const old=new Function(oldSource)(),next=new Function(newSource)();
 const results=[],samples=[];
 for(const l of new next.LevelManager().levels){
  const m=new next.Maze(l.map,next.CONFIG.cellSize),cells=[];
  for(let row=0;row<m.rows;row++)for(let col=0;col<m.cols;col++)if(m.isWalkable(row,col))cells.push({row,col});
  const pairs=cells.flatMap(a=>cells.map(b=>[a,b]));
  const distances=new Map();
  for(const start of cells){
   const d=new Map([[m.key(start.row,start.col),0]]),q=[start];
   for(let i=0;i<q.length;i++){
    const p=q[i];
    for(const [dr,dc] of [[0,1],[1,0],[0,-1],[-1,0]]){
     const row=p.row+dr,col=p.col+dc,k=m.key(row,col);
     if(m.isWalkable(row,col)&&!d.has(k)){d.set(k,d.get(m.key(p.row,p.col))+1);q.push({row,col});}
    }
   }
   distances.set(m.key(start.row,start.col),d);
  }
  for(const heuristic of [false,true]){
   const algorithm=heuristic?'A*':'BFS';
   let expanded=0,checksum=0;
   for(const [p,q] of pairs){
    const a=old.PathSearch.find(m,p,q,heuristic),b=next.PathSearch.find(m,p,q,heuristic);
    if(JSON.stringify(a)!==JSON.stringify(b))throw Error('equivalence '+l.name+' '+algorithm);
    if(b.path.length!==distances.get(m.key(p.row,p.col)).get(m.key(q.row,q.col)))throw Error('distance');
    let row=p.row,col=p.col;
    for(const d of b.path){row+=d.y;col+=d.x;if(!m.isWalkable(row,col))throw Error('illegal path');}
    if(row!==q.row||col!==q.col)throw Error('target');
    expanded+=b.expanded;checksum+=b.path.length;
   }
   results.push({map:l.name,algorithm,vertices:cells.length,pairs:pairs.length,expanded,checksum,matched:pairs.length});
   const run=engine=>{
    let sum=0,visited=0;const t=performance.now();
    for(const [p,q] of pairs){const r=engine.PathSearch.find(m,p,q,heuristic);sum+=r.path.length;visited+=r.expanded;}
    const ms=performance.now()-t;
    if(sum!==checksum||visited!==expanded)throw Error('benchmark checksum');
    return ms;
   };
   run(old);run(next);
   for(let repeat=0;repeat<10;repeat++)for(const version of repeat%2?['heap','baseline']:['baseline','heap'])
    samples.push({map:l.name,algorithm,repeat:repeat+1,version,queries:pairs.length,ms:run(version==='heap'?next:old)});
  }
 }
 return {results,samples};
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    page=browser.new_page()
    report=page.evaluate(CHECK,{'oldSource':source('versions/pacman_v0.12.2.html'),'newSource':source('experiments/pacman_v1.0-heap.html')})
    report.update(chromium=browser.version,platform=platform.platform(),processor=platform.processor(),commit=os.environ.get('GITHUB_SHA'))
    browser.close()
report['summary']=[]
for r in report['results']:
    row={k:r[k] for k in ('map','algorithm')}
    for version in ('baseline','heap'):
        values=[s['ms'] for s in report['samples'] if s['map']==r['map'] and s['algorithm']==r['algorithm'] and s['version']==version]
        q=statistics.quantiles(values,n=4,method='inclusive')
        row[version]={'median_ms':statistics.median(values),'iqr_ms':q[2]-q[0],'min_ms':min(values),'max_ms':max(values)}
    row['reduction_pct']=100*(1-row['heap']['median_ms']/row['baseline']['median_ms'])
    report['summary'].append(row)
(ROOT/'metrics/search-benchmark-v1.0-browser.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
