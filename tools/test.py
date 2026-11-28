from pathlib import Path
from playwright.sync_api import sync_playwright
import json, os, random
root=Path(__file__).resolve().parents[1]
results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or None, args=['--no-sandbox'])
 for version in ['0.07','0.08']:
  page=browser.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
  page.set_content((root/'versions'/f'pacman_v{version}.html').read_text()); checks={}
  checks['initial_state']=page.evaluate('finalScore===0 && cir_arr.length===105 && circle_1.x===340 && circle_2.x===20')
  checks['start_stop']=page.evaluate('''()=>{start();let a=running&&startBtn.disabled&&!stopBtn.disabled;stopEvent();return a&&!running&&!startBtn.disabled&&stopBtn.disabled&&frameId===null}''')
  checks['all_cells_reachable']=page.evaluate('''()=>{let q=[[340,180]], seen=new Set(['340,180']); for(let i=0;i<q.length;i++){let [x,y]=q[i]; for(let d of directions){let a={x,y,collision:circle_1.collision?.bind(circle_1)}; if(canEnterNextCell(a,d)){let nx=x+40*d.x,ny=y+40*d.y,k=nx+','+ny;if(!seen.has(k)){seen.add(k);q.push([nx,ny])}}}}return seen.size===105}''')
  # Same deterministic inputs for both versions; inspect geometry against legacy walls.
  seq=[]; rng=random.Random(42)
  for i in range(10000): seq.append(rng.randrange(4) if i%17==0 else -1)
  run=page.evaluate('''seq=>{initGame();const walls=[[40,40,40,80],[120,40,200,40],[120,120,40,40],[120,200,40,40],[200,120,40,120],[120,280,200,40],[40,240,40,80],[280,120,120,40],[280,200,120,40],[360,40,200,40],[360,280,200,40],[520,120,40,40],[520,200,40,40],[440,120,40,120],[600,40,40,80],[600,240,40,80],[2,160,80,40],[600,160,78,40]];let safe=true,trace=[];for(let i=0;i<seq.length;i++){if(seq[i]>=0)requested=directions[seq[i]];playTheGame();for(let a of [circle_1,circle_2]){if(a.x<16||a.y<16||a.x>664||a.y>344||walls.some(([x,y,w,h])=> (a.x-Math.max(x,Math.min(a.x,x+w)))**2+(a.y-Math.max(y,Math.min(a.y,y+h)))**2<256))safe=false;}trace.push([circle_1.x,circle_1.y,circle_2.x,circle_2.y,finalScore]);}return {safe,score:finalScore,consistent:finalScore===cir_arr.filter(d=>d.collected).length-1,trace}}''',seq)
  checks['geometry_10000_steps']=run['safe']; checks['score_consistent']=run['consistent']; checks['no_js_errors']=not errors
  if version=='0.07': baseline=run['trace']
  else: checks['identical_trace_to_007']=baseline==run['trace']
  checks['restart_reset']=page.evaluate('''()=>{start();let ok=finalScore===0&&circle_1.x===340&&circle_1.y===180;stopEvent();return ok}''')
  results.append({'version':version,'checks':checks,'steps':10000,'final_score':run['score'],'errors':errors}); page.close()
 version=browser.version;browser.close()
output={'chromium':version,'results':results};(root/'metrics'/'tests.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2));assert all(all(r['checks'].values()) for r in results)
