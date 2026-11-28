// npm install; node tools/metrics.cjs
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const ts = require('typescript');
const root = path.join(__dirname,'..');
const results = fs.readdirSync(path.join(root,'versions')).filter(f=>f.endsWith('.html')).sort((a,b)=>{const x=a.match(/\d+/g).map(Number),y=b.match(/\d+/g).map(Number);for(let i=0;i<Math.max(x.length,y.length);i++){const d=(x[i]||0)-(y[i]||0);if(d)return d;}return 0;}).map(file=>{
 const html=fs.readFileSync(path.join(root,'versions',file),'utf8');
 const code=html.match(/<script[^>]*>([\s\S]*?)<\/script>/i)[1].trim();
 const ast=ts.createSourceFile(file+'.js',code,ts.ScriptTarget.Latest,true,ts.ScriptKind.JS);
 let classes=0, globals=0, functions=0, complexity=0, lengths=[];
 const decisions=new Set([ts.SyntaxKind.IfStatement,ts.SyntaxKind.ForStatement,ts.SyntaxKind.ForInStatement,ts.SyntaxKind.ForOfStatement,ts.SyntaxKind.WhileStatement,ts.SyntaxKind.DoStatement,ts.SyntaxKind.CaseClause,ts.SyntaxKind.CatchClause,ts.SyntaxKind.ConditionalExpression]);
 function visit(n){
  if(ts.isClassDeclaration(n)) classes++;
  if(ts.isVariableStatement(n)&&n.parent===ast) globals+=n.declarationList.declarations.length;
  if(ts.isFunctionLike(n)&&n.body){functions++; complexity++; lengths.push(ast.getLineAndCharacterOfPosition(n.end).line-ast.getLineAndCharacterOfPosition(n.getStart(ast)).line+1);}
  if(decisions.has(n.kind)||ts.isBinaryExpression(n)&&[ts.SyntaxKind.AmpersandAmpersandToken,ts.SyntaxKind.BarBarToken,ts.SyntaxKind.QuestionQuestionToken].includes(n.operatorToken.kind)) complexity++;
  ts.forEachChild(n,visit);
 }
 visit(ast);
 return {file,sha256:crypto.createHash('sha256').update(html).digest('hex'),htmlLines:html.trimEnd().split(/\r?\n/).length,jsLines:code.split(/\r?\n/).length,jsNonblankLines:code.split(/\r?\n/).filter(l=>l.trim()).length,classes,globalBindings:globals,functions,meanFunctionLines:+(lengths.reduce((a,b)=>a+b,0)/functions).toFixed(2),complexityProxy:complexity,syntaxDiagnostics:ast.parseDiagnostics.length};
});
fs.writeFileSync(path.join(root,'metrics','code.json'),JSON.stringify({typescript:ts.version,results},null,2)+'\n');
const keys=Object.keys(results[0]); fs.writeFileSync(path.join(root,'metrics','code.csv'),keys.join(',')+'\n'+results.map(r=>keys.map(k=>r[k]).join(',')).join('\n')+'\n');
console.table(results.map(({sha256,...r})=>r));
