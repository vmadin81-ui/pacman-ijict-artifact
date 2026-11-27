// Generate publication-oriented monochrome SVG forest plots from E1 CSV.
const fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const [header,...lines]=fs.readFileSync(path.join(root,'analysis/e1-contrasts.csv'),'utf8').trim().split('\n');
const keys=header.split(',');
const rows=lines.map(line=>Object.fromEntries(line.split(',').map((v,i)=>[keys[i],v.replace(/^"|"$/g,'')])));
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function plot(name,selected,max,step){
 const W=850,H=100+selected.length*38,left=250,right=800,x=v=>left+Number(v)/max*(right-left);
 const out=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 '+W+' '+H+'" width="'+W+'" height="'+H+'">','<rect width="100%" height="100%" fill="white"/>','<g font-family="Arial,sans-serif" font-size="14" fill="black">','<text x="15" y="24" font-weight="bold">'+escape(name)+'</text>'];
 for(let i=0;i<=max+1e-9;i+=step)out.push('<line x1="'+x(i)+'" x2="'+x(i)+'" y1="38" y2="'+(H-48)+'" stroke="#ddd"/><text x="'+x(i)+'" y="'+(H-30)+'" text-anchor="middle">'+Number(i.toFixed(2))+'</text>');
 out.push('<line x1="'+x(1)+'" x2="'+x(1)+'" y1="38" y2="'+(H-48)+'" stroke="black" stroke-dasharray="5 4"/>');
 selected.forEach((r,i)=>{const y=55+i*38,l=x(r.paired_ci_low),h=x(r.paired_ci_high),m=x(r.paired_median_ratio);out.push('<text x="15" y="'+(y+5)+'">'+escape(r.label)+'</text><line x1="'+l+'" x2="'+h+'" y1="'+y+'" y2="'+y+'" stroke="black" stroke-width="2"/><line x1="'+l+'" x2="'+l+'" y1="'+(y-5)+'" y2="'+(y+5)+'" stroke="black"/><line x1="'+h+'" x2="'+h+'" y1="'+(y-5)+'" y2="'+(y+5)+'" stroke="black"/><circle cx="'+m+'" cy="'+y+'" r="4" fill="black"/>');});
 out.push('<text x="'+((left+right)/2)+'" y="'+(H-9)+'" text-anchor="middle">Paired speedup (exploratory 95% bootstrap interval)</text></g></svg>');
 return out.join('\n')+'\n';
}
const dir=path.join(root,'figures');fs.mkdirSync(dir,{recursive:true});
fs.writeFileSync(path.join(dir,'e1-search-forest.svg'),plot('Search: A versus C',rows.filter(r=>r.dataset==='search-abc'&&r.baseline==='A'&&r.candidate==='C').map(r=>({...r,label:r.map+' / '+r.condition})),12,2));
fs.writeFileSync(path.join(dir,'e1-renderer-forest.svg'),plot('Renderer: R0 versus R1 (separate datasets)',rows.filter(r=>r.dataset.startsWith('renderer-')&&r.baseline==='R0'&&r.candidate==='R1').map(r=>({...r,label:r.dataset.includes('four')?'4 variants / '+r.map+' / '+r.condition:'2 variants / '+r.map+' / '+r.condition})),2.5,.5));
