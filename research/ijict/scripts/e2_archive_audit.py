"""Independent archive check: replay archived routes on original raw grid; recompute statistics."""
import collections
import gzip
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "research/ijict/raw-data/e2-local-20261125T155033Z-a7499139"
REPORT = json.loads((RUN / "report.json").read_text(encoding="utf-8"))
ANALYSIS = json.loads((RUN / "analysis.json").read_text(encoding="utf-8"))
def require(condition, msg):
    if not condition:
        raise ValueError(msg)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

for v, s in REPORT["sources"].items():
    require(sha(ROOT/s["path"]) == s["sha256"], "Source hash "+v)
for name, digest in REPORT["scripts"].items():
    require(sha(ROOT/"research/ijict/scripts"/name) == digest, "Script hash "+name)
html = (ROOT/REPORT["sources"]["C"]["path"]).read_text(encoding="utf-8")
# Parse the three frozen raw grids directly, independent of Maze/PathSearch.
maps = {
    "Classic": ["G................",".#.#####.#####.#.",".#.............#.","...#.#.###.#.#...","##...#..P..#...##","...#.#.###.#.#...",".#.............#.",".#.#####.#####.#.","................."],
    "Labyrinth": ["G................",".###.#######.###.",".....#.....#.....",".###.#.###.#.###.","........P........",".###.#.###.#.###.",".....#.....#.....",".###.#######.###.","................."],
    "Crossroads": ["G................",".###.###.###.###.",".................",".#.#.#.#.#.#.#.#.",".......P.........",".#.#.#.#.#.#.#.#.",".................",".###.###.###.###.","................."],
}
for name, grid in maps.items():
    for row in grid:
        require(json.dumps(row) in html, "Map row not found: "+name)
    require(len(grid)==9 and all(len(row)==17 for row in grid), "Grid dimensions")
moves = {"R":(0,1),"D":(1,0),"L":(0,-1),"U":(-1,0)}
oracles = {}
for name, grid in maps.items():
    cells = {r*17+c for r,row in enumerate(grid) for c,v in enumerate(row) if v != "#"}
    def step(cell, move):
        r,c=divmod(cell,17)
        dr,dc=moves[move]
        nr,nc=r+dr,c+dc
        if 0<=nr<9 and 0<=nc<17 and nr*17+nc in cells:
            return nr*17+nc
        return None
    neighbors = {v:{k:step(v,k) for k in moves} for v in cells}
    dist = {}
    for start in cells:
        d={start:0}; queue=collections.deque([start])
        while queue:
            v=queue.popleft()
            for n in neighbors[v].values():
                if n is not None and n not in d:
                    d[n]=d[v]+1
                    queue.append(n)
        require(set(d)==cells,"Connectivity")
        dist[start]=d
    oracles[name]=(cells,neighbors,dist)

count=0; hashes={}; archives=0
for b in REPORT["browsers"]:
    for r in b["results"]:
        p=RUN/r["route_file"]
        require(sha(p)==r["route_sha256"],"Route archive SHA-256")
        payload=gzip.decompress(p.read_bytes())
        data=json.loads(payload)
        require(data["rows"]==9 and data["cols"]==17 and data["map"]==r["map"] and data["algorithm"]==r["algorithm"] and not data["failures"],"Route metadata")
        cells,neighbors,dist=oracles[r["map"]]
        seen=set(); length=expanded=0
        for x in data["records"]:
            s,t=x["start"],x["target"]
            require(s in cells and t in cells and (s,t) not in seen,"Endpoint/duplicate")
            seen.add((s,t)); pos=s
            for move in x["path"]:
                require(move in moves and neighbors[pos][move] is not None,"Illegal move")
                pos=neighbors[pos][move]
            require(pos==t and len(x["path"])==x["distance"]==x["length"]==dist[s][t],"Shortest route")
            require(isinstance(x["expanded"],int) and x["expanded"]>=1,"Expanded count")
            length+=x["length"]; expanded+=x["expanded"]; count+=1
        require(len(seen)==len(cells)**2==r["pairs"]==r["matched"] and not r["mismatched"],"Pair coverage")
        require(length==r["checksum"] and expanded==r["expanded"],"Aggregates")
        hashes.setdefault((r["map"],r["algorithm"]),[]).append(hashlib.sha256(payload).hexdigest())
        archives+=1
require(archives==12 and count==135980,"Archive count")
require(all(len(v)==2 and v[0]==v[1] for v in hashes.values()) and len(hashes)==6,"Cross-browser identity")
# Re-run the original analyzer on a temporary copy; never overwrite archived evidence.
with tempfile.TemporaryDirectory() as tmp:
    copied=Path(tmp)/"run"
    shutil.copytree(RUN,copied)
    subprocess.run([sys.executable,str(ROOT/"research/ijict/scripts/e2_analyze.py"),str(copied)],check=True)
    regenerated=json.loads((copied/"analysis.json").read_text(encoding="utf-8"))
    require(regenerated==ANALYSIS,"Recomputed JSON")
    for name in ("descriptive.csv","contrasts.csv","pairs.csv","preparation.csv","summary.md"):
        require((copied/name).read_text(encoding="utf-8")==(RUN/name).read_text(encoding="utf-8"),"Recomputed "+name)
print("E2_ARCHIVE_AUDIT "+json.dumps({"run_id":REPORT["run_id"],"archives":archives,"routes_checked":count,"cross_browser_conditions":len(hashes),"source_hashes":3,"recomputed_analysis":True,"recomputed_csv":4,"recomputed_summary":True,"complete":True}))
