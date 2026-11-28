function publication(a,e1,ci){
 const files={},prefix='research/ijict/',maps=['Classic','Labyrinth','Crossroads'],engines=['chromium','firefox'],algos=['BFS','A*'];
 const f=(v,n=3)=>v.toFixed(n),ru=(v,n=3)=>f(v,n).replace('.',','),name=e=>e==='chromium'?'Chromium':'Firefox';
 const groups=engines.flatMap(engine=>maps.flatMap(map=>algos.map(algorithm=>({engine,map,algorithm}))));
 const get=(g,x,y)=>a.contrasts.find(r=>r.engine===g.engine&&r.map===g.map&&r.algorithm===g.algorithm&&r.baseline===x&&r.candidate===y);
 const desc=(g,v)=>a.descriptive.find(r=>r.engine===g.engine&&r.map===g.map&&r.algorithm===g.algorithm&&r.variant===v);
 const lines=['# E2 — таблицы для авторской редакции статьи','', 'Источник: '+a.run_id+'; commit измерений '+a.commit+'. Основная выборка — локальная; E1 и CI только для сопоставления A/C. Все измерения сохранены. Нумерация предварительная.','',
 '## Таблица E2.1 — Медианное время поиска, мс на полный набор запросов (Q1–Q3)','',
 '| Браузер | Карта | Алгоритм | A | B | C |','|---|---|---|---:|---:|---:|',
 ...groups.map(g=>'| '+[name(g.engine),g.map,g.algorithm,...'ABC'.split('').map(v=>{const r=desc(g,v);return ru(r.median,2)+' ('+ru(r.q1,2)+'–'+ru(r.q3,2)+')'})].join(' | ')+' |'),'',
 '12 серий на вариант и условие; мс на пакет всех упорядоченных пар.','',
 '## Таблица E2.2 — Отношения медиан времени базовой и сравниваемой реализаций','',
 '| Браузер | Карта | Алгоритм | A/B | B/C | A/C |','|---|---|---|---:|---:|---:|',
 ...groups.map(g=>'| '+[name(g.engine),g.map,g.algorithm,...['AB','BC','AC'].map(([x,y])=>ru(get(g,x,y).ratio_of_medians))].join(' | ')+' |'),'',
 'Выше 1 — ускорение сравниваемой реализации, ниже 1 — замедление.','',
 '## Таблица E2.3 — Парные медианы отношений и условные 95% bootstrap-интервалы','',
 '| Браузер | Карта | Алгоритм | A/B | B/C | A/C |','|---|---|---|---:|---:|---:|',
 ...groups.map(g=>'| '+[name(g.engine),g.map,g.algorithm,...['AB','BC','AC'].map(([x,y])=>{const r=get(g,x,y);return ru(r.paired_median_ratio)+' ['+ru(r.paired_ci_low)+'; '+ru(r.paired_ci_high)+']'})].join(' | ')+' |'),'',
 '20 000 повторных выборок парных блоков с возвращением, seed 20261125. Интервалы условны на конкретной среде, не являются тестом значимости или независимой репликацией.','',
 '## Таблица E2.4 — Стоимость подготовки индексированного графа','',
 '| Браузер | Карта | Медиана, мкс/граф | Q1–Q3 | IQR | Min–Max |','|---|---|---:|---:|---:|---:|',
 ...a.preparation.map(r=>'| '+[name(r.engine),r.map,ru(r.median,2),ru(r.q1,2)+'–'+ru(r.q3,2),ru(r.iqr,2),ru(r.min,2)+'–'+ru(r.max,2)].join(' | ')+' |'),'',
 '6 серий по 1000 новых графов на карту; создание объекта Maze вне измерения. Время подготовки исключено из прогретого поиска.','',
 '## Таблица E2.5 — Сопоставление A/C между запусками (отношения медиан)','',
 '| Карта | Алгоритм | E1 Chromium | E2-CI Chromium | E2-local Chromium | E2-CI Firefox | E2-local Firefox |','|---|---|---:|---:|---:|---:|---:|',
 ...maps.flatMap(map=>algos.map(algorithm=>{const h=e1.contrasts.find(r=>r.dataset==='search-abc'&&r.map===map&&r.condition===algorithm&&r.baseline==='A'&&r.candidate==='C');const cp=engine=>ci.primary.find(r=>r.engine===engine&&r.map===map&&r.algorithm===algorithm).ratio_of_medians;return '| '+[map,algorithm,h.ratio_of_medians,cp('chromium'),get({engine:'chromium',map,algorithm},'A','C').ratio_of_medians,cp('firefox'),get({engine:'firefox',map,algorithm},'A','C').ratio_of_medians].map(v=>typeof v==='number'?ru(v):v).join(' | ')+' |'})),'',
 'Наборы не объединяются; E1 — архивный CI с шестью блоками, E2 — 12 блоков.','',
 '## Таблица E2.6 — Число выигрышей / ничьих / проигрышей','',
 '| Браузер | Карта | Алгоритм | A/B | B/C | A/C |','|---|---|---|---:|---:|---:|',
 ...groups.map(g=>'| '+[name(g.engine),g.map,g.algorithm,...['AB','BC','AC'].map(([x,y])=>{const r=get(g,x,y);return [r.wins,r.ties,r.losses].join('/')})].join(' | ')+' |'),'',
 '## Подписи к рисункам (предварительные)','',
 '- E2.1. Парные медианы коэффициентов ускорения и условные 95% bootstrap-интервалы: A/B, B/C, A/C. Вертикальный пунктир соответствует отношению 1; логарифмическая шкала.',
 '- E2.2. Медианная стоимость подготовки индексированного графа. Отрезки — Q1–Q3; шесть серий по 1000 графов.',
 '- E2.3. Сопоставление отношений медиан A/C в E1, E2-CI и E2-local; выборки не объединены.','',
 'Для основного текста рекомендуется E2.2 (таблица отношений медиан) и E2.1 (рисунок интервалов); остальные материалы — дополнительные, по ограничению объёма журнала. Научную интерпретацию утверждает автор.',''];
 files[prefix+'tables/e2-publication-tables.md']=lines.join('\n');
 const svg=(w,h,body)=>'<svg xmlns="http://www.w3.org/2000/svg" width="'+w+'" height="'+h+'" viewBox="0 0 '+w+' '+h+'"><rect width="100%" height="100%" fill="white"/><g font-family="Arial, DejaVu Sans, sans-serif" font-size="14" fill="#111" stroke-linecap="square">'+body+'</g></svg>\n';
 const t=(x,y,s,extra='')=>'<text x="'+x+'" y="'+y+'" '+extra+'>'+s+'</text>';
 const l=(x,y,X,Y,extra='')=>'<line x1="'+x+'" y1="'+y+'" x2="'+X+'" y2="'+Y+'" stroke="#111" '+(extra.includes('stroke-width=')?'':'stroke-width="1" ')+extra+'/>';
 const rect=(x,y,w,h,fill='#fff')=>'<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="'+fill+'" stroke="#111" stroke-width="1.2"/>';
 const mark=(x,y,i)=>i===0?'<circle cx="'+x+'" cy="'+y+'" r="4.5" fill="white" stroke="#111" stroke-width="1.5"/>':i===1?rect(x-4,y-4,8,8,'#111'):'<path d="M '+x+' '+(y-5)+' L '+(x+5)+' '+y+' L '+x+' '+(y+5)+' L '+(x-5)+' '+y+' Z" fill="white" stroke="#111" stroke-width="1.5"/>';
 // 3 panels, shared log scale, point/interval + exact values in tables.
 let body='',W=1110,H=532;
 const panels=['AB','BC','AC'],ticks=[.8,1,2,4,8,12];
 for(let p=0;p<3;p++){
  const x0=170+p*305,x1=x0+265,X=v=>Number((x0+(Math.log(v)-Math.log(.8))/(Math.log(12)-Math.log(.8))*(x1-x0)).toFixed(4));
  body+=t((x0+x1)/2,23,panels[p][0]+'/'+panels[p][1],'text-anchor="middle" font-weight="bold" font-size="16"');
  for(const tick of ticks){const x=X(tick);body+=l(x,38,x,465,tick===1?'stroke-dasharray="5 4"':'opacity=".14"')+t(x,484,tick,'text-anchor="middle" font-size="12"');}
  for(let i=0;i<groups.length;i++){
   const g=groups[i],r=get(g,...panels[p]),y=68+i*31+(i>=6?18:0),lo=X(r.paired_ci_low),hi=X(r.paired_ci_high);
   body+=l(lo,y,hi,y,'stroke-width="1.5"')+l(lo,y-4,lo,y+4)+l(hi,y-4,hi,y+4)+mark(X(r.paired_median_ratio),y,p);
   if(p===0)body+=t(12,y+5,g.map+' '+g.algorithm,'font-size="13"');
  }
  body+=l(x0,465,x1,465);
 }
 body+=t(12,46,'Chromium','font-weight="bold"')+t(12,250,'Firefox','font-weight="bold"')+t(610,515,'Коэффициент ускорения (логарифмическая шкала)','text-anchor="middle"');
 files[prefix+'figures/e2-local-forest.svg']=svg(W,H,body);
 body='';const X=v=>180+v/35*515;
 for(const tick of [0,5,10,15,20,25,30,35])body+=l(X(tick),35,X(tick),270,'opacity=".16"')+t(X(tick),291,tick,'text-anchor="middle" font-size="12"');
 for(let i=0;i<a.preparation.length;i++){const r=a.preparation[i],y=57+i*34+(i>=3?13:0);body+=t(12,y+5,r.map)+l(X(r.q1),y,X(r.q3),y,'stroke-width="2"')+l(X(r.q1),y-5,X(r.q1),y+5)+l(X(r.q3),y-5,X(r.q3),y+5)+mark(X(r.median),y,i<3?1:0)+t(X(r.q3)+11,y+5,ru(r.median,2),'font-size="12"');}
 body+=t(12,31,'Chromium','font-weight="bold"')+t(12,149,'Firefox','font-weight="bold"')+l(X(0),270,X(35),270)+t(438,320,'Время подготовки, мкс/граф','text-anchor="middle"');
 files[prefix+'figures/e2-graph-preparation.svg']=svg(780,338,body);
 body='';const XX=v=>180+v/12*570;const types=['E1 Chromium','E2-CI Chromium','E2-local Chromium','E2-CI Firefox','E2-local Firefox'];
 for(let j=0;j<5;j++){const x=16+(j%3)*245,y=20+Math.floor(j/3)*23;body+=l(x,y-4,x+24,y-4,'stroke-width="'+(j===2||j===4?2.6:1)+'" '+(j>=3?'stroke-dasharray="4 3"':''))+mark(x+12,y-4,j%3)+t(x+31,y,types[j],'font-size="12"');}
 for(const tick of [0,2,4,6,8,10,12])body+=l(XX(tick),62,XX(tick),535,'opacity=".15"')+t(XX(tick),553,tick,'text-anchor="middle" font-size="12"');
 body+=l(XX(1),62,XX(1),535,'stroke-dasharray="5 4"');
 for(const [i,g] of groups.slice(0,6).entries()){const y=90+i*76;body+=t(12,y+22,g.map+' '+g.algorithm,'font-size="13"');
 const h=e1.contrasts.find(r=>r.dataset==='search-abc'&&r.map===g.map&&r.condition===g.algorithm&&r.baseline==='A'&&r.candidate==='C');
 const ff={...g,engine:'firefox'},vals=[h.ratio_of_medians,ci.primary.find(r=>r.engine===g.engine&&r.map===g.map&&r.algorithm===g.algorithm).ratio_of_medians,get(g,'A','C').ratio_of_medians,ci.primary.find(r=>r.engine==='firefox'&&r.map===g.map&&r.algorithm===g.algorithm).ratio_of_medians,get(ff,'A','C').ratio_of_medians];
 for(let j=0;j<5;j++){const yy=y+j*12,x=XX(vals[j]);body+=l(XX(0),yy,x,yy,'stroke-width="'+(j===2||j===4?2.6:1)+'" '+(j>=3?'stroke-dasharray="4 3"':''))+mark(x,yy,j%3);}
 }
 body+=l(XX(0),535,XX(12),535)+t(465,580,'Отношение медианного времени A/C','text-anchor="middle"');
 // Legend requires unique encoding: each row uses its own fixed ordering; add concise note.
 files[prefix+'figures/e2-reproducibility.svg']=svg(810,595,body);
 return files;
}

if(typeof module!=='undefined')module.exports=publication;
if(typeof require!=='undefined'&&require.main===module){const fs=require('node:fs'),path=require('node:path'),root=path.resolve(__dirname,'../../..');const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));for(const [p,s] of Object.entries(publication(read('research/ijict/raw-data/e2-local-20261125T155033Z-a7499139/analysis.json'),read('research/ijict/analysis/e1-results.json'),read('research/ijict/analysis/e2-ci-pilot-summary.json')))){fs.mkdirSync(path.dirname(path.join(root,p)),{recursive:true});fs.writeFileSync(path.join(root,p),s);}}
