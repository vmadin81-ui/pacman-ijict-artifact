"""E3 validation and E1-compatible paired statistics; no pooling."""
import argparse
import json
import math
from pathlib import Path
from e2_analyze import q, stats, bootstrap, csv_file, require

MAPS=("Classic","Labyrinth","Crossroads")
SCENARIOS=("normal","power","shield","paused","reduced","ready","clear","victory","defeat","respawn")
ORDERS=[["R0","R1"],["R1","R0"]]*6

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    d=p.parse_args().directory
    r=json.loads((d/"report.json").read_text(encoding="utf-8"))
    require(r["complete"] and not r["errors"],"Incomplete run; retain raw diagnostics")
    require(r["design"]["orders"]==ORDERS,"Changed order")
    require([b["engine"] for b in r["browsers"]]==["chromium","firefox"],"Browser order")
    require(r["totals"]==dict(series=288,timed_frames=34560,frame_pairs=720,pixel_positions=176256000,different_pixels=0,hud_differences=0),"Totals")
    descriptive,contrasts,pairs,prep,visual,counts=[],[],[],[],[],[]
    for b in r["browsers"]:
        engine=b["engine"]
        require(b["complete"] and not b["errors"] and len(b["samples"])==144 and len(b["frames"])==360 and len(b["results"])==3 and len(b["counts"])==6 and len(b["prep"])==18,"Browser completeness")
        for name in MAPS:
            vs=[v for v in b["results"] if v["map"]==name]
            require(len(vs)==1,"Visual result")
            v=vs[0]
            require(v["frames"]==120 and v["version"]=="R1" and v["maxDelta"]==v["differentPixels"]==v["statusDifferences"]==0 and v["fallback"] and v["rebuilt"],"Visual gate")
            fs=[f for f in b["frames"] if f["map"]==name]
            require([(f["scenario"],f["frame"]) for f in fs]==[(s,i) for s in SCENARIOS for i in range(1,13)],"Scenario coverage")
            require(all(f["pixels"]==244800 and f["differentPixels"]==f["maxDelta"]==0 and f["hudMatch"] and f["statusA"]==f["statusB"] and f["firstDifference"] is None for f in fs),"Frame diagnostic")
            visual.append(dict(engine=engine,map=name,frame_pairs=120,pixel_positions=29376000,different_pixels=0,max_delta=0,hud_differences=0,cache_rebuilt=True,fallback=True))
            ps=[x for x in b["prep"] if x["map"]==name]
            require([x["repeat"] for x in ps]==list(range(1,7)) and all(x["builds"]==20 and math.isfinite(x["ms"]) and x["ms"]>0 for x in ps),"Prep")
            prep.append(dict(engine=engine,map=name,unit="us/build",**stats([x["ms"]*1000/x["builds"] for x in ps])))
            cs=[x for x in b["counts"] if x["map"]==name]
            require([x["version"] for x in cs]==["R0","R1"] and all(x["total"]==sum(x["calls"].values()) for x in cs),"Canvas counts")
            counts.extend(dict(engine=engine,map=name,version=x["version"],total=x["total"],calls=x["calls"]) for x in cs)
            for mode in ("submit","readback"):
                ss=[s for s in b["samples"] if s["map"]==name and s["mode"]==mode]
                require(len(ss)==24,"Series count")
                values={"R0":[],"R1":[]}
                group=dict(engine=engine,map=name,mode=mode,unit="us/frame")
                for i,order in enumerate(ORDERS,1):
                    batch=[s for s in ss if s["repeat"]==i]
                    require([s["version"] for s in batch]==order and [s["position"] for s in batch]==[1,2],"Order")
                    for s in batch:
                        require(s["order"]==order and s["frames"]==120 and math.isfinite(s["ms"]) and s["ms"]>0,"Series")
                        values[s["version"]].append(s["ms"]*1000/s["frames"])
                for variant,vals in values.items():
                    descriptive.append(dict(**group,variant=variant,**stats(vals)))
                a,c=values["R0"],values["R1"]
                ratios=[x/y for x,y in zip(a,c)]
                ratio=q(a,.5)/q(c,.5)
                lo,hi=bootstrap(ratios)
                wins=sum(x>1+1e-10 for x in ratios); losses=sum(x<1-1e-10 for x in ratios)
                contrasts.append(dict(**group,baseline="R0",candidate="R1",n=12,ratio_of_medians=ratio,reduction_pct=100*(1-1/ratio),paired_median_ratio=q(ratios,.5),paired_ci_low=lo,paired_ci_high=hi,wins=wins,ties=12-wins-losses,losses=losses))
                pairs.extend(dict(**group,repeat=i,baseline_time=x,candidate_time=y,ratio=z) for i,(x,y,z) in enumerate(zip(a,c,ratios),1))
    require(len(descriptive)==24 and len(contrasts)==12 and len(pairs)==144 and len(prep)==6 and len(visual)==6,"Analysis counts")
    a=dict(run_id=r["run_id"],kind=r["kind"],commit=r["commit"],environment=r["environment"],
        versions={b["engine"]:b["version"] for b in r["browsers"]},sources=r["sources"],totals=r["totals"],
        method=dict(quantiles="type 7",bootstrap_draws=20000,seed=20261125,interval="conditional exploratory percentile 95%",pooling=False,outliers="retained"),
        descriptive=descriptive,contrasts=contrasts,pairs=pairs,preparation=prep,visual=visual,canvas_counts=counts)
    (d/"analysis.json").write_text(json.dumps(a,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    for name,rows in (("descriptive",descriptive),("contrasts",contrasts),("pairs",pairs),("preparation",prep),("visual",visual)):
        csv_file(d/(name+".csv"),rows)
    summary=["# E3 — "+r["kind"]+" "+r["run_id"],"","Submit and Readback separate; not FPS. Conditional exploratory intervals.","",
        "| Browser | Map | Mode | R0/R1 | Reduction % | Paired median | 95% interval | W/T/L |","|---|---|---|---:|---:|---:|---|---|"]
    for x in contrasts:
        summary.append(f'| {x["engine"]} | {x["map"]} | {x["mode"]} | {x["ratio_of_medians"]:.3f} | {x["reduction_pct"]:.2f} | {x["paired_median_ratio"]:.3f} | {x["paired_ci_low"]:.3f}–{x["paired_ci_high"]:.3f} | {x["wins"]}/{x["ties"]}/{x["losses"]} |')
    (d/"summary.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    print("E3_ANALYSIS "+json.dumps({k:a[k] for k in ("run_id","kind","commit","environment","versions","sources","totals","contrasts","preparation","visual","canvas_counts")},ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
