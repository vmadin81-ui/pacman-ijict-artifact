"""Validate archived E3 evidence without rerunning the browser or changing raw files."""
import hashlib
import json
import math
import shutil
import statistics as st
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "research/ijict/raw-data/e3-local-20261125T162100Z-0cb3b422"
r = json.loads((RUN/"report.json").read_text(encoding="utf-8"))
a = json.loads((RUN/"analysis.json").read_text(encoding="utf-8"))
def require(x,msg):
    if not x:
        raise ValueError(msg)
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
for key,s in r["sources"].items():
    require(sha(ROOT/s["path"])==s["sha256"],"Source SHA-256 "+key)
for name,digest in r["scripts"].items():
    require(sha(ROOT/"research/ijict/scripts"/name)==digest,"Script SHA-256 "+name)
require(r["complete"] and not r["errors"],"Report completeness")
require(r["commit"]=="c6ebdb877aab14a7144abb86f4ad2bbf5399abb9","Measurement commit")
require(r["environment"]["background_load"]=="еобязательные приложения закрыты, стандартные системные процессы активны","Original metadata retained")
require([b["engine"] for b in r["browsers"]]==["chromium","firefox"],"Browser sequence")
checks=0
def equal(x,y,name):
    global checks
    require(math.isclose(x,y,rel_tol=1e-9,abs_tol=1e-9),name)
    checks+=1
def match(rows,**keys):
    result=[x for x in rows if all(x[k]==v for k,v in keys.items())]
    require(len(result)==1,"Row uniqueness "+str(keys))
    return result[0]
def stats(x,archive):
    q1,_,q3=st.quantiles(x,n=4,method="inclusive")
    for k,v in dict(n=len(x),median=st.median(x),q1=q1,q3=q3,iqr=q3-q1,min=min(x),max=max(x)).items():
        equal(archive[k],v,k)
