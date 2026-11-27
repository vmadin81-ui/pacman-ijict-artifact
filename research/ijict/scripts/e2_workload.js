// E2 browser-side workload. Loaded as functions by the Python runner.
({sources}) => {
 const engines=Object.fromEntries(Object.entries(sources).map(([v,s])=>[v,new Function(s)()]));
 const levels=new engines.C.LevelManager().levels;
 const variants=['A','B','C'];
 for(const v of variants){
  const l=new engines[v].LevelManager().levels;
  if(JSON.stringify(l.map(x=>[x.name,x.map]))!==JSON.stringify(levels.map(x=>[x.name,x.map])))throw Error('map mismatch '+v);
  if(engines[v].CONFIG.cellSize!==engines.C.CONFIG.cellSize)throw Error('cell size mismatch '+v);
 }
 const expected={Classic:105,Labyrinth:101,Crossroads:113};
 if(JSON.stringify(levels.map(x=>x.name))!==JSON.stringify(Object.keys(expected)))throw Error('unexpected maps');
 const directions=[[0,1,'R'],[1,0,'D'],[0,-1,'L'],[-1,0,'U']];
 let current=null;
 const find=(v,p,q,heuristic)=>engines[v].PathSearch.find(current.maze,p,q,heuristic);
 function prepareMap(name){
  const l=levels.find(x=>x.name===name),rows=l.map.length,cols=l.map[0].length;
  const walk=(r,c)=>r>=0&&r<rows&&c>=0&&c<cols&&l.map[r][c]!=='#';
  const maze=new engines.C.Maze(l.map,engines.C.CONFIG.cellSize),cells=[];
  for(const v of variants){
   const m=new engines[v].Maze(l.map,engines[v].CONFIG.cellSize);
   if(m.rows!==rows||m.cols!==cols)throw Error('dimensions '+v);
   for(let r=0;r<rows;r++)for(let c=0;c<cols;c++)if(m.isWalkable(r,c)!==walk(r,c))throw Error('walkability '+v);
  }
  for(let row=0;row<rows;row++)for(let col=0;col<cols;col++)if(walk(row,col))cells.push({row,col});
  if(cells.length!==expected[name])throw Error('vertex count');
  const id=p=>p.row*cols+p.col,distances=new Map();
  // Independent reference BFS uses the raw grid, not PathSearch or Maze.key.
  for(const p of cells){
   const d=new Map([[id(p),0]]),q=[p];
   for(let i=0;i<q.length;i++){
    const a=q[i];
    for(const [dr,dc] of directions){
     const b={row:a.row+dr,col:a.col+dc},k=id(b);
     if(walk(b.row,b.col)&&!d.has(k)){d.set(k,d.get(id(a))+1);q.push(b);}
    }
   }
   if(d.size!==cells.length)throw Error('disconnected reference map');
   distances.set(id(p),d);
  }
  const pairs=cells.flatMap(p=>cells.map(q=>[p,q]));
  const preparation=[];
  // Six independent batches; maze allocation excluded, as in historical benchmark.
  for(let repeat=1;repeat<=6;repeat++){
   const mazes=Array.from({length:1000},()=>new engines.C.Maze(l.map,engines.C.CONFIG.cellSize));
   const t=performance.now();for(const m of mazes)engines.C.PathSearch.prepare(m);
   preparation.push({map:name,repeat,iterations:mazes.length,ms:performance.now()-t});
  }
  current={name,maze,walk,rows,cols,cells,pairs,distances,id};
  return {map:name,rows,cols,vertices:cells.length,pairs:pairs.length,preparation};
 }
 function verify(algorithm){
  const heuristic=algorithm==='A*',records=[],failures=[];
  let checksum=0,expanded=0,matched=0,evaluated=0,mismatched=0;
  for(const [p,q] of current.pairs){
   const start=current.id(p),target=current.id(q),distance=current.distances.get(start).get(target);
   try{
    const a=find('A',p,q,heuristic),b=find('B',p,q,heuristic),c=find('C',p,q,heuristic);evaluated+=3;
    if(JSON.stringify(a)!==JSON.stringify(b)||JSON.stringify(a)!==JSON.stringify(c)){
     mismatched++;failures.push({start,target,distance,reason:'variant mismatch',A:a,B:b,C:c});continue;
    }
    if(!Array.isArray(a.path)||a.path.length!==distance||!Number.isInteger(a.expanded)||a.expanded<1)throw Error('reference distance/expanded');
    let row=p.row,col=p.col,route='';
    for(const d of a.path){
     const direction=directions.find(([dr,dc])=>dr===d.y&&dc===d.x);
     if(!direction)throw Error('non-cardinal move');
     row+=d.y;col+=d.x;if(!current.walk(row,col))throw Error('illegal move');
     route+=direction[2];
    }
    if(row!==q.row||col!==q.col)throw Error('target mismatch');
    matched++;checksum+=a.path.length;expanded+=a.expanded;
    records.push({start,target,distance,path:route,length:a.path.length,expanded:a.expanded});
   }catch(e){mismatched++;failures.push({start,target,distance,reason:String(e)});}
  }
  const summary={map:current.name,algorithm,vertices:current.cells.length,pairs:current.pairs.length,evaluated,matched,mismatched,checksum,expanded};
  current.verified={algorithm,checksum,expanded,ok:mismatched===0&&matched===current.pairs.length};
  return {summary,records,failures};
 }
 function measure(algorithm,orders){
  const v=current.verified,heuristic=algorithm==='A*',samples=[],warmup=[];
  if(!v||!v.ok||v.algorithm!==algorithm)throw Error('verification not passed');
  const run=variant=>{
   let sum=0,visited=0;const t=performance.now();
   for(const [p,q] of current.pairs){const r=find(variant,p,q,heuristic);sum+=r.path.length;visited+=r.expanded;}
   const ms=performance.now()-t;
   if(sum!==v.checksum||visited!==v.expanded||!Number.isFinite(ms)||ms<=0)throw Error('timing checksum/clock '+variant);
   return {ms,queries:current.pairs.length,checksum:sum,expanded:visited};
  };
  try{
   for(const version of variants)warmup.push({version,...run(version)});
   for(let repeat=1;repeat<=orders.length;repeat++){
    const order=orders[repeat-1];
    for(let position=0;position<order.length;position++){
     const version=order[position];
     samples.push({map:current.name,algorithm,repeat,position:position+1,order,version,...run(version)});
    }
   }
   return {samples,warmup,error:null};
  }catch(e){return {samples,warmup,error:String(e)};}
 }
 globalThis.e2={prepareMap,verify,measure};
 return {maps:levels.map(x=>x.name),cellSize:engines.C.CONFIG.cellSize};
}
