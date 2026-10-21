import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
import assert from 'node:assert/strict';

const source=readFileSync(new URL('../qprint/static/graph.js',import.meta.url),'utf8');
function element(tag){
  const classes=new Set();
  return {tag,children:[],attrs:{},style:{},events:{},dataset:{},
    classList:{toggle(name,on){on?classes.add(name):classes.delete(name);},contains(name){return classes.has(name);}},
    setAttribute(key,value){this.attrs[key]=value;},append(child){this.children.push(child);},
    replaceChildren(){this.children=[];},addEventListener(name,fn){this.events[name]=fn;},
    querySelector(tag){return this.children.find(c=>c.tag===tag);},
    getBoundingClientRect(){return {width:1000,height:700,left:0,top:0};},
    setPointerCapture(){},closest(){return null;}};
}
function harness(layout){
  let frame,preview;
  const Graph=runInNewContext(source.replace('export class KnowledgeGraph','class KnowledgeGraph')+'\nKnowledgeGraph',{
    document:{createElementNS:(_,tag)=>element(tag),querySelector:()=>({})},
    ResizeObserver:class{observe(){}},cancelAnimationFrame(){},clearTimeout(){},
    requestAnimationFrame(fn){frame=fn;return 1;},
  });
  const svg=element('svg'),graph=new Graph(svg,node=>preview=node,()=>{});
  graph.render({nodes:[
    {id:'a',title:'Alpha',kind:'lemma',status:'complete'},
    {id:'b',title:'Beta',kind:'theorem',status:'not_started'},
    {id:'c',title:'Gamma',kind:'definition',status:'complete'},
  ],edges:[{source:'a',target:'b',kind:'uses'}]},'b',{layout,previewSelected:true});
  return {graph,svg,get preview(){return preview;},step(){frame();}};
}
function assertCentered(graph){
  const point=graph.points.find(p=>p.id===graph.selected),{x,y,k}=graph.transform;
  assert.ok(Math.abs(point.x*k+x-500)<1e-8);
  assert.ok(Math.abs(point.y*k+y-350)<1e-8);
}
for(const layout of ['layered','force'])test(`${layout}: entry highlights, centers and previews the selected node`,()=>{
  const h=harness(layout),point=h.graph.points.find(p=>p.id==='b');
  assert.equal(h.preview.id,'b');assert.equal(h.graph.selected,'b');
  assert.equal(point.el.classList.contains('selected'),true);
  assert.equal(point.el.querySelector('circle').attrs.stroke,'#e2d0ff');
  assert.equal(h.graph.points.find(p=>p.id==='c').el.style.opacity,'.4');
  assertCentered(h.graph);
  if(layout==='force')for(let i=0;i<200;i++){h.step();assertCentered(h.graph);}
});
test('manual pan and zoom release automatic centering during force layout',()=>{
  for(const gesture of ['pan','zoom']){
    const h=harness('force');
    if(gesture==='pan'){
      h.svg.events.pointerdown({button:0,target:h.svg,clientX:0,clientY:0,pointerId:1});
      h.svg.events.pointermove({clientX:60,clientY:30});
    }else h.svg.events.wheel({preventDefault(){},clientX:100,clientY:100,deltaY:200});
    const transform={...h.graph.transform};
    h.step();assert.equal(h.graph.centeredId,null);
    assert.deepEqual({...h.graph.transform},transform);
  }
});
