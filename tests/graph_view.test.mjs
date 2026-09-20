import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

// Load the browser's dependency-free state module without changing package mode.
const source=readFileSync(new URL('../qprint/static/graph-view.js',import.meta.url),'utf8');
const {createGraphView,syncGraphContext,changeGraphLevel,drillGraph,graphProjection}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const project={nodes:[{id:'A/One#X',path:'A/One.md'},{id:'A/One#Y',path:'A/One.md'},{id:'A/Two#Z',path:'A/Two.md'},{id:'B/Other#X',path:'B/Other.md'}],edges:[{source:'B/Other#X',target:'A/One#X'},{source:'A/One#X',target:'A/Two#Z'}],graph:{
  files:[{id:'A/One.md',project_id:'A',node_ids:['A/One#X','A/One#Y']},{id:'A/Two.md',project_id:'A',node_ids:['A/Two#Z']},{id:'B/Other.md',project_id:'B',node_ids:['B/Other#X']},{id:'B/Empty.md',project_id:'B',node_ids:[]}],
  projects:[{id:'A',file_ids:['A/One.md','A/Two.md']},{id:'B',file_ids:['B/Other.md','B/Empty.md']}],
  node_projects:{'A/One#X':'A','A/One#Y':'A','A/Two#Z':'A','B/Other#X':'B'},
  file_edges:[{source:'B/Other.md',target:'A/One.md'}],project_edges:[{source:'B',target:'A'}]
}};

test('node view defaults to current project; global restores cross-project edges',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');
  let data=graphProjection(project,view,'A/One#X');
  assert.equal(view.scope,'project');assert.equal(data.nodes.length,3);assert.equal(data.edges.length,1);
  view.scope='all';data=graphProjection(project,view,'A/One#X');
  assert.equal(data.nodes.length,4);assert.equal(data.edges.length,2);
});
test('project granularity forces all and drill highlights all file members',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');changeGraphLevel(view,'project');
  assert.equal(view.scope,'all');assert.equal(graphProjection(project,view,'A/One#X').nodes.length,2);
  drillGraph(view,project,'B');
  assert.equal(view.level,'file');assert.equal(view.projectId,'B');assert.equal(view.scope,'all');
  const data=graphProjection(project,view,'A/One#X');
  assert.equal(data.nodes.length,4);assert.deepEqual(data.highlightIds,['B/Other.md','B/Empty.md']);assert.equal(data.selected,null);
});
test('file drill highlights exactly its nodes inside its project',()=>{
  const view=createGraphView();changeGraphLevel(view,'file');drillGraph(view,project,'A/One.md');
  assert.equal(view.level,'node');assert.equal(view.scope,'project');
  const data=graphProjection(project,view,'B/Other#X');
  assert.deepEqual(data.highlightIds,['A/One#X','A/One#Y']);assert.equal(data.nodes.length,3);assert.equal(data.selected,null);
});
test('empty milestone drills without opening an unrelated node',()=>{
  const view=createGraphView();changeGraphLevel(view,'file');drillGraph(view,project,'B/Empty.md');
  assert.equal(view.projectId,'B');assert.equal(view.level,'node');assert.deepEqual(view.highlightIds,[]);
  assert.equal(graphProjection(project,view,'A/One#X').selected,null);
});
test('switching reader context resets stale highlights and tracks new project',()=>{
  const view=createGraphView();changeGraphLevel(view,'file');drillGraph(view,project,'B/Other.md');
  syncGraphContext(view,project,'A/One#X',true);assert.equal(view.projectId,'A');assert.deepEqual(view.highlightIds,[]);
});
test('removed project or empty vault has a safe context',()=>{
  const view=createGraphView();view.projectId='Deleted';syncGraphContext(view,project,null);assert.equal(view.projectId,'A');
  const empty={nodes:[],edges:[],graph:{projects:[],files:[],node_projects:{},file_edges:[],project_edges:[]}};
  syncGraphContext(view,empty,null);assert.equal(view.projectId,null);assert.deepEqual(graphProjection(empty,view,null).nodes,[]);
});
