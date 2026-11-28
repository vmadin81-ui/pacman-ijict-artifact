function publication(r,a,ci,e1){
 const prefix='research/ijict/',files={},fmt=(v,n=2)=>v.toFixed(n).replace('.',','),engine=e=>e==='chromium'?'Chromium':'Firefox',same=(x,y)=>['engine','map','mode'].every(k=>x[k]===y[k]),rows=a.contrasts.map(c=>{const d=v=>a.descriptive.find(x=>same(x,c)&&x.variant===v),A=d('R0'),B=d('R1'),p=a.preparation.find(x=>x.engine===c.engine&&x.map===c.map),delta=A.median-B.median,n=p.median/delta;return {...c,A,B,p,delta,n,ceil:Math.ceil(n),ci:ci.contrasts.find(x=>same(x,c)).ratio_of_medians}});
 const losses=a.pairs.filter(x=>x.ratio<1-1e-10).map(x=>{const g=rows.find(y=>same(x,y));return {...x,order:x.repeat%2?'R0/R1':'R1/R0',slowdown:100*(1/x.ratio-1),candidate_multiple:x.candidate_time/g.B.median};});
 const table=(header,body)=>['| '+header.join(' | ')+' |','| '+header.map(()=> '---').join(' | ')+' |',...body.map(row=>'| '+row.join(' | ')+' |'),''];
 const group=x=>[engine(x.engine),x.map,x.mode==='submit'?'Submit':'Readback'];
 const m=x=>fmt(x.median)+' ('+fmt(x.q1)+'–'+fmt(x.q3)+')';
 let lines=['# E3 — публикационные материалы (для авторской проверки)','',
 'Локальный запуск '+a.run_id+'; измерительный коммит '+a.commit+'. E3-CI — отдельный технический пилот. Нумерация предварительная.','',
 '## Таблица E3.1 — Абсолютное время, мкс/кадр, медиана (Q1–Q3)','',
 ...table(['Браузер','Карта','Режим','R0','R1','Разность медиан'],rows.map(x=>[...group(x),m(x.A),m(x.B),fmt(x.delta)])),
 '12 серий по 120 кадров на реализацию и условие; 30 прогревочных кадров и одинаковый начальный readback. Не FPS.','',
 '## Таблица E3.2 — Коэффициенты ускорения и условные интервалы','',
 ...table(['Браузер','Карта','Режим','R0/R1','Сокращение, %','Парная медиана [95% интервал]','В/Н/П'],rows.map(x=>[...group(x),fmt(x.ratio_of_medians,3),fmt(x.reduction_pct),fmt(x.paired_median_ratio,3)+' ['+fmt(x.paired_ci_low,3)+'; '+fmt(x.paired_ci_high,3)+']',[x.wins,x.ties,x.losses].join('/')])),
 '20 000 bootstrap повторов, seed 20261125; интервалы условны на конкретной среде; не тест значимости. Все серии сохранены.','',
 '## Таблица E3.3 — Подготовка статического кэша и ориентировочная окупаемость','',
 ...table(['Браузер','Карта','Кэш, мкс/построение (Q1–Q3)','Submit N (целых кадров)','Readback N (целых кадров)'],a.preparation.map(p=>{const g=rows.filter(x=>x.engine===p.engine&&x.map===p.map);return [engine(p.engine),p.map,m(p),fmt(g[0].n)+' ('+g[0].ceil+')',fmt(g[1].n)+' ('+g[1].ceil+')']})),
 'N = median(Tcache)/(median(TR0) - median(TR1)); целые кадры = ceil(N). Постфактум, описательная модель постоянной экономии, не измеренный cold-start crossover. Подготовка: 6 серий по 20 построений с заключительным readback одного пикселя. Не полная загрузка уровня.','',
 '## Таблица E3.4 — Проигрышные блоки','',
 ...table(['Браузер','Карта','Режим','Блок','Порядок','R0, мкс','R1, мкс','R0/R1','Замедление R1, %'],losses.map(x=>[...group(x),x.repeat,x.order,fmt(x.baseline_time),fmt(x.candidate_time),fmt(x.ratio,3),fmt(x.slowdown)])),
 'Три проигрыша Chromium Submit приходятся на блок 2; один Firefox Readback — на блок 11. Причины не установлены. Не исключать наблюдения.','',
 '## Таблица E3.5 — Визуальные проверки и выбранные вызовы Canvas API','',
 ...table(['Браузер','Карта','Пар кадров','Позиций пикселей','Различных пикселей','Δ RGBA max','HUD различий','Кэш / fallback','Вызовы R0/R1'],a.visual.map(v=>{const cs=a.canvas_counts.filter(c=>c.engine===v.engine&&c.map===v.map);return [engine(v.engine),v.map,v.frame_pairs,v.pixel_positions,v.different_pixels,v.max_delta,v.hud_differences,(v.cache_rebuilt?'да':'нет')+'/'+(v.fallback?'да':'нет'),cs.map(c=>c.total).join('/')]})),
 'Проверяются RGBA внутри одного движка и шесть полей HUD. Полные растровые буферы не архивируются; аудит проверяет сохранённую покадровую диагностику, не заново сравнивает исходные растры. Счётчики выбранных методов получены на одном синтетическом кадре.','',
 '## Таблица E3.6 — Сопоставление отношений медиан R0/R1 между исследованиями','',
 ...table(['Браузер','Карта','Режим','E1 four','E1 two','E3-CI','E3-local'],rows.map(x=>{const old=k=>x.engine==='chromium'?fmt(e1.contrasts.find(c=>c.dataset==='renderer-'+k+'-'+x.mode&&c.map===x.map&&c.baseline==='R0'&&c.candidate==='R1').ratio_of_medians,3):'—';return [...group(x),old('four'),old('two'),fmt(x.ci,3),fmt(x.ratio_of_medians,3)]})),
 'E1 four и E1 two — разные исторические нагрузки/протоколы, не объединять. CI и локальные данные не объединять.','',
 '## Технические примечания','',
 'В параметре background_load исходного отчёта опечатка «еобязательные» вместо «Необязательные»; сырой отчёт не изменён. Интерпретация как опечатки опирается на зафиксированные условия до запуска.','',
 'WebGL-проба локального Chromium: '+r.browsers[0].capabilities.webgl.renderer+'. Firefox: '+r.browsers[1].capabilities.webgl.renderer+'. WebGL-проба не определяет фактический backend Canvas 2D.','',
 'Подписи: E3.1 — парные медианы и условные 95% интервалы; E3.2 — ориентировочная окупаемость построения кэша; E3.3 — все 144 парных отношения по блокам (пунктир 1, кресты — проигрыши). Все графики монохромные, не удаляют проигрыши. Научную интерпретацию утверждает автор.',''];
 files[prefix+'tables/e3-publication-tables.md']=lines.join('\n');
 const esc=s=>String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'),num=x=>Number(x.toFixed(4));
 const t=(x,y,s,extra='')=>'<text x="'+num(x)+'" y="'+num(y)+'" '+extra+'>'+esc(s)+'</text>';
 const l=(x,y,X,Y,extra='')=>'<line x1="'+num(x)+'" y1="'+num(y)+'" x2="'+num(X)+'" y2="'+num(Y)+'" stroke="#111" '+extra+'/>';
 const dot=(x,y,solid)=>solid?'<rect x="'+num(x-3.5)+'" y="'+num(y-3.5)+'" width="7" height="7" fill="#111"/>':'<circle cx="'+num(x)+'" cy="'+num(y)+'" r="3.5" fill="white" stroke="#111" stroke-width="1.4"/>';
 const svg=(w,h,b)=>'<svg xmlns="http://www.w3.org/2000/svg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'"><rect width="100%" height="100%" fill="white"/><g font-family="Arial, DejaVu Sans, sans-serif" font-size="14" fill="#111">'+b+'</g></svg>\n';
 let b='',X=v=>190+(v-1)/1.5*480;
 for(const tick of [1,1.25,1.5,1.75,2,2.25,2.5])b+=l(X(tick),39,X(tick),460,tick===1?'stroke-dasharray="5 4"':'opacity=".15"')+t(X(tick),480,fmt(tick,2),'text-anchor="middle" font-size="12"');
 b+=t(12,26,'Chromium','font-weight="bold"')+t(12,244,'Firefox','font-weight="bold"');
 rows.forEach((x,i)=>{const y=53+i*31+(i>=6?32:0);b+=t(12,y+5,x.map+' '+(x.mode==='submit'?'S':'R'))+l(X(x.paired_ci_low),y,X(x.paired_ci_high),y,'stroke-width="1.5"')+l(X(x.paired_ci_low),y-4,X(x.paired_ci_low),y+4)+l(X(x.paired_ci_high),y-4,X(x.paired_ci_high),y+4)+dot(X(x.paired_median_ratio),y,x.mode==='submit')+t(690,y+5,fmt(x.paired_median_ratio,3),'font-size="12"');});
 b+=l(X(1),460,X(2.5),460)+t(430,510,'Парная медиана R0/R1','text-anchor="middle"')+dot(100,534,true)+t(111,539,'Submit (S)')+dot(290,534,false)+t(301,539,'Readback (R)');
 files[prefix+'figures/e3-local-forest.svg']=svg(750,554,b);
 b='';X=v=>190+v/14*475;
 for(const tick of [0,2,4,6,8,10,12,14])b+=l(X(tick),40,X(tick),310,'opacity=".15"')+t(X(tick),328,tick,'text-anchor="middle" font-size="12"');
 b+=t(12,25,'Chromium','font-weight="bold"')+t(12,161,'Firefox','font-weight="bold"');
 a.preparation.forEach((p,i)=>{const y=50+i*43+(i>=3?17:0),g=rows.filter(x=>x.engine===p.engine&&x.map===p.map);b+=t(12,y+13,p.map);g.forEach((x,j)=>{const yy=y+j*14;b+=l(X(0),yy,X(x.n),yy,'stroke-width="'+(j?1:2.4)+'" '+(j?'stroke-dasharray="4 3"':''))+dot(X(x.n),yy,j===0)+t(X(x.n)+10,yy+4,fmt(x.n),'font-size="12"');});});
 b+=l(X(0),310,X(14),310)+t(425,353,'Ориентировочное число кадров N','text-anchor="middle"')+dot(100,375,true)+t(111,380,'Submit')+dot(280,375,false)+t(291,380,'Readback');
 files[prefix+'figures/e3-cache-break-even.svg']=svg(760,395,b);
 b='';const XX=i=>65+(i-1)*43, YY=(v,top)=>top+95-(v-.5)/2.1*95;
 rows.forEach((x,i)=>{const col=i%2,ri=Math.floor(i/2),dx=col*580,top=ri*139+32;const y=v=>YY(v,top);
 b+=t(dx+8,top-10,engine(x.engine)+' · '+x.map+' · '+x.mode,'font-size="13" font-weight="bold"');
 for(const tick of [.5,1,1.5,2,2.5])b+=l(dx+XX(1),y(tick),dx+XX(12),y(tick),tick===1?'stroke-dasharray="5 3"':'opacity=".12"')+t(dx+XX(1)-9,y(tick)+4,fmt(tick,1),'text-anchor="end" font-size="10"');
 const ps=a.pairs.filter(p=>same(p,x));ps.forEach((p,j)=>{const px=dx+XX(p.repeat),py=y(p.ratio);if(j)b+=l(dx+XX(ps[j-1].repeat),y(ps[j-1].ratio),px,py,'stroke-width=".8"');if(p.ratio<1-1e-10)b+=l(px-4,py-4,px+4,py+4,'stroke-width="2"')+l(px-4,py+4,px+4,py-4,'stroke-width="2"');else b+=dot(px,py,true);b+=t(px,top+109,p.repeat,'text-anchor="middle" font-size="9"');});
 });
 b+=t(575,875,'Номер парного блока; вертикальная величина — R0/R1; крест — проигрыш','text-anchor="middle" font-size="13"');
 files[prefix+'figures/e3-paired-blocks.svg']=svg(1160,890,b);
 const derived={run_id:a.run_id,source_report:'research/ijict/raw-data/e3-local-20261125T162100Z-0cb3b422/report.json',unit:'us/frame',method:'post hoc descriptive break-even; not measured crossover',losses,break_even:rows.map(x=>({engine:x.engine,map:x.map,mode:x.mode,R0_median:x.A.median,R1_median:x.B.median,delta_us:x.delta,cache_us:x.p.median,N:x.n,whole_frames:x.ceil}))};
 files[prefix+'analysis/e3-derived.json']=JSON.stringify(derived,null,2)+'\n';
 return files;
}
const fs=require('node:fs'),path=require('node:path'),root=path.resolve(__dirname,'../../..');const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));for(const [p,s] of Object.entries(publication(read('research/ijict/raw-data/e3-local-20261125T162100Z-0cb3b422/report.json'),read('research/ijict/raw-data/e3-local-20261125T162100Z-0cb3b422/analysis.json'),read('research/ijict/analysis/e3-ci-pilot-summary.json'),read('research/ijict/analysis/e1-results.json')))){fs.mkdirSync(path.dirname(path.join(root,p)),{recursive:true});fs.writeFileSync(path.join(root,p),s);}
