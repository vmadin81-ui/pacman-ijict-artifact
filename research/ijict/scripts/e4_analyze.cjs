// E4: read-only frozen-source structural analysis (TypeScript 5.8.3, ESLint 9.39.1).
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),cp=require('node:child_process'),assert=require('node:assert/strict');
const ts=require('typescript'),{Linter}=require('eslint'),{builtinRules}=require('eslint/use-at-your-own-risk');
const ROOT=path.resolve(__dirname,'../../..'),RELEASE='aaf3ca5dde1e70ee2a94b2f3571dd7b251f4bc66';
const OUT=path.resolve(process.argv[2]||path.join(ROOT,'research/ijict/raw-data/e4-structural'));
assert.equal(ts.version,'5.8.3');assert.equal(Linter.version,'9.39.1');
const git=(...args)=>cp.execFileSync('git',args,{cwd:ROOT,encoding:'utf8'}).trim();
const hash=(s)=>crypto.createHash('sha256').update(s).digest('hex');
const q=(v,p)=>{const a=[...v].sort((a,b)=>a-b),i=(a.length-1)*p,j=Math.floor(i);return a[j]+(a[Math.min(j+1,a.length-1)]-a[j])*(i-j)};
const stats=v=>{assert(v.length);const q1=q(v,.25),q3=q(v,.75);return {n:v.length,sum:v.reduce((a,b)=>a+b,0),mean:v.reduce((a,b)=>a+b,0)/v.length,median:q(v,.5),q1,q3,iqr:q3-q1,min:Math.min(...v),max:Math.max(...v)}};
const histogram=v=>Object.fromEntries([...new Set(v)].sort((a,b)=>a-b).map(x=>[x,v.filter(y=>y===x).length]));
const legacy=JSON.parse(fs.readFileSync(path.join(ROOT,'metrics/code-v1.0-final-ci.json'),'utf8'));
const rule=builtinRules.get('complexity');
assert(rule&&rule.create,'Pinned ESLint rule unavailable');
const options={max:0,variant:'classic'};
function measureESLint(code){
 // Run the actual built-in rule twice: normal rule and a transparent instrumented
 // copy, to associate each report with its original CodePath node.
 // use-at-your-own-risk API is intentionally pinned and the reports are checked.
 const paths=[],captured=[];
 const instrumented={meta:rule.meta,create(context){
  let current=null;
  const wrapped=Object.create(context,{report:{value(desc){
   assert(current,'Complexity report outside onCodePathEnd');
   captured.push({...current,messageId:desc.messageId,data:desc.data});
   context.report(desc);
  }}});
  const listeners=rule.create(wrapped);
  return {...listeners,onCodePathStart(cp,node){
   const parent=node.parent;
   let range=node.range;
   if(cp.origin==='function'&&parent&&(parent.type==='MethodDefinition'||(parent.type==='Property'&&(parent.method||parent.kind==='get'||parent.kind==='set')))&&parent.value===node)range=parent.range;
   paths.push({origin:cp.origin,type:node.type,start:range[0],end:range[1]});
   listeners.onCodePathStart?.(cp,node);
  },onCodePathEnd(cp,node){
   const parent=node.parent;
   let range=node.range;
   if(cp.origin==='function'&&parent&&(parent.type==='MethodDefinition'||(parent.type==='Property'&&(parent.method||parent.kind==='get'||parent.kind==='set')))&&parent.value===node)range=parent.range;
   current={origin:cp.origin,type:node.type,start:range[0],end:range[1]};
   try{listeners.onCodePathEnd?.(cp,node)}finally{current=null;}
  }};
 }};
 const lint=new Linter({configType:'flat'});
 const messages=lint.verify(code,[{languageOptions:{ecmaVersion:2022,sourceType:'script'},linterOptions:{noInlineConfig:true,reportUnusedDisableDirectives:'off'},plugins:{e4:{rules:{instrumented}}},rules:{complexity:['warn',options],'e4/instrumented':['warn',options]}}],{filename:'inline.js'});
 const original=messages.filter(m=>m.ruleId==='complexity'),copy=messages.filter(m=>m.ruleId==='e4/instrumented');
 assert.equal(messages.length,original.length+copy.length,JSON.stringify(messages.filter(m=>!['complexity','e4/instrumented'].includes(m.ruleId))));
 const clean=m=>({message:m.message,messageId:m.messageId,line:m.line,column:m.column,endLine:m.endLine,endColumn:m.endColumn,severity:m.severity,nodeType:m.nodeType});
 assert.deepEqual(copy.map(clean),original.map(clean),'Instrumented rule differs from original');
 const units=captured.map(x=>{const n=Number(x.data.complexity);assert(Number.isInteger(n)&&n>=1,JSON.stringify(x));return {origin:x.origin,type:x.type,start:x.start,end:x.end,complexity:n,description:x.data.name??null}});
 const key=x=>[x.origin,x.type,x.start,x.end].join(':');
 const inventory=paths.filter(x=>x.origin!=='program');
 assert.deepEqual(units.map(key).sort(),inventory.map(key).sort(),'CodePath coverage');
 assert.equal(new Set(units.map(key)).size,units.length,'Duplicate code paths');
 assert.equal(original.length,units.length);
 return {units,program_paths:paths.filter(x=>x.origin==='program').length,warnings:original.map(clean)};
}
const fixtures=[
 ['linear','function f(){return 1}',[1]],
 ['if','function f(x){if(x)return 1;return 0}',[2]],
 ['if-and','function f(x,y){if(x&&y)return 1;return 0}',[3]],
 ['nested','function outer(x){if(x)return function inner(y){if(y)return 1;return 0};return null}',[2,2]],
 ['optional','function f(a){return a?.b?.c}',[3]],
 ['defaults','function f(a={}){const {b=1}=a;return b}',[3]],
 ['logical-assign','function f(a,b){a ||= 1;b &&= 2;return a+b}',[3]],
 ['switch-classic','function f(x){switch(x){case 1:return 1;case 2:return 2;default:return 0}}',[3]],
 ['nullish','function f(a,b){return a??b}',[2]],
 ['class-implicit','class C { x = a || b; static {if(a)b=1} m(){return 1} }',[1,2,2]],
 ['method-arrow','const x={m(){return ()=>1},get a(){return 2}}; class C {constructor(){} static m(){return 1}}',[1,1,1,1,1]]
];
const controls=fixtures.map(([name,code,expected])=>{const {units}=measureESLint(code),actual=units.map(x=>x.complexity).sort((a,b)=>a-b);assert.deepEqual(actual,expected,name);if(name==='class-implicit')assert.deepEqual(units.map(x=>x.origin).sort(),['class-field-initializer','class-static-block','function']);return {name,code,expected,actual,origins:units.map(x=>x.origin),passed:true}});
function measureAST(file,html,code){
 const ast=ts.createSourceFile(file+'.js',code,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 let classes=0,globalBindings=0,complexityProxy=0;const functions=[];
 const decisions=new Set([ts.SyntaxKind.IfStatement,ts.SyntaxKind.ForStatement,ts.SyntaxKind.ForInStatement,ts.SyntaxKind.ForOfStatement,ts.SyntaxKind.WhileStatement,ts.SyntaxKind.DoStatement,ts.SyntaxKind.CaseClause,ts.SyntaxKind.CatchClause,ts.SyntaxKind.ConditionalExpression]);
 function visit(n){
  if(ts.isClassDeclaration(n))classes++;
  if(ts.isVariableStatement(n)&&n.parent===ast)globalBindings+=n.declarationList.declarations.length;
  if(ts.isFunctionLike(n)&&n.body){
   const start=n.getStart(ast),end=n.end,line=ast.getLineAndCharacterOfPosition(start).line+1,endLine=ast.getLineAndCharacterOfPosition(end).line+1;
   functions.push({start,end,line,endLine,lines:endLine-line+1,kind:ts.SyntaxKind[n.kind],name:n.name?.getText(ast)??(ts.isVariableDeclaration(n.parent)||ts.isPropertyAssignment(n.parent)?n.parent.name.getText(ast):'<anonymous>')});complexityProxy++;
  }
  if(decisions.has(n.kind)||(ts.isBinaryExpression(n)&&[ts.SyntaxKind.AmpersandAmpersandToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken].includes(n.operatorToken.kind)))complexityProxy++;
  ts.forEachChild(n,visit);
 }
 visit(ast);
 const l=functions.map(x=>x.lines);
 return {legacy:{file,htmlLines:html.trimEnd().split(/\r?\n/).length,jsLines:code.split(/\r?\n/).length,jsNonblankLines:code.split(/\r?\n/).filter(l=>l.trim()).length,classes,globalBindings,functions:functions.length,meanFunctionLines:+(l.reduce((a,b)=>a+b,0)/l.length).toFixed(2),complexityProxy,syntaxDiagnostics:ast.parseDiagnostics.length},functions,lengths:stats(l),lengthHistogram:histogram(l)};
}
const releaseFiles=git('ls-tree','-r','--name-only',RELEASE,'versions').split('\n').filter(x=>x.endsWith('.html'));
assert.equal(releaseFiles.length,12);
assert.deepEqual([...releaseFiles].sort(),legacy.results.map(x=>'versions/'+x.file).sort());
const versions=[],functionRows=[],complexityRows=[],coverageRows=[],sources=[];
for(const archived of legacy.results){
 const file=archived.file,relative='versions/'+file,raw=fs.readFileSync(path.join(ROOT,relative)),blob=git('hash-object',relative),expected=git('rev-parse',RELEASE+':'+relative);
 assert.equal(blob,expected,'Frozen source changed '+file);sources.push({file,git_blob:blob,sha256:hash(raw)});
 const html=raw.toString('utf8'),scripts=[...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];assert.equal(scripts.length,1,'Legacy extraction assumes one script '+file);
 const code=scripts[0][1].trim(),A=measureAST(file,html,code),E=measureESLint(code);
 assert.deepEqual(A.legacy,archived,'Legacy metric mismatch '+file);assert.equal(A.legacy.syntaxDiagnostics,0);
 const key=x=>x.start+':'+x.end,ef=E.units.filter(x=>x.origin==='function'),by=new Map(ef.map(x=>[key(x),x])),astBy=new Map(A.functions.map(x=>[key(x),x]));
 assert.equal(by.size,ef.length);assert.equal(astBy.size,A.functions.length);
 let matched=0;
 for(const f of A.functions){const e=by.get(key(f));if(e)matched++;
  functionRows.push({file,...f,complexity:e?.complexity??null,match:e?'matched':'TS-only'});
  if(!e)coverageRows.push({file,origin:'TS-only',type:f.kind,start:f.start,end:f.end,name:f.name});
 }
 for(const e of E.units){const f=e.origin==='function'?astBy.get(key(e)):null;
  complexityRows.push({file,...e,line:code.slice(0,e.start).split('\n').length,match:f?'matched':e.origin==='function'?'ESLint-only':'implicit'});
  if(!f)coverageRows.push({file,origin:e.origin==='function'?'ESLint-only':e.origin,type:e.type,start:e.start,end:e.end,name:e.description});
 }
 const v=ef.map(x=>x.complexity),imp=E.units.filter(x=>x.origin!=='function');
 assert.equal(matched+(A.functions.length-matched),A.functions.length);
 versions.push({...A.legacy,git_blob:blob,sha256:hash(raw),lengths:A.lengths,length_histogram:A.lengthHistogram,cyclomatic:stats(v),complexity_histogram:histogram(v),complexity_gt10:v.filter(x=>x>10).length,complexity_gt10_pct:100*v.filter(x=>x>10).length/v.length,eslint_functions:ef.length,eslint_implicit:imp.length,matched,ts_only:A.functions.length-matched,eslint_only:ef.length-matched,program_paths:E.program_paths,legacy_proxy_per_function:A.legacy.complexityProxy/A.legacy.functions});
}
const result={release:RELEASE,typescript:ts.version,eslint:Linter.version,method:{source:'single inline script, trim as historical AST; positions UTF-16 offsets relative to trimmed JS',complexity:options,unit:'explicit functions only; implicit class initializer/static blocks separately retained',coverage:'exact start/end range after normalizing ESTree method nodes; unmatched preserved',length:'inclusive source lines including nested functions, not exclusive LOC',quantiles:'type 7',threshold:'CC > 10 descriptive only, not a quality standard',top_level:'historical proxy includes top-level decisions; ESLint excludes program path'},controls,sources,versions,coverage:coverageRows,totals:{versions:versions.length,ts_functions:functionRows.length,eslint_functions:complexityRows.filter(x=>x.origin==='function').length,eslint_implicit:complexityRows.filter(x=>x.origin!=='function').length,matched:versions.reduce((s,x)=>s+x.matched,0),legacy_fields_verified:versions.length*9}};
fs.mkdirSync(OUT,{recursive:false});
const write=(name,x)=>fs.writeFileSync(path.join(OUT,name),x);
const json=(name,x)=>write(name,JSON.stringify(x,null,2)+'\n');
const csv=(name,rows)=>{const keys=Object.keys(rows[0]??{file:'',origin:'',type:'',start:'',end:'',name:''}),quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';write(name,keys.join(',')+'\n'+rows.map(r=>keys.map(k=>quote(r[k])).join(',')).join('\n')+(rows.length?'\n':''))};
json('results.json',result);csv('functions.csv',functionRows);csv('complexity.csv',complexityRows);csv('coverage.csv',coverageRows);
csv('versions.csv',versions.map(v=>({file:v.file,jsLines:v.jsLines,classes:v.classes,globalBindings:v.globalBindings,functions:v.functions,meanFunctionLines:v.meanFunctionLines,medianFunctionLines:v.lengths.median,q1FunctionLines:v.lengths.q1,q3FunctionLines:v.lengths.q3,maxFunctionLines:v.lengths.max,complexityProxy:v.complexityProxy,ccSum:v.cyclomatic.sum,ccMean:v.cyclomatic.mean,ccMedian:v.cyclomatic.median,ccQ1:v.cyclomatic.q1,ccQ3:v.cyclomatic.q3,ccMax:v.cyclomatic.max,ccGt10:v.complexity_gt10,matched:v.matched,tsOnly:v.ts_only,eslintOnly:v.eslint_only,implicit:v.eslint_implicit})));
json('environment.json',{commit:git('rev-parse','HEAD'),node:process.version,platform:process.platform,arch:process.arch,typescript:ts.version,eslint:Linter.version,lock_sha256:fs.existsSync(path.join(ROOT,'package-lock.json'))?hash(fs.readFileSync(path.join(ROOT,'package-lock.json'))):null,script_sha256:hash(fs.readFileSync(__filename))});
if(fs.existsSync(path.join(ROOT,'package-lock.json')))fs.copyFileSync(path.join(ROOT,'package-lock.json'),path.join(OUT,'package-lock.json'));
console.log('E4_REPORT '+JSON.stringify(result));
