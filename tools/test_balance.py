"""Verify ghost mode timing, pause, power override and geometry."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
CHECK="""()=>{
 const checks={};
 const check=(name,value)=>{checks[name]=Boolean(value);if(!value)throw Error(name);};
 for(const level of Object.keys(DIFFICULTIES)){
  game.stop();game.difficulty.value=level;game.strategy.value=DIFFICULTIES[level].strategy;game.start();game.cancel();
  const m=game.ghostMode,p=game.profile;
  check(level+'_initial',m.mode(0)==='SCATTER'&&m.remaining===p.scatter);
  for(let i=0;i<p.scatter;i++)m.tick(0);
  check(level+'_chase',m.base==='CHASE'&&m.remaining===p.chase);
  m.tick(1);check(level+'_power_override',m.mode(1)==='FRIGHTENED'&&m.remaining===p.chase);
  game.togglePause();game.update();check(level+'_pause',m.remaining===p.chase);game.togglePause();game.cancel();
  for(let i=0;i<p.chase;i++)m.tick(0);
  check(level+'_scatter',m.base==='SCATTER'&&m.remaining===p.scatter);
  game.player.x=60;game.player.y=20;game.update();
  check(level+'_power_duration',game.power===p.power&&game.ghost.speed===p.frightened);
  game.stop();game.start();game.cancel();
  let seed=42;
  for(let i=0;i<10000&&game.active;i++){
   if(i%17===0){seed=(Math.imul(seed,1664525)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(seed/4294967296*4)];}
   game.update();
   for(const e of [game.player,game.ghost]){
    if(e.x<16-1e-7||e.y<16-1e-7||e.x>664+1e-7||e.y>344+1e-7)throw Error('boundary');
    for(const {row,col} of game.maze.walls){
     const x=col*40,y=row*40;
     if((e.x-Math.max(x,Math.min(e.x,x+40)))**2+(e.y-Math.max(y,Math.min(e.y,y+40)))**2<256-1e-7)throw Error('wall');
    }
   }
  }
  check(level+'_geometry',true);
 }
 game.stop();return checks;
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'versions/pacman_v0.11.1.html').read_text(encoding='utf-8'))
    checks=page.evaluate(CHECK)
    assert not errors,errors
    report={'chromium':browser.version,'checks':checks,'errors':errors}
    browser.close()
(ROOT/'metrics/balance-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
