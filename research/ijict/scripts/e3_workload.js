// Derived from tools/renderer_compare_four.py (blob 244546379eed2de590eecaf495b7522592b423de); E3 R0/R1 only.
({sources,mapName,mode})=>{
 const engines=Object.fromEntries(Object.entries(sources).map(([k,v])=>[k,new Function(v)()]));
 const versions=Object.keys(engines);
 if(versions.join(',')!=='R0,R1')throw Error('versions');
 const results=[],samples=[],prep=[],counts=[],frames=[]; let error=null;
 try {
 const make=(version,l)=>{
  const E=engines[version],maze=new E.Maze(l.map,40),canvas=document.createElement('canvas');
  const renderer=new E.Renderer(canvas,document.createElement('h2'),maze);
  // Isolate each renderer HUD: prevent shared DOM masking cached writes.
  renderer.overlay=document.createElement('div');renderer.overlayTitle=document.createElement('b');renderer.overlayHint=document.createElement('span');renderer.lifeIcons=document.createElement('div');
  return {E,maze,canvas,renderer,player:new E.Player(maze),ghost:new E.Ghost(maze,E.createGhostAI('Greedy',42)),pellets:new E.PelletStore(maze)};
 };
 const render=(a,i,scenario)=>{
  const {E,renderer,player,ghost,pellets}=a;
  player.x=340+(i%15)*2;player.y=180;player.direction=E.DIRECTIONS[i%4];
  ghost.x=20+(i%23)*2;ghost.y=20;ghost.direction=E.DIRECTIONS[(i+1)%4];
  renderer.render(player,ghost,pellets,100+Math.floor(i/20),scenario.state,scenario.lives,scenario.power,scenario.shield);
 };
 const states=[
  {name:'normal',state:'PLAYING',lives:3,power:0,shield:0,reduced:false},
  {name:'power',state:'PLAYING',lives:2,power:100,shield:0,reduced:false},
  {name:'shield',state:'PLAYING',lives:2,power:0,shield:100,reduced:false},
  {name:'paused',state:'PAUSED',lives:2,power:0,shield:0,reduced:false},
  {name:'reduced',state:'PLAYING',lives:3,power:0,shield:0,reduced:true},
  {name:'ready',state:'READY',lives:3,power:0,shield:0,reduced:false},
  {name:'clear',state:'LEVEL_CLEAR',lives:2,power:0,shield:0,reduced:false},
  {name:'victory',state:'VICTORY',lives:2,power:0,shield:0,reduced:false},
  {name:'defeat',state:'GAME_OVER',lives:0,power:0,shield:0,reduced:false},
  {name:'respawn',state:'RESPAWNING',lives:2,power:0,shield:100,reduced:false}
 ];
 const pixels=a=>a.renderer.context.getImageData(0,0,a.canvas.width,a.canvas.height).data;
 const levels=new engines.R0.LevelManager().levels;
 if(JSON.stringify(levels.map(l=>[l.name,l.map]))!==JSON.stringify(new engines.R1.LevelManager().levels.map(l=>[l.name,l.map])))throw Error('map mismatch');
 if(!levels.some(l=>l.name===mapName))throw Error('unknown map');
 const shared=Object.fromEntries(versions.map(v=>[v,make(v,levels[0])]));
 for(const l of levels.filter(l=>l.name===mapName)){
  const a=shared.R0, b=shared.R1, previousCache=b.renderer.staticLayer;
  for(const x of Object.values(shared)){
   x.maze=new x.E.Maze(l.map,40);x.renderer.setMaze(x.maze);
   x.player=new x.E.Player(x.maze);x.ghost=new x.E.Ghost(x.maze,x.E.createGhostAI('Greedy',42));
   x.pellets=new x.E.PelletStore(x.maze);
  }
  for(const v of versions.slice(1))if(!shared[v].renderer.staticLayer)throw Error('cache missing '+v);
  if(mode==='equivalence'){
  const rebuilt=!!b.renderer.staticLayer&&b.renderer.staticLayer!==previousCache&&b.renderer.staticLayer.width===b.canvas.width&&b.renderer.staticLayer.height===b.canvas.height;
  const hud=x=>[x.renderer.overlay.hidden,x.renderer.overlayTitle.textContent,x.renderer.overlayHint.textContent,x.renderer.lifeIcons.childElementCount,x.renderer.scoreElement.textContent,x.renderer.lifeIcons.getAttribute('aria-label')];
  const comparisons=Object.fromEntries(versions.slice(1).map(v=>[v,{frames:0,maxDelta:0,differentPixels:0,statusDifferences:0}]));
  for(const scenario of states){
   for(const x of Object.values(shared)){x.renderer.phase=0;x.renderer.previousPosition=null;x.renderer.reducedMotion=scenario.reduced;}
   for(let i=0;i<12;i++){
    if(i===6)for(const x of Object.values(shared)){const key=[...x.pellets.remaining.keys()].find(k=>!x.pellets.remaining.get(k).power);if(key!==undefined)x.pellets.remaining.delete(key);}
    render(a,i,scenario);const statusA=[a.renderer.overlay.hidden,a.renderer.overlayTitle.textContent,a.renderer.overlayHint.textContent,a.renderer.lifeIcons.childElementCount,a.renderer.scoreElement.textContent,a.renderer.lifeIcons.getAttribute('aria-label')];
    const p=pixels(a);
    for(const v of versions.slice(1)){
    const b=shared[v], c=comparisons[v];render(b,i,scenario);const statusB=[b.renderer.overlay.hidden,b.renderer.overlayTitle.textContent,b.renderer.overlayHint.textContent,b.renderer.lifeIcons.childElementCount,b.renderer.scoreElement.textContent,b.renderer.lifeIcons.getAttribute('aria-label')];
    const hudMatch=JSON.stringify(statusA)===JSON.stringify(statusB);if(!hudMatch)c.statusDifferences++;
    const q=pixels(b);
    if(p.length!==q.length||p.length!==680*360*4)throw Error('RGBA dimensions');
    let differentPixels=0,maxDelta=0,firstDifference=null;
    for(let j=0;j<p.length;j+=4){let delta=0;for(let k=0;k<4;k++)delta=Math.max(delta,Math.abs(p[j+k]-q[j+k]));if(delta){differentPixels++;maxDelta=Math.max(maxDelta,delta);if(firstDifference===null)firstDifference={pixel:j/4,reference:Array.from(p.slice(j,j+4)),candidate:Array.from(q.slice(j,j+4))};}}
    c.differentPixels+=differentPixels;c.maxDelta=Math.max(c.maxDelta,maxDelta);
    frames.push({map:l.name,scenario:scenario.name,frame:i+1,pixels:p.length/4,differentPixels,maxDelta,hudMatch,statusA,statusB,firstDifference});
    c.frames++;
    }
   }
  }
  // Strict equivalence gate; any raster discrepancy is reported, not silently accepted.
  // Preserve diagnostics even if a candidate differs. Python exits nonzero after saving all maps.
  // Explicit cache failure fallback on a fresh renderer.
  for(const v of versions.slice(1)){
  const f=make(v,l),g=make('R0',l);f.renderer.staticLayer=null;
  render(f,0,states[0]);render(g,0,states[0]);
  const fallbackPixels=pixels(f), referencePixels=pixels(g);
  results.push({map:l.name,version:v,...comparisons[v],fallback:!fallbackPixels.some((v,i)=>v!==referencePixels[i])&&JSON.stringify(hud(f))===JSON.stringify(hud(g)),rebuilt,wallShapes:a.renderer.wallShapes.length});
  }
  for(const version of versions){
   const x=make(version,l),ctx=x.renderer.context,calls={};
   for(const name of ['fillRect','beginPath','roundRect','fill','stroke','arc','drawImage','save','restore','translate','moveTo','lineTo','closePath']){
    const fn=ctx[name].bind(ctx);ctx[name]=(...args)=>{calls[name]=(calls[name]||0)+1;return fn(...args);};
   }
   render(x,0,states[0]);counts.push({map:l.name,version,calls,total:Object.values(calls).reduce((s,n)=>s+n,0)});
  }
  }
  if(mode==='submit')for(let repeat=0;repeat<6;repeat++){
   const x=make('R1',l),t=performance.now();
   for(let i=0;i<20;i++)x.renderer.buildStaticLayer();
   // Force completion of the final cache raster.
   x.renderer.staticLayer.getContext('2d').getImageData(0,0,1,1);
   prep.push({map:l.name,repeat:repeat+1,builds:20,ms:performance.now()-t});
  }
  if(mode!=='equivalence'){
   const run=version=>{
    const x=make(version,l),ctx=x.renderer.context;
    for(let i=0;i<30;i++)render(x,i,states[0]);
    ctx.getImageData(0,0,1,1);
    const begin=performance.now(),n=120;
    for(let i=0;i<n;i++){render(x,i,states[0]);if(mode==='readback')ctx.getImageData(0,0,1,1);}
    return {ms:performance.now()-begin,frames:n};
   };
   for(let repeat=0;repeat<12;repeat++){
    const order=repeat%2?['R1','R0']:['R0','R1'];
    for(const [position,version] of order.entries()){
      const sample=run(version);if(!Number.isFinite(sample.ms)||sample.ms<=0)throw Error('invalid duration '+version);
      samples.push({map:l.name,mode,version,repeat:repeat+1,position:position+1,order,...sample});
    }
   }
  }
 }
 } catch(e){error=String(e);}
 return {results,samples,prep,counts,frames,error};
}
