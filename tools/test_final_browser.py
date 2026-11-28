"""Final release browser acceptance: actual v1.0 source, independent browser contexts."""
import json, os, hashlib
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
AUDIO=r"""async ()=>{
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
RECORDS=r"""()=>{
 const checks={};
 const check=(n,v)=>{checks[n]=Boolean(v);if(!v)throw Error(n);};
 const data=new Map(),store=new LocalStore(()=>({getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)}));
 const base={name:'PLAYER',difficulty:'normal',strategy:'Greedy',seed:42,score:100,level:1,ticks:60,result:'GAME_OVER',date:'2026-11-25T00:00:00Z'};
 for(let i=0;i<15;i++)store.add({...base,score:i*10});
 check('top10',store.records.length===10&&store.records[0].score===140&&store.records[9].score===50);
 store.add({...base,strategy:'BFS'});check('strategy_partition',store.top('normal','BFS').length===1);
 store.add({...base,difficulty:'hard'});check('difficulty_partition',store.top('hard','Greedy').length===1);
 const tie=LocalStore.normalize([{...base,ticks:90},{...base,ticks:30},{...base,level:3,result:'VICTORY'}]);
 check('tie_order',tie[0].result==='VICTORY'&&tie[1].ticks===30);
 check('invalid_records',LocalStore.normalize([null,{...base,score:-1},{...base,level:4},{...base,result:'PLAYING'},{...base,result:'VICTORY'},{...base,date:'bad'}]).length===0);
 store.setSettings({name:'  ',difficulty:'wrong',strategy:'wrong',seed:1.5,volume:2,muted:'yes'});
 check('settings_validation',store.settings.name==='PLAYER'&&store.settings.difficulty==='normal'&&store.settings.strategy==='Greedy'&&store.settings.seed===42&&store.settings.volume===1&&!store.settings.muted);
 const broken=new LocalStore(()=>({getItem:()=>'{bad',setItem(){}}));check('corrupt_json',!broken.available&&broken.records.length===0);
 const denied=new LocalStore(()=>{throw Error('denied');});denied.add(base);check('read_failure',!denied.available&&denied.records.length===1);
 const quota=new LocalStore(()=>({getItem:()=>null,setItem(){throw Error('quota');}}));quota.add(base);check('write_failure',!quota.available&&quota.records.length===1);
 game.stop();game.start();game.cancel();game.update();const ticks=game.sessionTicks;game.togglePause();game.update();
 check('pause_time',game.sessionTicks===ticks);game.togglePause();game.cancel();game.stop();check('stop_no_record',game.store.records.length===0);
 game.start();game.cancel();game.score=123;game.lives=1;game.ghost.x=game.player.x;game.ghost.y=game.player.y;game.resolveContact();
 check('defeat_record',game.store.records.length===1&&game.store.records[0].score===123&&game.store.records[0].result==='GAME_OVER');
 game.finishRecord();game.update();check('no_duplicate',game.store.records.length===1);
 game.start();game.cancel();for(let i=0;i<3;i++){game.pellets.remaining.clear();game.update();if(i<2){check('no_intermediate_'+i,game.store.records.length===1);for(let j=0;j<120;j++)game.update();}}
 check('victory_record',game.store.records.length===2&&game.store.records.some(r=>r.result==='VICTORY'&&r.level===3));
 check('campaign_ticks',game.store.records.find(r=>r.result==='VICTORY').ticks===243);
 game.stop();return checks;
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
EXTRA=r"""async ()=>{
 const checks={};
 const check=(n,v)=>{checks[n]=Boolean(v);if(!v)throw Error(n);};
 game.stop();game.seed.value='1.5';game.strategy.value='Random';game.start();game.cancel();
 check('canonical_seed',game.seed.value==='42'&&game.sessionSettings.seed===42);
 game.stop();game.seed.value='';game.start();game.cancel();check('blank_seed',game.sessionSettings.seed===42);
 game.stop();
 const original=game.renderer.staticLayer;check('native_cache',!!original);
 game.start();game.cancel();game.pellets.remaining.clear();game.update();
 for(let i=0;i<120;i++)game.update();
 check('cache_switch',game.levelManager.index===1&&game.renderer.staticLayer!==original&&!!game.renderer.staticLayer);
 game.render();const ctx=game.renderer.context;
 const a=ctx.getImageData(0,0,680,360).data;
 game.renderer.staticLayer=null;game.renderer.phase--;game.render();
 const b=ctx.getImageData(0,0,680,360).data;
 check('cache_fallback',a.every((v,i)=>v===b[i]));
 game.stop();
 let release,calls=0;
 const context={state:'suspended',createGain:()=>({gain:{},connect(){}}),resume(){calls++;return new Promise(r=>release=()=>{this.state='running';r();});}};
 const manager=new AudioManager(()=>context);const p=manager.unlock(),q=manager.unlock();release();
 check('concurrent_audio',(await Promise.all([p,q])).every(v=>v===true)&&calls===1);
 check('malformed_storage',LocalStore.settings({difficulty:{toString:null}}).difficulty==='normal');
 return checks;
}"""
path=ROOT/'versions/pacman_v1.0.html'
html=path.read_text(encoding='utf-8')
report={'source':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'commit':os.environ.get('GITHUB_SHA'),'checks':{},'regression':[],'errors':[],'complete':False}
def save():
    (ROOT/'metrics/final-browser-v1.0.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    report['chromium']=browser.version
    def fresh():
        page=browser.new_page(viewport={'width':375,'height':750})
        page.on('pageerror',lambda e:report['errors'].append(str(e)))
        page.route('https://pacman.test/',lambda route:route.fulfill(content_type='text/html',body=html))
        page.goto('https://pacman.test/')
        return page
    page=fresh()
    assert page.evaluate('game.audio.context===null')
    page.locator('#start').click()
    page.wait_for_function('game.audio.context?.state==="running"')
    page.evaluate('game.cancel()')
    report['checks'].update(page.evaluate(AUDIO))
    page.close();save();print('AUDIO PASS',flush=True)
    page=fresh()
    page.locator('#playerName').fill('Researcher')
    page.locator('#difficulty').select_option('hard')
    page.locator('#strategy').select_option('A*')
    page.locator('#seed').fill('777')
    page.locator('#volume').fill('20')
    page.locator('#mute').click()
    page.reload()
    assert page.evaluate('game.playerName.value==="Researcher" && game.difficulty.value==="hard" && game.strategy.value==="A*" && game.seed.value==="777" && game.audio.muted && game.audio.volume===.2')
    report['checks']['persistence_reload']=True
    report['checks'].update(page.evaluate(RECORDS))
    page.reload()
    assert page.evaluate('game.store.records.length===2')
    assert page.locator('#recordsBody tr').count()==2
    page.evaluate("""()=>{game.store.add({name:'<img src=x>',difficulty:'hard',strategy:'A*',seed:1,score:999,level:1,ticks:1,result:'GAME_OVER',date:new Date().toISOString()});game.renderRecords()}""")
    assert page.locator('#recordsBody img').count()==0
    assert '<img src=x>' in page.locator('#recordsBody').inner_text()
    report['checks']['safe_record_text']=True
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    report['checks']['mobile_width']=True
    page.close();save();print('RECORDS PASS',flush=True)
    page=fresh()
    report['checks'].update(page.evaluate(EXTRA))
    page.locator('#start').click();page.locator('#pause').click()
    assert page.locator('#overlay').is_visible()
    page.locator('#pause').click();assert not page.locator('#overlay').is_visible()
    page.locator('#stop').click()
    report['checks']['ui_controls']=True
    save();print('EXTRA PASS',flush=True)
    old=browser.new_page()
    old.on('pageerror',lambda e:report['errors'].append(str(e)))
    old.set_content((ROOT/'versions/pacman_v0.12.2.html').read_text(encoding='utf-8'))
    page.evaluate('game.audio.setMuted(true)')
    for level in ('easy','normal','hard','expert'):
        for seed in (42,7,2026):
            args={'level':level,'seed':seed}
            a=old.evaluate(TRACE,args);b=page.evaluate(TRACE,args)
            assert a==b,args
            report['regression'].append({**args,'matchedSteps':len(a)})
        save();print('TRACE PASS '+level,flush=True)
    assert not report['errors'],report['errors']
    browser.close()
report['complete']=True
save()
print(json.dumps(report,indent=2),flush=True)
