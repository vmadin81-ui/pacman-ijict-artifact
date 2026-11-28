"""Compare gameplay traces and check the Canvas presentation."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
TRACE="""({level,seed})=>{
 game.stop();game.difficulty.value=level;game.strategy.value=DIFFICULTIES[level].strategy;game.seed.value=seed;
 game.start();game.cancel();let rng=seed,trace=[];
 for(let i=0;i<5000;i++){
  if(i%17===0){rng=(Math.imul(1664525,rng)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(rng/4294967296*4)];}
  game.update();game.render();
  trace.push([game.state,game.lives,game.score,game.power,game.shield,game.respawn,game.captureLocked,game.player.x,game.player.y,game.ghost.x,game.ghost.y,game.player.direction,game.ghost.direction,[...game.pellets.remaining.keys()]]);
 }
 return trace;
}"""
VISUAL="""()=>{
 const checks={};
 const check=(name,value)=>{checks[name]=Boolean(value);if(!value)throw Error(name);};
 game.stop();const renderer=game.renderer, ctx=renderer.context;
 check('wall_coverage',renderer.wallShapes.reduce((n,w)=>n+w.width*w.height,0)===game.maze.walls.length);
 check('life_icons',document.getElementById('lives').childElementCount===3);
 const p=[...game.pellets.remaining.values()].find(x=>x.power);
 const phase=renderer.phase;renderer.phase=0;renderer.drawPellet(p);
 const a=ctx.getImageData(p.x-8,p.y-8,16,16).data.slice();
 renderer.phase=12;renderer.drawPellet(p);
 const b=ctx.getImageData(p.x-8,p.y-8,16,16).data;
 check('pellet_pulse',a.some((x,i)=>x!==b[i]));renderer.phase=phase;
 game.start();game.cancel();game.togglePause();
 check('pause_overlay',!renderer.overlay.hidden&&renderer.overlayTitle.textContent==='Пауза');
 game.togglePause();game.cancel();
 const mouth=(phase)=>{renderer.phase=phase;ctx.clearRect(0,0,680,360);renderer.drawPlayer(game.player,0,true);return ctx.getImageData(game.player.x-16,game.player.y-16,32,32).data;};
 check('mouth_animation',mouth(0).some((x,i)=>x!==mouth(4)[i]));
 const eyes=(direction)=>{game.ghost.direction=direction;ctx.clearRect(0,0,680,360);renderer.drawGhost(game.ghost,0);return ctx.getImageData(game.ghost.x-16,game.ghost.y-16,32,32).data;};
 const left=eyes(DIRECTIONS[2]),right=eyes(DIRECTIONS[0]);
 check('directional_eyes',left.some((x,i)=>x!==right[i]));
 game.pellets.remaining.clear();game.update();game.render();
 check('victory_overlay',renderer.overlayTitle.textContent==='Победа!');
 game.start();game.cancel();game.lives=1;game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();game.render();
 check('defeat_overlay',renderer.overlayTitle.textContent==='Игра окончена'&&renderer.lifeIcons.childElementCount===0);
 game.stop();check('reset_overlay',renderer.overlay.hidden);
 return checks;
}"""
# Compute mouth frames once per phase rather than per pixel.
VISUAL=VISUAL.replace("check('mouth_animation',mouth(0).some((x,i)=>x!==mouth(4)[i]));","const m0=mouth(0),m4=mouth(4);check('mouth_animation',m0.some((x,i)=>x!==m4[i]));")
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    pages=[browser.new_page(reduced_motion='no-preference') for _ in range(2)]
    errors=[]
    for page,version in zip(pages,['0.10','0.11']):
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.set_content((ROOT/f'versions/pacman_v{version}.html').read_text(encoding='utf-8'))
    scenarios=[]
    for level in ['easy','normal','hard','expert']:
        for seed in [42,7,2026]:
            args={'level':level,'seed':seed}
            assert pages[0].evaluate(TRACE,args)==pages[1].evaluate(TRACE,args),args
            scenarios.append({**args,'steps':5000,'equal':True})
    checks=pages[1].evaluate(VISUAL)
    pages[1].locator('#start').click()
    pages[1].locator('#pause').click()
    assert pages[1].locator('#overlay').is_visible()
    pages[1].locator('#pause').click()
    assert not pages[1].locator('#overlay').is_visible()
    pages[1].locator('#stop').click()
    pages[1].set_viewport_size({'width':375,'height':800})
    assert pages[1].evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    report={'chromium':browser.version,'scenarios':scenarios,'visual_checks':checks,'ui':'passed','errors':errors}
    browser.close()
(ROOT/'metrics/visual-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
