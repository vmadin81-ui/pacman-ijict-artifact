"""Compare v0.08 and v0.08.1 in Chromium using deterministic input and UI checks."""
from pathlib import Path
import hashlib
import json
import os
import random
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OLD = '''({reset:()=>initGame(), step:()=>playTheGame(), input:i=>requested=directions[i],
    player:()=>circle_1, ghost:()=>circle_2, score:()=>finalScore,
    remaining:()=>cir_arr.filter(d=>!d.collected).length,
    walk:(r,c)=>isWalkable(r,c), running:()=>running, frame:()=>frameId})'''
NEW = '''({reset:()=>game.reset(), step:()=>game.update(), input:i=>game.player.requested=DIRECTIONS[i],
    player:()=>game.player, ghost:()=>game.ghost, score:()=>game.score,
    remaining:()=>game.pellets.remaining.size,
    walk:(r,c)=>game.maze.isWalkable(r,c), running:()=>game.running, frame:()=>game.frameId})'''
RUN = '''({seq,adapter})=>{const a=eval(adapter); a.reset();let trace=[],safe=true,consistent=true;
 const walls=[];for(let r=0;r<9;r++)for(let c=0;c<17;c++)if(!a.walk(r,c))walls.push([c*40,r*40]);
 for(const i of seq){if(i>=0)a.input(i);a.step();const p=a.player(),g=a.ghost();
 for(const e of [p,g]){if(e.x<16||e.y<16||e.x>664||e.y>344||walls.some(([x,y])=>
 (e.x-Math.max(x,Math.min(e.x,x+40)))**2+(e.y-Math.max(y,Math.min(e.y,y+40)))**2<256))safe=false;}
 if(a.score()+a.remaining()!==104)consistent=false;
 trace.push([p.x,p.y,g.x,g.y,a.score()]);}return {trace,safe,consistent,score:a.score()};}'''

def sequence(seed):
    rng = random.Random(seed)
    return [rng.randrange(4) if i % 17 == 0 else -1 for i in range(10000)]

results = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None, args=['--no-sandbox'])
    traces = {}
    for version, adapter in [('0.08', OLD), ('0.08.1', NEW)]:
        page = browser.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content((ROOT / 'versions' / f'pacman_v{version}.html').read_text())
        page.evaluate('adapter=>window.testAdapter=eval(adapter)', adapter)
        checks = {}
        checks['initial_state'] = page.evaluate('testAdapter.score()===0 && testAdapter.remaining()===104 && testAdapter.player().x===340 && testAdapter.player().y===180 && testAdapter.ghost().x===20 && testAdapter.ghost().y===20')
        checks['all_cells_reachable'] = page.evaluate('''()=>{const a=testAdapter,q=[[4,8]],seen=new Set(['4,8']);for(let i=0;i<q.length;i++){const [r,c]=q[i];for(const [dr,dc] of [[0,1],[1,0],[0,-1],[-1,0]]){const nr=r+dr,nc=c+dc,k=nr+','+nc;if(a.walk(nr,nc)&&!seen.has(k)){seen.add(k);q.push([nr,nc]);}}}return seen.size===105}''')
        runs = []
        for seed in (42, 7, 2026):
            run = page.evaluate(RUN, {'seq': sequence(seed), 'adapter': adapter})
            checks[f'geometry_seed_{seed}'] = run['safe']
            checks[f'score_seed_{seed}'] = run['consistent']
            if version == '0.08':
                traces[seed] = run['trace']
            else:
                checks[f'identical_trace_seed_{seed}'] = traces[seed] == run['trace']
            runs.append({'seed': seed, 'steps': 10000, 'score': run['score'], 'trace_sha256': hashlib.sha256(json.dumps(run['trace'], separators=(',', ':')).encode()).hexdigest()})
        page.locator('#start').click()
        checks['start_ui'] = page.evaluate('testAdapter.running() && testAdapter.frame()!==null') and page.locator('#start').is_disabled() and page.locator('#stop').is_enabled()
        page.keyboard.press('ArrowRight')
        page.wait_for_function('testAdapter.player().x>340', timeout=2000)
        checks['keyboard_ui'] = True
        page.locator('#stop').click()
        before = page.evaluate('[testAdapter.player().x,testAdapter.player().y,testAdapter.ghost().x,testAdapter.ghost().y,testAdapter.score()]')
        page.wait_for_timeout(150)
        checks['stop_ui'] = before == page.evaluate('[testAdapter.player().x,testAdapter.player().y,testAdapter.ghost().x,testAdapter.ghost().y,testAdapter.score()]') and page.evaluate('!testAdapter.running() && testAdapter.frame()===null') and page.locator('#stop').is_disabled()
        page.locator('#start').click()
        checks['restart_reset'] = page.evaluate('testAdapter.player().x===340 && testAdapter.player().y===180 && testAdapter.score()===0 && testAdapter.remaining()===104')
        page.locator('#stop').click()
        checks['no_js_errors'] = not errors
        results.append({'version': version, 'checks': checks, 'runs': runs, 'errors': errors})
        page.close()
    chromium = browser.version
    browser.close()
output = {'chromium': chromium, 'results': results}
(ROOT / 'metrics' / 'refactor-tests.json').write_text(json.dumps(output, indent=2)+'\n')
print(json.dumps(output, indent=2))
assert all(all(r['checks'].values()) for r in results)
