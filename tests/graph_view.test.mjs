import {readFileSync} from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

// Load the browser's dependency-free state module without changing package mode.
const source=readFileSync(new URL('../qprint/static/graph-view.js',import.meta.url),'utf8');
const {createGraphView,syncGraphContext,changeGraphLevel,changeGraphScope,drillGraph,graphProjection}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
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
test('project granularity preserves scope and drill highlights all file members',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');changeGraphLevel(view,'project');
  assert.equal(view.scope,'project');assert.deepEqual(graphProjection(project,view,'A/One#X').nodes.map(n=>n.id),['A']);
  view.scope='all';assert.equal(graphProjection(project,view,'A/One#X').nodes.length,2);
  drillGraph(view,project,'B');
  syncGraphContext(view,project,'A/One#X');
  assert.equal(view.level,'file');assert.equal(view.projectId,'B');assert.equal(view.scope,'all');
  const data=graphProjection(project,view,'A/One#X');
  assert.equal(data.nodes.length,4);assert.deepEqual(data.highlightIds,['B/Other.md','B/Empty.md']);assert.equal(data.selected,null);
});
test('file drill highlights exactly its nodes inside its project',()=>{
  const view=createGraphView();changeGraphLevel(view,'file');drillGraph(view,project,'A/One.md');
  assert.equal(view.level,'node');assert.equal(view.scope,'project');
  assert.equal(view.milestoneId,'A/One.md');
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
  assert.equal(view.milestoneId,'A/One.md');
});
test('removed project or empty vault has a safe context',()=>{
  const view=createGraphView();view.projectId='Deleted';syncGraphContext(view,project,null);assert.equal(view.projectId,'A');
  const empty={nodes:[],edges:[],graph:{projects:[],files:[],node_projects:{},file_edges:[],project_edges:[]}};
  syncGraphContext(view,empty,null);assert.equal(view.projectId,null);assert.equal(view.milestoneId,null);assert.deepEqual(graphProjection(empty,view,null).nodes,[]);
});

test('milestone scope retains only its nodes and internal edges; all restores the vault',()=>{
  const data={...project,edges:[...project.edges,{source:'A/One#X',target:'A/One#Y'}]};
  const view=createGraphView();syncGraphContext(view,data,'A/One#Y');view.scope='milestone';
  let graph=graphProjection(data,view,'A/One#Y');
  assert.deepEqual(graph.nodes.map(n=>n.id),['A/One#X','A/One#Y']);
  assert.deepEqual(graph.edges,[{source:'A/One#X',target:'A/One#Y'}]);
  assert.equal(graph.selected,'A/One#Y');
  view.scope='project';assert.equal(graphProjection(data,view,null).nodes.length,3);
  view.scope='all';graph=graphProjection(data,view,null);
  assert.equal(graph.nodes.length,4);assert.equal(graph.edges.length,3);
});

test('milestone scope stays selected across granularities with the owning file/project',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');view.scope='milestone';
  for(const [level,expected] of [['file',['A/One.md']],['project',['A']],['node',['A/One#X','A/One#Y']]]){
    changeGraphLevel(view,level);
    assert.equal(view.scope,'milestone');
    const graph=graphProjection(project,view,'A/One#X');
    assert.deepEqual(graph.nodes.map(n=>n.id),expected);assert.deepEqual(graph.edges,[]);
  }
});

test('manual milestone survives refresh and reader navigation updates it even within a project',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');view.scope='milestone';
  view.milestoneId='A/Two.md';syncGraphContext(view,project,'A/One#X');
  assert.deepEqual(graphProjection(project,view,'A/One#X').nodes.map(n=>n.id),['A/Two#Z']);
  assert.equal(graphProjection(project,view,'A/One#X').selected,null);
  syncGraphContext(view,project,'A/One#Y',true);
  assert.equal(view.milestoneId,'A/One.md');assert.equal(view.scope,'milestone');
  syncGraphContext(view,project,'B/Other#X',true);
  assert.equal(view.projectId,'B');assert.equal(view.milestoneId,'B/Other.md');
});

test('project switch and removed milestone fall back to a valid file and clear stale focus',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');view.scope='milestone';
  view.projectId='B';syncGraphContext(view,project,'A/One#X');
  assert.equal(view.milestoneId,'B/Other.md');
  view.milestoneId='Deleted.md';view.focusId='Deleted#Node';view.highlightIds=['Deleted#Node'];
  syncGraphContext(view,project,'A/One#X');
  assert.equal(view.milestoneId,'B/Other.md');assert.equal(view.focusId,null);assert.deepEqual(view.highlightIds,[]);
});

