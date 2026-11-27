"""E3 strict R0/R1 renderer experiment, with isolated browser conditions."""
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import traceback
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright
from e2_run import ROOT, SCRIPT, command, hardware, require, save_json

MAPS = ("Classic", "Labyrinth", "Crossroads")
MODES = ("equivalence", "submit", "readback")
SOURCES = {
    "R0": ("experiments/pacman_v1.0-indexed.html", "f9bd03a36841f8319b207cf76e0f33c20fda6059"),
    "R1": ("experiments/pacman_v1.0-render-cache.html", "fe275d19288289f37dfd16e03ad7790a66202d09"),
}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kind", choices=("local","ci"), default="local")
    p.add_argument("--power-profile", required=True)
    p.add_argument("--background-load", required=True)
    p.add_argument("--notes", default="")
    p.add_argument("--output", type=Path)
    args=p.parse_args()
    require(not (os.environ.get("GITHUB_ACTIONS")=="true" and args.kind=="local"),"CI is not local")
    require(importlib.metadata.version("playwright")=="1.57.0","Use requirements.txt")
    commit=command("git","rev-parse","HEAD")
    require(commit and command("git","status","--porcelain")=="","Clean Git checkout required")
    start=dt.datetime.now(dt.timezone.utc)
    run_id="e3-"+args.kind+"-"+start.strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    output=(args.output or ROOT/"research/ijict/raw-data"/run_id).resolve()
    output.mkdir(parents=True,exist_ok=False)
    workload=SCRIPT/"e3_workload.js"
    report=dict(schema=1,run_id=run_id,kind=args.kind,commit=commit,complete=False,
        started_utc=start.isoformat(),github_run_id=os.environ.get("GITHUB_RUN_ID") if args.kind=="ci" else None,
        environment=dict(platform=platform.platform(),machine=platform.machine(),python=platform.python_version(),
            node=command("node","--version"),playwright=importlib.metadata.version("playwright"),
            headless=True,power_profile=args.power_profile,background_load=args.background_load,notes=args.notes,**hardware()),
        design=dict(maps=list(MAPS),modes=list(MODES),browser_order=["chromium","firefox"],blocks=12,
            orders=[["R0","R1"],["R1","R0"]]*6,warmup_frames=30,frames_per_series=120,
            equivalence_frames_per_map=120,canvas=[680,360],cache_batches=6,cache_builds_per_batch=20,
            expected_series=288,expected_timed_frames=34560,expected_frame_pairs=720,expected_pixel_positions=176256000),
        sources={},scripts={n:hashlib.sha256((SCRIPT/n).read_bytes()).hexdigest() for n in
            ("e3_run.py","e3_workload.js","e3_analyze.py","e2_run.py","e2_analyze.py")},browsers=[],errors=[])
    def checkpoint():
        save_json(output/"report.json",report)
    checkpoint()
    try:
        sources={}
        for v,(relative,expected) in SOURCES.items():
            raw=(ROOT/relative).read_bytes()
            blob=hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
            require(blob==expected,"Frozen source changed: "+v+" (use LF checkout)")
            sources[v]=raw.decode("utf-8").split("<script>",1)[1].split("</script>",1)[0].split("const game = new Game(",1)[0]+"\nreturn {Renderer,Maze,LevelManager,CONFIG,Player,Ghost,PelletStore,createGhostAI,DIRECTIONS,STATES};"
            report["sources"][v]=dict(path=relative,git_blob=blob,sha256=hashlib.sha256(raw).hexdigest())
        checkpoint()
        with sync_playwright() as pw:
            for engine in ("chromium","firefox"):
                b=dict(engine=engine,version=None,complete=False,results=[],frames=[],samples=[],prep=[],counts=[],errors=[])
                report["browsers"].append(b)
                browser=None
                try:
                    browser=getattr(pw,engine).launch(headless=True,**({"args":["--no-sandbox"]} if engine=="chromium" else {}))
                    b["version"]=browser.version
                    probe=browser.new_page()
                    b["user_agent"]=probe.evaluate("navigator.userAgent")
                    b["capabilities"]=probe.evaluate("""()=>{const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');let webgl=null;try{const gl=document.createElement('canvas').getContext('webgl');if(gl){const e=gl.getExtension('WEBGL_debug_renderer_info');webgl={vendor:gl.getParameter(e?e.UNMASKED_VENDOR_WEBGL:gl.VENDOR),renderer:gl.getParameter(e?e.UNMASKED_RENDERER_WEBGL:gl.RENDERER)};}}catch(e){}return {canvas2d:!!ctx,roundRect:typeof ctx?.roundRect==='function',drawImage:typeof ctx?.drawImage==='function',getImageData:typeof ctx?.getImageData==='function',reducedMotion:matchMedia('(prefers-reduced-motion: reduce)').matches,webgl};}""")
                    probe.close()
                    require(all(b["capabilities"][k] for k in ("canvas2d","roundRect","drawImage","getImageData")),"Canvas API unavailable")
                    for name in MAPS:
                        # A new page for each condition, matching the historical harness.
                        # Run equivalence first; do not benchmark a failed visual condition.
                        for mode in MODES:
                            print(f"START {engine} {name} {mode}",flush=True)
                            page=None
                            try:
                                page=browser.new_page()
                                page.on("pageerror",lambda error,b=b:b["errors"].append({"pageerror":str(error)}))
                                page.set_content('<div id="overlay"><b id="overlayTitle"></b><span id="overlayHint"></span></div><div id="lives"></div>')
                                data=page.evaluate(workload.read_text(encoding="utf-8"),dict(sources=sources,mapName=name,mode=mode))
                                for key in ("results","frames","samples","prep","counts"):
                                    b[key].extend(data[key])
                                checkpoint()
                                require(data["error"] is None,str(data["error"]))
                                if mode=="equivalence":
                                    require(len(data["results"])==1 and len(data["frames"])==120,"Incomplete frame comparison")
                                    r=data["results"][0]
                                    require(r["differentPixels"]==r["maxDelta"]==r["statusDifferences"]==0 and r["fallback"] and r["rebuilt"],"Strict RGBA/HUD/cache gate failed")
                                else:
                                    require(len(data["samples"])==24,"Incomplete timings")
                                print(f"PASS {engine} {name} {mode}",flush=True)
                            except Exception as ex:
                                b["errors"].append(dict(map=name,mode=mode,error=str(ex)))
                                checkpoint()
                                if mode=="equivalence":
                                    print(f"FAIL {engine} {name}: no timing for failed equivalence",flush=True)
                                    break
                            finally:
                                if page:
                                    page.close()
                    require(not b["errors"] and len(b["samples"])==144 and len(b["frames"])==360,"Incomplete browser")
                    b["complete"]=True
                except Exception as ex:
                    report["errors"].append(dict(engine=engine,error=str(ex)))
                finally:
                    if browser:
                        browser.close()
                    checkpoint()
        report["totals"]=dict(series=sum(len(b["samples"]) for b in report["browsers"]),
            timed_frames=sum(s["frames"] for b in report["browsers"] for s in b["samples"]),
            frame_pairs=sum(len(b["frames"]) for b in report["browsers"]),
            pixel_positions=sum(f["pixels"] for b in report["browsers"] for f in b["frames"]),
            different_pixels=sum(f["differentPixels"] for b in report["browsers"] for f in b["frames"]),
            hud_differences=sum(not f["hudMatch"] for b in report["browsers"] for f in b["frames"]))
        require(len(report["browsers"])==2 and all(b["complete"] for b in report["browsers"]),"Incomplete browsers")
        require(report["totals"]==dict(series=288,timed_frames=34560,frame_pairs=720,pixel_positions=176256000,different_pixels=0,hud_differences=0),"Unexpected totals")
        report["complete"]=True
    except Exception as ex:
        report["errors"].append(dict(error=str(ex)))
        traceback.print_exc()
    finally:
        report["finished_utc"]=dt.datetime.now(dt.timezone.utc).isoformat()
        checkpoint()
    print("E3_REPORT "+json.dumps(dict(run_id=run_id,kind=args.kind,complete=report["complete"],
        browsers=[{k:b[k] for k in ("engine","version","complete","errors")} for b in report["browsers"]],
        totals=report.get("totals"),errors=report["errors"]),ensure_ascii=False),flush=True)
    print("Output: "+str(output),flush=True)
    if not report["complete"]:
        return 1
    return subprocess.call([sys.executable,str(SCRIPT/"e3_analyze.py"),str(output)],cwd=ROOT)

if __name__=="__main__":
    raise SystemExit(main())
