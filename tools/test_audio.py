"""Audio events, native Web Audio lifecycle and muted/unavailable regression."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
CHECK=r"""async ()=>{
 const checks={};
 const check=(n,v)=>{checks[n]=Boolean(v);if(!v)throw Error(n);};
 check('native_context',game.audio.context?.state==='running');
 const audio=game.audio;
 audio.stopAll();
 audio.play('power');check('native_voices',audio.voices.size===3);
 audio.setMuted(true);check('mute_stops',audio.voices.size===0&&audio.master.gain.value===0);
 audio.play('victory');check('mute_blocks',audio.voices.size===0);
 audio.setMuted(false);audio.setVolume(.5);check('volume',Math.abs(audio.master.gain.value-.1)<1e-6);
 audio.setVolume(0);audio.play('pellet');check('zero_volume',audio.voices.size===0);
 audio.setVolume(.35);for(let i=0;i<100;i++)audio.play('victory');
 check('voice_cap',audio.voices.size<=24);audio.stopAll();
 audio.play('pellet');await new Promise(r=>setTimeout(r,150));check('cleanup',audio.voices.size===0);
 const missing=new AudioManager(()=>null);check('missing_context',!(await missing.unlock()));missing.play('power');
 const broken=new AudioManager(()=>{throw Error('unavailable');});check('factory_failure',!(await broken.unlock()));
 const denied=new AudioManager(()=>({state:'suspended',createGain:()=>({gain:{value:0},connect(){}}),resume:()=>Promise.reject(Error('denied'))}));
 check('resume_failure',!(await denied.unlock()));
 game.stop();game.start();game.cancel();
 const events=[];const play=audio.play.bind(audio);audio.play=n=>events.push(n);
 game.player.x=60;game.player.y=20;game.update();check('power_event',events.at(-1)==='power');
 game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();check('capture_event',events.at(-1)==='capture');
 game.captureLocked=false;game.power=0;game.shield=0;game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();check('life_event',events.at(-1)==='life');
 game.stop();game.start();game.cancel();
 game.player.x=380;game.player.y=180;game.update();check('pellet_event',events.at(-1)==='pellet');
 game.pellets.remaining.clear();game.update();check('clear_event',events.at(-1)==='clear');
 for(let i=0;i<120;i++)game.update();
 game.pellets.remaining.clear();game.update();for(let i=0;i<120;i++)game.update();
 game.pellets.remaining.clear();game.update();check('victory_event',events.at(-1)==='victory');
 game.start();game.cancel();game.lives=1;game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();check('defeat_event',events.at(-1)==='defeat');
 audio.play=play;game.stop();game.start();game.cancel();audio.play('victory');game.togglePause();check('pause_stops',audio.voices.size===0);game.stop();
 return checks;
}"""
TRACE=r"""({level,seed})=>{
 game.stop();game.difficulty.value=level;game.strategy.value=DIFFICULTIES[level].strategy;game.seed.value=seed;game.start();game.cancel();
 let rng=seed;const trace=[];
 for(let i=0;i<5000&&game.active;i++){
  if(i%17===0){rng=(Math.imul(rng,1664525)+1013904223)>>>0;game.player.requested=DIRECTIONS[Math.floor(rng/4294967296*4)];}
  game.update();trace.push([game.state,game.levelManager.index,game.lives,game.score,game.power,game.shield,game.respawn,game.levelWait,game.captureLocked,game.player.x,game.player.y,game.ghost.x,game.ghost.y,game.ghostMode.base,game.ghostMode.remaining,[...game.pellets.remaining.keys()]]);
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
    old.set_content((ROOT/'versions/pacman_v0.12.0.html').read_text(encoding='utf-8'))
    page.set_content((ROOT/'versions/pacman_v0.12.1.html').read_text(encoding='utf-8'))
    assert page.evaluate('game.audio.context===null')
    page.locator('#start').click()
    page.wait_for_function('game.audio.context?.state==="running"')
    page.evaluate('game.cancel()')
    checks=page.evaluate(CHECK)
    regression=[]
    for level in ['easy','normal','hard','expert']:
        for seed in [42,7,2026]:
            args={'level':level,'seed':seed}
            a=old.evaluate(TRACE,args)
            page.evaluate('game.audio.setMuted(true)')
            b=page.evaluate(TRACE,args)
            assert a==b,(level,seed)
            regression.append({**args,'matchedSteps':len(a)})
    page.evaluate('game.audio.setMuted(false)')
    page.locator('#mute').click()
    assert page.locator('#mute').get_attribute('aria-pressed')=='true'
    page.locator('#volume').fill('20')
    assert page.evaluate('game.audio.volume===.2')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    report={'chromium':browser.version,'checks':checks,'regression':regression,'ui':'passed','errors':errors}
    browser.close()
(ROOT/'metrics/audio-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