test('empty or missing milestone never leaks unrelated nodes',()=>{
  const view=createGraphView();changeGraphLevel(view,'file');drillGraph(view,project,'B/Empty.md');
  view.scope='milestone';syncGraphContext(view,project,'A/One#X');
  assert.equal(view.milestoneId,'B/Empty.md');
  assert.deepEqual(graphProjection(project,view,'A/One#X').nodes,[]);
  changeGraphLevel(view,'file');assert.deepEqual(graphProjection(project,view,null).nodes.map(n=>n.id),['B/Empty.md']);
  view.milestoneId=null;
  for(const level of ['node','file','project']){
    changeGraphLevel(view,level);assert.deepEqual(graphProjection(project,view,null).nodes,[]);
  }
});

test('entering milestone scope follows the reader instead of a stale manually chosen file',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');
  view.milestoneId='A/Two.md';
  assert.equal(graphProjection(project,view,'A/One#X').nodes.length,3);
  changeGraphScope(view,project,'milestone','A/One#X');
  // Rendering synchronizes again; it must retain the newly resolved context.
  syncGraphContext(view,project,'A/One#X');
  const graph=graphProjection(project,view,'A/One#X');
  assert.equal(view.milestoneId,'A/One.md');
  assert.deepEqual(graph.nodes.map(n=>n.id),['A/One#X','A/One#Y']);
  assert.deepEqual(graph.edges,[]);assert.equal(graph.selected,'A/One#X');
  changeGraphScope(view,project,'project','A/One#X');
  assert.equal(graphProjection(project,view,'A/One#X').nodes.length,3);
});

test('a previewed blueprint node takes priority over the reader and retains focus',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');
  view.focusId='A/Two#Z';view.highlightIds=['A/One#X'];view.highlightLabel='stale';
  changeGraphScope(view,project,'milestone','A/One#X');
  syncGraphContext(view,project,'A/One#X');
  const graph=graphProjection(project,view,'A/One#X');
  assert.equal(view.milestoneId,'A/Two.md');assert.deepEqual(graph.nodes.map(n=>n.id),['A/Two#Z']);
  assert.equal(graph.selected,'A/Two#Z');assert.deepEqual(graph.highlightIds,[]);assert.equal(view.highlightLabel,null);
});

test('milestone entry switches project ownership to the current node',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');
  view.projectId='B';view.milestoneId='B/Other.md';
  changeGraphScope(view,project,'milestone','A/One#X');
  assert.equal(view.projectId,'A');assert.equal(view.milestoneId,'A/One.md');
  changeGraphScope(view,project,'all','A/One#X');view.focusId='B/Other#X';
  changeGraphScope(view,project,'milestone','A/One#X');
  assert.equal(view.projectId,'B');assert.equal(view.milestoneId,'B/Other.md');
  assert.deepEqual(graphProjection(project,view,'A/One#X').nodes.map(n=>n.id),['B/Other#X']);
});

test('entering milestone from project granularity expands its nodes instead of the same project bubble',()=>{
  const view=createGraphView();syncGraphContext(view,project,'A/One#X');changeGraphLevel(view,'project');
  view.focusId='B';
  changeGraphScope(view,project,'milestone','A/One#X');
  assert.equal(view.level,'node');assert.equal(view.milestoneId,'A/One.md');
  assert.deepEqual(graphProjection(project,view,'A/One#X').nodes.map(n=>n.id),['A/One#X','A/One#Y']);
});

test('without a current node, milestone entry preserves a valid empty file and handles an empty vault',()=>{
  const view=createGraphView();view.projectId='B';view.milestoneId='B/Empty.md';view.focusId='Deleted#Node';
  changeGraphScope(view,project,'milestone',null);
  assert.equal(view.milestoneId,'B/Empty.md');assert.deepEqual(graphProjection(project,view,null).nodes,[]);
  const empty={nodes:[],edges:[],graph:{files:[],projects:[],node_projects:{},file_edges:[],project_edges:[]}};
  changeGraphScope(view,empty,'milestone','Deleted#Node');
  assert.equal(view.milestoneId,null);assert.equal(view.projectId,null);assert.deepEqual(graphProjection(empty,view,null).nodes,[]);
});
