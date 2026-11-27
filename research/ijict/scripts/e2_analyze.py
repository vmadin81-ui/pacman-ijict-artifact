"""Validate a complete E2 run and calculate E1-compatible paired statistics."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

MAPS = {"Classic":11025,"Labyrinth":10201,"Crossroads":12769}
ORDERS = [list(x) for x in ("ABC","BCA","CAB","ACB","CBA","BAC")]*2


def require(ok, message):
    if not ok:
        raise ValueError(message)


def q(values, p):
    a=sorted(values)
    x=(len(a)-1)*p
    j=int(x)
    return a[j]+(a[min(j+1,len(a)-1)]-a[j])*(x-j)


def stats(a):
    lo,hi=q(a,.25),q(a,.75)
    return dict(n=len(a),median=q(a,.5),q1=lo,q3=hi,iqr=hi-lo,min=min(a),max=max(a))


def bootstrap(a):
    state=20261125
    values=[]
    for _ in range(20000):
        sample=[]
        for _ in a:
            state=(state*1664525+1013904223)&0xffffffff
            sample.append(a[(state*len(a))>>32])
        values.append(q(sample,.5))
    return q(values,.025),q(values,.975)


def csv_file(path, rows):
    with path.open("w",encoding="utf-8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    d=parser.parse_args().directory
    report=json.loads((d/"report.json").read_text(encoding="utf-8"))
    require(report["complete"] and not report["errors"],"Incomplete run; keep diagnostics")
    require(report["design"]["orders"]==ORDERS,"Changed order")
    require([b["engine"] for b in report["browsers"]]==["chromium","firefox"],"Browser order")
    require(report["totals"]=={"series":432,"timed_queries":4895280,
        "verified_ordered_pairs_by_algorithm":135980,"pairwise_variant_comparisons":271960},"Unexpected totals")
    descriptive,contrasts,pairs,preparation,validation=[],[],[],[],[]
    cross_browser={}
    for b in report["browsers"]:
        engine=b["engine"]
        require(b["complete"] and not b["errors"] and len(b["results"])==6 and len(b["samples"])==216,engine)
        require(len(b["preparation"])==18 and len(b["warmup"])==18,"Preparation/warmup count")
        for name,count in MAPS.items():
            prep=[x for x in b["preparation"] if x["map"]==name]
            require([x["repeat"] for x in prep]==list(range(1,7)) and
                all(x["iterations"]==1000 and math.isfinite(x["ms"]) and x["ms"]>0 for x in prep),"Prep")
            preparation.append(dict(engine=engine,map=name,unit="us/graph",
                **stats([x["ms"]*1000/x["iterations"] for x in prep])))
            for algorithm in ("BFS","A*"):
                group=dict(engine=engine,map=name,algorithm=algorithm,unit="ms/batch")
                results=[r for r in b["results"] if r["map"]==name and r["algorithm"]==algorithm]
                require(len(results)==1,"Duplicate or missing verification")
                r=results[0]
                require(r["matched"]==count and r["pairs"]==count and r["mismatched"]==0 and r["evaluated"]==3*count,"Verification count")
                raw=(d/r["route_file"]).read_bytes()
                require(hashlib.sha256(raw).hexdigest()==r["route_sha256"],"Route checksum")
                data=json.loads(gzip.decompress(raw))
                records=data["records"]
                require(data["map"]==name and data["algorithm"]==algorithm and not data["failures"] and len(records)==count,"Route records")
                require(len({(x["start"],x["target"]) for x in records})==count,"Duplicate route")
                require(all(x["length"]==x["distance"]==len(x["path"]) and set(x["path"])<=set("RDLU") and x["expanded"]>=1 for x in records),"Route lengths")
                require(sum(x["length"] for x in records)==r["checksum"] and sum(x["expanded"] for x in records)==r["expanded"],"Route sums")
                cross_browser.setdefault((name,algorithm),[]).append(hashlib.sha256(gzip.decompress(raw)).hexdigest())
                values={v:[] for v in "ABC"}
                samples=[s for s in b["samples"] if s["map"]==name and s["algorithm"]==algorithm]
                warmup=[s for s in b["warmup"] if s["map"]==name and s["algorithm"]==algorithm]
                require([s["version"] for s in warmup]==list("ABC"),"Warmup order")
                require(len(samples)==36,"Sample count")
                def valid(s):
                    return s["queries"]==count and s["checksum"]==r["checksum"] and s["expanded"]==r["expanded"] and math.isfinite(s["ms"]) and s["ms"]>0
                require(all(valid(s) for s in warmup),"Warmup checksum")
                for repeat,order in enumerate(ORDERS,1):
                    batch=[s for s in samples if s["repeat"]==repeat]
                    require([s["version"] for s in batch]==order and [s["position"] for s in batch]==[1,2,3],"Block order")
                    for s in batch:
                        require(s["order"]==order and valid(s),"Sample checksum")
                        values[s["version"]].append(s["ms"])
                for v,a in values.items():
                    st=stats(a)
                    descriptive.append(dict(**group,variant=v,**st,median_us_per_query=st["median"]*1000/count))
                for base,candidate in (("A","B"),("A","C"),("B","C")):
                    a,c=values[base],values[candidate]
                    ratios=[x/y for x,y in zip(a,c)]
                    ratio=q(a,.5)/q(c,.5)
                    lo,hi=bootstrap(ratios)
                    wins=sum(v>1+1e-10 for v in ratios)
                    losses=sum(v<1-1e-10 for v in ratios)
                    contrasts.append(dict(**group,baseline=base,candidate=candidate,n=12,
                        ratio_of_medians=ratio,reduction_pct=100*(1-1/ratio),
                        paired_median_ratio=q(ratios,.5),paired_ci_low=lo,paired_ci_high=hi,
                        wins=wins,ties=12-wins-losses,losses=losses))
                    for i,(x,y,z) in enumerate(zip(a,c,ratios),1):
                        pairs.append(dict(**group,baseline=base,candidate=candidate,repeat=i,
                            baseline_time=x,candidate_time=y,ratio=z))
                validation.append(dict(**group,series=len(samples),routes=len(records),matched=r["matched"]))
    require(len(descriptive)==36 and len(contrasts)==36 and len(pairs)==432 and len(validation)==12,"Analysis totals")
    cross=[dict(map=k[0],algorithm=k[1],same_route_payload=len(v)==2 and v[0]==v[1]) for k,v in cross_browser.items()]
    analysis=dict(run_id=report["run_id"],kind=report["kind"],commit=report["commit"],
        method=dict(quantiles="type 7",bootstrap_draws=20000,seed=20261125,
                    interval="exploratory conditional percentile 95%",pooling=False,outliers="retained"),
        environment=report["environment"],versions={b["engine"]:b["version"] for b in report["browsers"]},
        sources=report["sources"],totals=report["totals"],descriptive=descriptive,
        contrasts=contrasts,pairs=pairs,preparation=preparation,validation=validation,cross_browser_routes=cross)
    (d/"analysis.json").write_text(json.dumps(analysis,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    for name,rows in (("descriptive",descriptive),("contrasts",contrasts),("pairs",pairs),("preparation",preparation)):
        csv_file(d/(name+".csv"),rows)
    summary=["# E2 — "+report["kind"]+" run "+report["run_id"],"",
        "Conditional exploratory intervals; no pooling across engines or E1; no removal of outliers.","",
        "| Browser | Map | Algorithm | A/C ratio of medians | Reduction % | Paired median | 95% interval | W/T/L |",
        "|---|---|---|---:|---:|---:|---|---|"]
    primary=[r for r in contrasts if r["baseline"]=="A" and r["candidate"]=="C"]
    for r in primary:
        summary.append(f'| {r["engine"]} | {r["map"]} | {r["algorithm"]} | {r["ratio_of_medians"]:.3f} | {r["reduction_pct"]:.2f} | {r["paired_median_ratio"]:.3f} | {r["paired_ci_low"]:.3f}–{r["paired_ci_high"]:.3f} | {r["wins"]}/{r["ties"]}/{r["losses"]} |')
    (d/"summary.md").write_text("\n".join(summary)+"\n",encoding="utf-8")
    print("E2_ANALYSIS "+json.dumps({k:analysis[k] for k in ("run_id","kind","commit","environment","versions","sources","totals","cross_browser_routes")} | {"primary":primary,"descriptive_groups":len(descriptive),"contrasts":len(contrasts),"paired_observations":len(pairs)},ensure_ascii=False),flush=True)


if __name__=="__main__":
    main()
