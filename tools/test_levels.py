"""Browser checks for campaign lifecycle and first-level regression."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
CHECK = r"""() => {
 const checks = {};
 const check = (name, value) => { checks[name] = Boolean(value); if (!value) throw Error(name); };
 const reject = (name, map) => {
  let rejected = false;
  try { LevelValidator.validate(new Level('bad', map)); } catch { rejected = true; }
  check(name, rejected);
 };
 const levels = game.levelManager.levels;
 check('order', levels.map(l=>l.name).join(',') === 'Classic,Labyrinth,Crossroads');
 const maps = levels.map(l=>({name:l.name,...LevelValidator.validate(l)}));
 check('counts', maps.map(m=>m.pellets).join(',') === '104,100,112');
 check('immutable', levels.every(l=>Object.isFrozen(l)&&Object.isFrozen(l.map)));
 reject('bad_dimensions', levels[0].map.slice(1));
 reject('bad_tile', levels[0].map.map((r,i)=>i===0?r.replace('.', 'X'):r));
 reject('missing_player', levels[0].map.map(r=>r.replace('P','.')));
 reject('duplicate_ghost', levels[0].map.map((r,i)=>i===8?'G'+r.slice(1):r));
 reject('blocked_power', levels[0].map.map((r,i)=>i===0?r.slice(0,1)+'#'+r.slice(2):r));
 reject('disconnected', levels[0].map.map((r,i)=>i===1?'#'.repeat(17):r));
 game.start();game.cancel();
 let geometrySteps=0;
 for(let level=0;level<3;level++){
  check('map_'+level,game.maze.map===levels[level].map&&game.renderer.maze===game.maze&&game.player.maze===game.maze&&game.ghost.maze===game.maze);
  check('power_'+level,[...game.pellets.remaining.values()].filter(p=>p.power).length===4);
  const wallKeys=new Set(game.maze.walls.map(w=>game.maze.key(w.row,w.col)));
  const drawn=new Set();
  for(const w of game.renderer.wallShapes)for(let r=w.row;r<w.row+w.height;r++)for(let c=w.col;c<w.col+w.width;c++)drawn.add(game.maze.key(r,c));
  check('walls_'+level,drawn.size===wallKeys.size&&[...drawn].every(k=>wallKeys.has(k)));
  let rng=42;
  // Exercise the real actors without consuming the campaign lives or pellets.
  for(let i=0;i<2000;i++){
   if(i%17===0){rng=(Math.imul(rng,1664525)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(rng/4294967296*4)];}
   game.player.update();game.ghost.update(game.player);geometrySteps++;
   for(const e of [game.player,game.ghost]){
    if(e.x<16-1e-7||e.y<16-1e-7||e.x>664+1e-7||e.y>344+1e-7)throw Error('boundary');
    for(const {row,col} of game.maze.walls){
     const x=col*40,y=row*40;
     if((e.x-Math.max(x,Math.min(e.x,x+40)))**2+(e.y-Math.max(y,Math.min(e.y,y+40)))**2<256-1e-7)throw Error('wall');
    }
   }
  }
  check('geometry_'+level,true);
  game.score=1000+level*100;game.lives=2;game.power=10;game.shield=10;
  game.pellets.remaining.clear();game.update();game.render();
  if(level<2){
   check('clear_'+level,game.state==='LEVEL_CLEAR'&&game.levelWait===120&&!game.renderer.overlay.hidden);
   check('clear_controls_'+level,game.controls.start.disabled&&!game.controls.pause.disabled);
   game.togglePause();game.update();check('pause_'+level,game.state==='PAUSED'&&game.levelWait===120);
   game.togglePause();game.cancel();check('resume_'+level,game.state==='LEVEL_CLEAR');
   for(let i=0;i<119;i++)game.update();
   check('delay_'+level,game.levelManager.index===level&&game.levelWait===1);
   game.update();game.render();
   check('next_'+level,game.state==='PLAYING'&&game.levelManager.index===level+1&&game.score===1000+level*100&&game.lives===2);
   check('reset_transient_'+level,game.power===0&&game.shield===0&&game.respawn===0&&!game.captureLocked&&game.ghostMode.base==='SCATTER'&&game.pellets.remaining.size===maps[level+1].pellets);
   check('hud_'+level,game.hud.textContent.includes(levels[level+1].name)&&game.renderer.overlay.hidden);
  }else check('victory',game.state==='VICTORY'&&game.levelManager.index===2&&!game.renderer.overlay.hidden);
 }
 game.start();game.cancel();check('restart',game.levelManager.index===0&&game.score===0&&game.lives===3&&game.pellets.remaining.size===104);
 game.pellets.remaining.clear();game.update();game.stop();check('stop_clear',game.state==='READY'&&game.levelManager.index===0&&game.pellets.remaining.size===104);
 game.start();game.cancel();game.lives=1;game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();check('defeat',game.state==='GAME_OVER'&&game.lives===0);
 game.stop();
 return {checks,maps,geometrySteps};
}"""
TRACE = r"""({level,seed})=>{
 game.stop();game.difficulty.value=level;game.strategy.value=DIFFICULTIES[level].strategy;game.seed.value=seed;game.start();game.cancel();
 let rng=seed;const trace=[];
 for(let i=0;i<5000;i++){
  if(i%17===0){rng=(Math.imul(rng,1664525)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(rng/4294967296*4)];}
  game.update();
  const state=['LEVEL_CLEAR','VICTORY'].includes(game.state)?'CLEARED':game.state;
  trace.push([state,game.lives,game.score,game.power,game.shield,game.respawn,game.captureLocked,game.player.x,game.player.y,game.ghost.x,game.ghost.y,game.player.direction,game.ghost.direction,game.ghostMode.base,game.ghostMode.remaining,[...game.pellets.remaining.keys()]]);
  if(state==='CLEARED'||state==='GAME_OVER')break;
 }
 game.stop();return trace;
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    old=browser.new_page()
    page=browser.new_page(viewport={'width':375,'height':750})
    errors=[]
    for tab in (old,page):
        tab.on('pageerror',lambda e:errors.append(str(e)))
    old.set_content((ROOT/'versions/pacman_v0.11.1.html').read_text(encoding='utf-8'))
    page.set_content((ROOT/'versions/pacman_v0.12.0.html').read_text(encoding='utf-8'))
    result=page.evaluate(CHECK)
    regression=[]
    for level in ['easy','normal','hard','expert']:
        for seed in [42,7,2026]:
            args={'level':level,'seed':seed}
            a=old.evaluate(TRACE,args)
            b=page.evaluate(TRACE,args)
            assert a==b,(level,seed)
            regression.append({**args,'matchedSteps':len(a)})
    page.locator('#start').click()
    page.locator('#pause').click()
    assert page.locator('#overlayTitle').inner_text()=='Пауза'
    page.locator('#pause').click()
    page.locator('#stop').click()
    assert page.evaluate('game.state==="READY" && game.levelManager.index===0')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    report={'chromium':browser.version,**result,'regression':regression,'ui':'passed','errors':errors}
    browser.close()
(ROOT/'metrics/levels-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
