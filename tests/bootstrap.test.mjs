import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source=readFileSync(new URL('../qprint/static/bootstrap.js',import.meta.url),'utf8')
  .replace(/import\('\.\/app\.js\?[^']+'\)/,'loadModule()');
function element(){return {children:[],setAttribute(){},append(...children){this.children.push(...children);},replaceChildren(...children){this.children=children;}};}
for(const stage of ['module','initialization'])test(`${stage} failure replaces loading placeholder with persistent error and retry`,async()=>{
  const content=element();let reloaded=false;
  const fail=()=>{throw new Error('broken <module>');};
  await runInNewContext(`(async()=>{${source}})()`,{
    loadModule:stage==='module'?fail:async()=>({startApp:fail}),
    document:{createElement:element,querySelector:()=>content},console:{error(){}},
    location:{reload(){reloaded=true;}},
  });
  const [title,detail,,retry]=content.children[0].children;
  assert.equal(title.textContent,'知识库加载失败');assert.equal(detail.textContent,'broken <module>');
  retry.onclick();assert.equal(reloaded,true);
});
test('successful module loading awaits application initialization',async()=>{
  let initialized=false;
  await runInNewContext(`(async()=>{${source}})()`,{loadModule:async()=>({startApp:async()=>{initialized=true;}})});
  assert.equal(initialized,true);
});