maps=("Classic","Labyrinth","Crossroads")
scenarios=("normal","power","shield","paused","reduced","ready","clear","victory","defeat","respawn")
orders=[["R0","R1"],["R1","R0"]]*6
series=timed=frames=pixels=0
losses=[]
for b in r["browsers"]:
    e=b["engine"]
    require(b["complete"] and not b["errors"],e)
    require((len(b["samples"]),len(b["frames"]),len(b["prep"]),len(b["counts"]),len(b["results"]))==(144,360,18,6,3),"Browser coverage")
    for m in maps:
        g=dict(engine=e,map=m)
        f=[x for x in b["frames"] if x["map"]==m]
        require([(x["scenario"],x["frame"]) for x in f]==[(s,i) for s in scenarios for i in range(1,13)],"Frame coverage")
        for x in f:
            require(x["pixels"]==244800 and x["differentPixels"]==x["maxDelta"]==0 and x["hudMatch"] and x["statusA"]==x["statusB"] and x["firstDifference"] is None,"RGBA/HUD diagnostics")
            frames+=1
            pixels+=x["pixels"]
        v=match(b["results"],map=m,version="R1")
        require(v["frames"]==120 and v["differentPixels"]==v["maxDelta"]==v["statusDifferences"]==0 and v["rebuilt"] and v["fallback"],"Visual gate")
        p=[x for x in b["prep"] if x["map"]==m]
        require([x["repeat"] for x in p]==list(range(1,7)) and all(x["builds"]==20 and math.isfinite(x["ms"]) and x["ms"]>0 for x in p),"Prep coverage")
        stats([x["ms"]*1000/x["builds"] for x in p],match(a["preparation"],**g))
        for version in ("R0","R1"):
            c=match(b["counts"],map=m,version=version)
            equal(c["total"],sum(c["calls"].values()),"Canvas total")
            require(c["calls"]==match(a["canvas_counts"],**g,version=version)["calls"],"Canvas calls")
        for mode in ("submit","readback"):
            group=dict(**g,mode=mode)
            ss=[x for x in b["samples"] if x["map"]==m and x["mode"]==mode]
            require(len(ss)==24,"Series coverage")
            vals={"R0":[],"R1":[]}
            for i,order in enumerate(orders,1):
                block=[x for x in ss if x["repeat"]==i]
                require([x["version"] for x in block]==order and [x["position"] for x in block]==[1,2],"Block order")
                for x in block:
                    require(x["order"]==order and x["frames"]==120 and math.isfinite(x["ms"]) and x["ms"]>0,"Sample")
                    vals[x["version"]].append(x["ms"]*1000/120)
                    series+=1
                    timed+=x["frames"]
            for v,x in vals.items():
                stats(x,match(a["descriptive"],**group,variant=v))
            ratios=[]
            for i,(x,y) in enumerate(zip(vals["R0"],vals["R1"]),1):
                z=x/y
                ratios.append(z)
                row=match(a["pairs"],**group,repeat=i)
                for k,v in dict(baseline_time=x,candidate_time=y,ratio=z).items():
                    equal(row[k],v,k)
                if z<1-1e-10:
                    losses.append((e,m,mode,i))
            ratio=st.median(vals["R0"])/st.median(vals["R1"])
            win=sum(z>1+1e-10 for z in ratios)
            loss=sum(z<1-1e-10 for z in ratios)
            # Independent bootstrap implementation using statistics.median and inclusive quantiles.
            state=20261125
            boot=[]
            for _ in range(20000):
                sample=[]
                for _ in range(12):
                    state=(1664525*state+1013904223)%4294967296
                    sample.append(ratios[state*12//4294967296])
                boot.append(st.median(sample))
            quant=st.quantiles(boot,n=40,method="inclusive")
            for k,v in dict(n=12,ratio_of_medians=ratio,reduction_pct=100*(1-1/ratio),paired_median_ratio=st.median(ratios),paired_ci_low=quant[0],paired_ci_high=quant[-1],wins=win,ties=12-win-loss,losses=loss).items():
                equal(match(a["contrasts"],**group)[k],v,k)
require((series,timed,frames,pixels)==(288,34560,720,176256000),"Totals")
require(losses==[("chromium","Classic","submit",2),("chromium","Labyrinth","submit",2),("chromium","Crossroads","submit",2),("firefox","Crossroads","readback",11)],"Loss positions")
require(checks==762,"Numeric check count")
# Regenerate original analyzer outputs in a temporary copy; never write raw archive.
with tempfile.TemporaryDirectory() as tmp:
    copy=Path(tmp)/"run"
    shutil.copytree(RUN,copy)
    subprocess.run([sys.executable,str(ROOT/"research/ijict/scripts/e3_analyze.py"),str(copy)],check=True,stdout=subprocess.DEVNULL)
    require(json.loads((copy/"analysis.json").read_text(encoding="utf-8"))==a,"Regenerated JSON")
    for n in ("descriptive.csv","contrasts.csv","pairs.csv","preparation.csv","visual.csv","summary.md"):
        require((copy/n).read_text(encoding="utf-8")== (RUN/n).read_text(encoding="utf-8"),"Regenerated "+n)  # Normalize only platform newline conventions.
# XML parse all SVG originals, verify monochrome palette.
for n in ("e3-local-forest.svg","e3-cache-break-even.svg","e3-paired-blocks.svg"):
    svg=ET.parse(ROOT/"research/ijict/figures"/n).getroot()
    for node in svg.iter():
        for k in ("fill","stroke"):
            require(node.attrib.get(k,"none") in ("none","white","#111"),"Palette")
print("E3_ARCHIVE_AUDIT "+json.dumps(dict(run_id=r["run_id"],series=series,frames=timed,diagnostic_pairs=frames,pixel_positions=pixels,numeric_checks=checks,losses=losses,source_hashes=2,script_hashes=5,recomputed_json=True,recomputed_csv=5,recomputed_summary=True,svg_xml=3,complete=True)))
