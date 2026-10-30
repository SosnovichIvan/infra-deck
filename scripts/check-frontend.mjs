import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve('src');
const files=[];
function walk(dir){for(const entry of fs.readdirSync(dir,{withFileTypes:true})){const file=path.join(dir,entry.name);if(entry.isDirectory())walk(file);else if(/\.(ts|tsx)$/.test(file))files.push(file);}}
walk(root);
const ranks={app:0,pages:1,widgets:2,features:3,entities:4,shared:5};
const graph=new Map();
for(const file of files){
 const relative=path.relative(root,file);if(!/^[a-z0-9./-]+$/.test(relative))throw Error('Use kebab-case: '+relative);
 const edges=[];const source=fs.readFileSync(file,'utf8');
 for(const match of source.matchAll(/(?:from\s*|import\s*)['"]([^'"]+)['"]/g)){
  if(!match[1].startsWith('.'))continue;
  const resolved=path.resolve(path.dirname(file),match[1]);
  const target=[resolved,resolved+'.ts',resolved+'.tsx',path.join(resolved,'index.ts')].find(candidate=>files.includes(candidate));
  if(!target)continue;
  const originParts=relative.split(path.sep),targetParts=path.relative(root,target).split(path.sep);
  if(ranks[targetParts[0]]<ranks[originParts[0]] || (originParts[0]===targetParts[0]&&!['app','shared'].includes(originParts[0])&&originParts[1]!==targetParts[1]))throw Error('FSD dependency: '+relative+' -> '+match[1]);
  if(originParts[0]!==targetParts[0]&&targetParts[0]!=='shared'&&path.basename(target)!=='index.ts')throw Error('Slice public API required: '+match[1]);
  edges.push(target);
 }
 graph.set(file,edges);
}
const active=new Set(),done=new Set();
function visit(file){if(active.has(file))throw Error('Import cycle '+file);if(done.has(file))return;active.add(file);for(const edge of graph.get(file)??[])visit(edge);active.delete(file);done.add(file);}
for(const file of files)visit(file);
console.log('FSD, public API, names and cycles verified');
