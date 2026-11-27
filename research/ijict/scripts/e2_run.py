"""E2 search replication. Run from a clean research checkout, using Playwright 1.57.0."""
import argparse
import datetime as dt
import gzip
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

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).resolve().parent
MAPS = {"Classic": 11025, "Labyrinth": 10201, "Crossroads": 12769}
ALGORITHMS = ("BFS", "A*")
ORDERS = [list(x) for x in ("ABC", "BCA", "CAB", "ACB", "CBA", "BAC")] * 2
SOURCES = {
    "A": ("versions/pacman_v0.12.2.html", "34e0211924a83d94719448247fe8490dab66ace4"),
    "B": ("experiments/pacman_v1.0-heap.html", "260361c60ace997d8ff70879b4a3bdaf494b8942"),
    "C": ("experiments/pacman_v1.0-indexed.html", "f9bd03a36841f8319b207cf76e0f33c20fda6059"),
}
EXPECTED = {
    ("Classic", "BFS"): (584325, 105536), ("Classic", "A*"): (203675, 105536),
    ("Labyrinth", "BFS"): (520251, 99520), ("Labyrinth", "A*"): (179791, 99520),
    ("Crossroads", "BFS"): (727833, 114160), ("Crossroads", "A*"): (248049, 114160),
}


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def command(*args):
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True, timeout=15,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def hardware():
    info = {"cpu": platform.processor() or None, "logical_cpu_count": os.cpu_count(),
            "ram_bytes": None, "gpu": None}
    if sys.platform == "win32":
        ps = ("$c=Get-CimInstance Win32_Processor;"
              "$m=Get-CimInstance Win32_ComputerSystem;"
              "$g=Get-CimInstance Win32_VideoController;"
              "[pscustomobject]@{cpu=($c.Name -join '; ');"
              "ram_bytes=[long]$m.TotalPhysicalMemory;"
              "gpu=($g.Name -join '; ')}|ConvertTo-Json -Compress")
        try:
            info.update(json.loads(command("powershell.exe", "-NoProfile", "-Command", ps) or "{}"))
        except ValueError:
            pass
    elif sys.platform.startswith("linux"):
        try:
            cpu = Path("/proc/cpuinfo").read_text()
            info["cpu"] = next((x.split(":", 1)[1].strip() for x in cpu.splitlines()
                                if x.startswith("model name")), info["cpu"])
            mem = Path("/proc/meminfo").read_text()
            info["ram_bytes"] = int(next(x for x in mem.splitlines() if x.startswith("MemTotal:")).split()[1])*1024
        except (OSError, ValueError, StopIteration):
            pass
    elif sys.platform == "darwin":
        info["cpu"] = command("sysctl", "-n", "machdep.cpu.brand_string") or info["cpu"]
        ram = command("sysctl", "-n", "hw.memsize")
        if ram and ram.isdigit():
            info["ram_bytes"] = int(ram)
    return info


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+"\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("local", "ci"), default="local")
    parser.add_argument("--power-profile", required=True, help="Observed setting; not modified by runner")
    parser.add_argument("--background-load", required=True, help="Observed background workload")
    parser.add_argument("--notes", default="")
    parser.add_argument("--output", type=Path, help="New, non-existing output directory")
    args = parser.parse_args()
    require(not (os.environ.get("GITHUB_ACTIONS") == "true" and args.kind == "local"),
            "CI must not be labeled as local")
    require(importlib.metadata.version("playwright") == "1.57.0", "Use requirements.txt")
    start = dt.datetime.now(dt.timezone.utc)
    run_id = "e2-"+args.kind+"-"+start.strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8]
    output = (args.output or ROOT/"research/ijict/raw-data"/run_id).resolve()
    commit = command("git", "rev-parse", "HEAD")
    require(commit is not None, "Run from Git checkout")
    dirty = command("git", "status", "--porcelain")
    require(dirty == "", "Start with clean checkout; archive previous attempts before running")
    output.mkdir(parents=True, exist_ok=False)
    sources, provenance = {}, {}
    workload = SCRIPT/"e2_workload.js"
    report = {
        "schema": 1, "run_id": run_id, "kind": args.kind, "complete": False,
        "started_utc": start.isoformat(), "commit": commit,
        "github_run_id": os.environ.get("GITHUB_RUN_ID") if args.kind == "ci" else None,
        "environment": {"platform": platform.platform(), "machine": platform.machine(),
                        "python": platform.python_version(), "node": command("node", "--version"),
                        "playwright": importlib.metadata.version("playwright"),
                        "headless": True, "power_profile": args.power_profile,
                        "background_load": args.background_load, "notes": args.notes,
                        **hardware()},
        "design": {"maps": MAPS, "algorithms": list(ALGORITHMS), "orders": ORDERS,
                   "browser_order": ["chromium", "firefox"], "warmup_passes": 1,
                   "expected_series": 432, "expected_timed_queries": 4895280,
                   "unit": "ms/full query batch", "preparation_batches": 6,
                   "preparation_graphs_per_batch": 1000},
        "sources": provenance, "browsers": [], "errors": [],
        "scripts": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (Path(__file__), workload, SCRIPT/"e2_analyze.py")},
    }

    def checkpoint():
        save_json(output/"report.json", report)

    checkpoint()
    try:
        for v, (relative, expected_blob) in SOURCES.items():
            raw = (ROOT/relative).read_bytes()
            blob = hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
            require(blob == expected_blob, f"Frozen source changed: {v}, {relative}. Use LF checkout.")
            html = raw.decode("utf-8")
            sources[v] = html.split("<script>", 1)[1].split("</script>", 1)[0].split(
                "const game = new Game(", 1)[0]+"\nreturn {PathSearch,Maze,LevelManager,CONFIG};"
            provenance[v] = {"path": relative, "git_blob": blob,
                             "sha256": hashlib.sha256(raw).hexdigest()}
        checkpoint()
        with sync_playwright() as p:
            for engine in ("chromium", "firefox"):
                b = {"engine": engine, "version": None, "complete": False, "preparation": [],
                     "results": [], "samples": [], "warmup": [], "errors": []}
                report["browsers"].append(b)
                browser = None
                try:
                    browser = getattr(p, engine).launch(headless=True,
                        **({"args": ["--no-sandbox"]} if engine=="chromium" else {}))
                    b["version"] = browser.version
                    page = browser.new_page()
                    page.on("pageerror", lambda error, b=b: b["errors"].append(str(error)))
                    b["user_agent"] = page.evaluate("navigator.userAgent")
                    b["webgl"] = page.evaluate("""()=>{try {
                        const gl=document.createElement('canvas').getContext('webgl');
                        if(!gl)return null;
                        const ext=gl.getExtension('WEBGL_debug_renderer_info');
                        return {vendor:gl.getParameter(ext?ext.UNMASKED_VENDOR_WEBGL:gl.VENDOR),
                        renderer:gl.getParameter(ext?ext.UNMASKED_RENDERER_WEBGL:gl.RENDERER)};
                        }catch(e){return null}}""")
                    init = page.evaluate(workload.read_text(encoding="utf-8"), {"sources": sources})
                    require(init["maps"] == list(MAPS), "Map order")
                    for name, count in MAPS.items():
                        prep = page.evaluate("name=>e2.prepareMap(name)", name)
                        require(prep["pairs"] == count, "Unexpected query count")
                        b["preparation"].extend(prep["preparation"])
                        for algorithm in ALGORITHMS:
                            print(f"START {engine} {name} {algorithm}", flush=True)
                            try:
                                v = page.evaluate("a=>e2.verify(a)", algorithm)
                                result = v["summary"]
                                file = f"{engine}-{name.lower()}-{('astar' if algorithm=='A*' else 'bfs')}-routes.json.gz"
                                payload = json.dumps({"map":name,"algorithm":algorithm,
                                    "rows":prep["rows"],"cols":prep["cols"],
                                    "encoding":"row*cols+col; R,D,L,U; common exact A/B/C path",
                                    "records":v["records"],"failures":v["failures"]},
                                    separators=(",",":"), ensure_ascii=False).encode()
                                compressed = gzip.compress(payload, mtime=0)
                                (output/file).write_bytes(compressed)
                                result.update(route_file=file, route_sha256=hashlib.sha256(compressed).hexdigest())
                                b["results"].append(result)
                                checkpoint()
                                require(result["matched"]==count and result["mismatched"]==0
                                    and result["evaluated"]==3*count, "Path equivalence failed")
                                require((result["expanded"],result["checksum"])==EXPECTED[name,algorithm],
                                    "Historical checksum or expanded changed")
                                m = page.evaluate("x=>e2.measure(x.algorithm,x.orders)",
                                                  {"algorithm":algorithm,"orders":ORDERS})
                                b["samples"].extend(m["samples"])
                                b["warmup"].extend({"map":name,"algorithm":algorithm,**w} for w in m["warmup"])
                                checkpoint()
                                require(m["error"] is None and len(m["samples"])==36, str(m["error"]))
                                print(f"PASS {engine} {name} {algorithm} pairs={count} series=36", flush=True)
                            except Exception as e:
                                b["errors"].append({"map":name,"algorithm":algorithm,"error":str(e)})
                                checkpoint()
                    require(not b["errors"], f"{engine}: condition failed")
                    require(len(b["results"])==6 and len(b["samples"])==216, "Incomplete browser")
                    b["complete"] = True
                except Exception as e:
                    report["errors"].append({"engine":engine,"error":str(e)})
                finally:
                    if browser:
                        browser.close()
                    checkpoint()
        report["totals"] = {
            "series":sum(len(b["samples"]) for b in report["browsers"]),
            "timed_queries":sum(s["queries"] for b in report["browsers"] for s in b["samples"]),
            "verified_ordered_pairs_by_algorithm":sum(r["matched"] for b in report["browsers"] for r in b["results"]),
            "pairwise_variant_comparisons":2*sum(r["matched"] for b in report["browsers"] for r in b["results"]),
        }
        require(len(report["browsers"])==2 and all(b["complete"] for b in report["browsers"]), "Incomplete browsers")
        require(report["totals"]=={"series":432,"timed_queries":4895280,
            "verified_ordered_pairs_by_algorithm":135980,"pairwise_variant_comparisons":271960}, "Unexpected total")
        report["complete"] = True
    except Exception as e:
        report["errors"].append({"error":str(e)})
        traceback.print_exc()
    finally:
        report["finished_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        checkpoint()
    print("E2_REPORT "+json.dumps({"run_id":run_id,"kind":args.kind,"complete":report["complete"],
        "browsers":[{k:b[k] for k in ("engine","version","complete","errors")} for b in report["browsers"]],
        "totals":report.get("totals"),"errors":report["errors"]}), flush=True)
    print(f"Output: {output}", flush=True)
    if not report["complete"]:
        return 1
    return subprocess.call([sys.executable, str(SCRIPT/"e2_analyze.py"), str(output)], cwd=ROOT)


if __name__=="__main__":
    raise SystemExit(main())
