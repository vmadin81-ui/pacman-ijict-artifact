"""FSM, gameplay rules, geometry and UI checks for v0.10."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]
CHECK = """() => {
 const checks = {};
 const check = (name, condition) => {checks[name]=Boolean(condition);if(!condition)throw Error(name);};
 const fresh = () => {game.stop();game.start();game.cancel();};
 const collide = () => {game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();};
 check('initial_ready',game.state==='READY'&&game.lives===3&&game.pellets.remaining.size===104);
 check('four_power_pellets',[...game.pellets.remaining.values()].filter(p=>p.power).length===4);
 let rejected=false;try{game.fsm.transition('VICTORY')}catch{rejected=true}
 check('illegal_transition_rejected',rejected&&game.state==='READY');
 fresh();game.togglePause();const before=game.power;game.update();
 check('pause_freezes',game.state==='PAUSED'&&game.power===before);
 game.togglePause();game.cancel();check('resume',game.state==='PLAYING');
 game.player.x=60;game.player.y=20;game.update();
 check('power_pickup',game.score===50&&game.power===480&&game.pellets.remaining.size===103);
 collide();check('capture',game.score===250&&game.power===480&&game.lives===3);
 collide();check('no_repeat_capture',game.score===250);
 game.ghost.update=()=>{};game.ghost.x=20;game.ghost.y=340;
 for(let i=0;i<480;i++)game.update();
 check('power_expires',game.power===0);
 fresh();game.player.x=380;game.player.y=180;game.update();
 check('ordinary_pickup',game.score===10&&game.pellets.remaining.size===103);
 collide();check('life_loss',game.lives===2&&game.state==='RESPAWNING'&&game.score===10&&game.pellets.remaining.size===103);
 game.togglePause();game.update();check('respawn_pause',game.respawn===60);
 game.togglePause();game.cancel();
 for(let i=0;i<60;i++)game.update();
 check('respawn_complete',game.state==='PLAYING'&&game.shield===180);
 collide();check('shield_protects',game.lives===2);
 game.ghost.update=()=>{};game.ghost.x=20;game.ghost.y=340;
 for(let i=0;i<180;i++)game.update();
 check('shield_expires',game.shield===0);
 collide();check('second_loss',game.lives===1);
 for(let i=0;i<60;i++)game.update();
 game.shield=0;collide();check('game_over',game.state==='GAME_OVER'&&game.lives===0);
 fresh();game.pellets.remaining.clear();game.update();
 check('victory',game.state==='VICTORY');
 fresh();check('restart',game.lives===3&&game.score===0&&game.pellets.remaining.size===104);
 for(const level of ['easy','normal','hard','expert']){
   game.stop();game.difficulty.value=level;game.difficulty.dispatchEvent(new Event('change'));
   fresh();
   let seed=42;
   const speed=game.ghost.speed;
   check('speed_'+level,speed===DIFFICULTIES[level].speed);
   for(let i=0;i<5000;i++){
     if(i%17===0){seed=(Math.imul(seed,1664525)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(seed/4294967296*4)];}
     game.player.update();game.ghost.update(game.player);
     for(const e of [game.player,game.ghost]){
       if(e.x<16-1e-7||e.y<16-1e-7||e.x>664+1e-7||e.y>344+1e-7)throw Error('boundary '+level);
       for(const {row,col} of game.maze.walls){
         const x=col*40,y=row*40;
         if((e.x-Math.max(x,Math.min(e.x,x+40)))**2+(e.y-Math.max(y,Math.min(e.y,y+40)))**2<256-1e-7)throw Error('wall '+level);
       }
     }
   }
   check('geometry_'+level,true);
 }
 game.stop();return checks;
}"""
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    page=browser.new_page()
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.set_content((ROOT/'versions/pacman_v0.10.html').read_text(encoding='utf-8'))
    checks=page.evaluate(CHECK)
    page.locator('#start').click()
    assert page.locator('#strategy').is_disabled()
    page.locator('#pause').click()
    assert page.evaluate("game.state==='PAUSED'")
    page.locator('#pause').click()
    assert page.evaluate("game.state==='PLAYING'")
    page.locator('#stop').click()
    assert page.evaluate("game.state==='READY'")
    assert not errors,errors
    report={'chromium':browser.version,'checks':checks,'ui':'passed','errors':errors,'geometry_steps':20000}
    browser.close()
(ROOT/'metrics/mechanics-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
