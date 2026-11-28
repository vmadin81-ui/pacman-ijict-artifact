"""Measure static search implementation costs; report raw samples, not CI speed guarantees."""
import json
import os
import platform
import statistics
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
BENCH="""() => {
 const maze=game.maze,cells=[];
 for(let r=0;r<maze.rows;r++)for(let c=0;c<maze.cols;c++)if(maze.isWalkable(r,c))cells.push({row:r,col:c});
 const pairs=cells.flatMap(a=>cells.map(b=>[a,b]));
 function run(name){
   let checksum=0;
   const begin=performance.now();
   for(const [a,b] of pairs)checksum+=PathSearch.find(maze,a,b,name==='A*').path.length;
   const ms=performance.now()-begin;
   if(checksum!==105536)throw Error('Unexpected checksum');
   return ms;
 }
 run('BFS');run('A*');
 const samples=[];
 for(let i=0;i<10;i++)for(const strategy of (i%2?['A*','BFS']:['BFS','A*']))
 samples.push({repeat:i+1,strategy,ms:run(strategy),queries:pairs.length});
 return samples;
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    page=browser.new_page()
    page.set_content((ROOT/'versions/pacman_v0.09.html').read_text(encoding='utf-8'))
    samples=page.evaluate(BENCH)
    report={'chromium':browser.version,'platform':platform.platform(),'commit':os.environ.get('GITHUB_SHA'),'samples':samples,'summary':{}}
    for name in ('BFS','A*'):
        values=[s['ms'] for s in samples if s['strategy']==name]
        q=statistics.quantiles(values,n=4,method='inclusive')
        report['summary'][name]={'median_ms':statistics.median(values),'iqr_ms':q[2]-q[0],'min_ms':min(values),'max_ms':max(values)}
    browser.close()
(ROOT/'metrics/ai-benchmark.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
