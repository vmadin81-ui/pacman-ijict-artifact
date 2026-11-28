"""Exhaustive static path checks and deterministic moving-player scenarios."""
import json
import os
import hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = """() => {
 const maze=game.maze, cells=[];
 for(let r=0;r<maze.rows;r++)for(let c=0;c<maze.cols;c++)
 if(maze.isWalkable(r,c))cells.push({row:r,col:c});
 const totals={BFS:{expanded:0,steps:0},'A*':{expanded:0,steps:0}};
 let pairs=0;
 for(const start of cells){
   const distances=new Map([[maze.key(start.row,start.col),0]]), q=[start];
   for(let i=0;i<q.length;i++){
     const p=q[i], d=distances.get(maze.key(p.row,p.col));
     for(const v of DIRECTIONS){
       const r=p.row+v.y,c=p.col+v.x,k=maze.key(r,c);
       if(maze.isWalkable(r,c)&&!distances.has(k)){distances.set(k,d+1);q.push({row:r,col:c});}
     }
   }
   for(const target of cells){
     pairs++;
     for(const name of ['BFS','A*']){
       const result=PathSearch.find(maze,start,target,name==='A*');
       if(!result.path||result.path.length!==distances.get(maze.key(target.row,target.col)))throw Error('Nonoptimal path '+name);
       let r=start.row,c=start.col;
       for(const d of result.path){r+=d.y;c+=d.x;if(!maze.isWalkable(r,c))throw Error('Wall');}
       if(r!==target.row||c!==target.col)throw Error('Wrong target');
       totals[name].expanded+=result.expanded;totals[name].steps+=result.path.length;
     }
   }
 }
 return {pairs,totals};
}"""
DYNAMIC = """({strategy,seed})=>{
 game.strategy.value=strategy;game.seed.value=seed;game.reset();
 let state=seed>>>0, firstContact=null, contacts=0, trace=[];
 for(let i=0;i<10000;i++){
   if(i%17===0){state=(Math.imul(1664525,state)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(state/4294967296*4)];}
   game.update();
   for(const e of [game.player,game.ghost]){
     if(e.x<16||e.y<16||e.x>664||e.y>344)throw Error('Outside');
     for(const {row,col} of game.maze.walls){
       const x=col*40,y=row*40;
       if((e.x-Math.max(x,Math.min(e.x,x+40)))**2+(e.y-Math.max(y,Math.min(e.y,y+40)))**2<256)throw Error('Collision with wall');
     }
   }
   if(game.score+game.pellets.remaining.size!==104)throw Error('Score');
   if(Math.hypot(game.player.x-game.ghost.x,game.player.y-game.ghost.y)<=32){contacts++;if(firstContact===null)firstContact=i+1;}
   trace.push([game.player.x,game.player.y,game.ghost.x,game.ghost.y,game.score]);
 }
 return {firstContact,contacts,score:game.score,trace};
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'versions/pacman_v0.09.html').read_text(encoding='utf-8'))
    static=page.evaluate(STATIC)
    assert static['pairs']==11025
    dynamic=[]
    for strategy in ['Random','Greedy','BFS','A*']:
        for seed in [42,7,2026]:
            args={'strategy':strategy,'seed':seed}
            result=page.evaluate(DYNAMIC,args)
            assert result==page.evaluate(DYNAMIC,args)
            trace=result.pop('trace')
            dynamic.append({**args,**result,'steps':10000,'trace_sha256':hashlib.sha256(json.dumps(trace,separators=(',',':')).encode()).hexdigest()})
    page.locator('#strategy').select_option('BFS')
    page.locator('#start').click()
    assert page.locator('#strategy').is_disabled() and page.locator('#seed').is_disabled()
    page.keyboard.press('ArrowRight')
    page.wait_for_function('game.player.x>340')
    page.locator('#stop').click()
    assert page.locator('#strategy').is_enabled() and not page.evaluate('game.running')
    assert not errors,errors
    report={'chromium':browser.version,'static':static,'dynamic':dynamic,'ui':'passed','errors':errors}
    browser.close()
(ROOT/'metrics/ai-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
