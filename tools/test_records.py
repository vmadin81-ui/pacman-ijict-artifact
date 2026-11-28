"""Real browser storage, failure handling, record lifecycle and regression."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
CHECK=r"""()=>{
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
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None,args=['--no-sandbox'])
    old=browser.new_page()
    page=browser.new_page(viewport={'width':375,'height':750})
    errors=[]
    for tab in (old,page):
        tab.on('pageerror',lambda e:errors.append(str(e)))
    html=(ROOT/'versions/pacman_v0.12.2.html').read_text(encoding='utf-8')
    page.route('https://pacman.test/',lambda route:route.fulfill(content_type='text/html',body=html))
    page.goto('https://pacman.test/')
    page.locator('#playerName').fill('<img src=x onerror=alert(1)>')
    page.locator('#playerName').fill('Researcher')
    page.locator('#difficulty').select_option('hard')
    page.locator('#strategy').select_option('A*')
    page.locator('#seed').fill('777')
    page.locator('#volume').fill('20')
    page.locator('#mute').click()
    page.reload()
    assert page.evaluate('game.playerName.value==="Researcher" && game.difficulty.value==="hard" && game.strategy.value==="A*" && game.seed.value==="777" && game.audio.muted && game.audio.volume===.2')
    checks=page.evaluate(CHECK)
    page.reload()
    assert page.evaluate('game.store.records.length===2')
    assert page.locator('#recordsBody tr').count()==2
    page.evaluate("""()=>{game.store.add({name:'<img src=x>',difficulty:'hard',strategy:'A*',seed:1,score:999,level:1,ticks:1,result:'GAME_OVER',date:new Date().toISOString()});game.renderRecords()}""")
    assert page.locator('#recordsBody img').count()==0
    assert '<img src=x>' in page.locator('#recordsBody').inner_text()
    page.locator('#strategy').select_option('BFS')
    assert 'Пока нет' in page.locator('#recordsBody').inner_text()
    old.set_content((ROOT/'versions/pacman_v0.12.1.html').read_text(encoding='utf-8'))
    regression=[]
    for level in ['easy','normal','hard','expert']:
        for seed in [42,7,2026]:
            args={'level':level,'seed':seed}
            a=old.evaluate(TRACE,args); b=page.evaluate(TRACE,args)
            assert a==b,(level,seed)
            regression.append({**args,'matchedSteps':len(a)})
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert not errors,errors
    report={'chromium':browser.version,'checks':checks,'regression':regression,'persistence':'passed','ui':'passed','errors':errors}
    browser.close()
(ROOT/'metrics/records-tests.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,indent=2))
