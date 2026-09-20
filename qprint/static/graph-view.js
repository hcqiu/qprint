// View-only grouping: the Markdown node schema remains unchanged.
export function createGraphView() {
  return {level:'node', scope:'project', projectId:null, focusId:null, highlightIds:[], highlightLabel:null};
}

export function syncGraphContext(view, project, selected, reset=false) {
  const index=project.graph;
  const selectedProject=index.node_projects[selected];
  if(reset || !index.projects.some(p=>p.id===view.projectId)) {
    view.projectId=selectedProject??index.projects[0]?.id??null;
    view.focusId=null;
    view.highlightIds=[];
    view.highlightLabel=null;
  }
}

export function changeGraphLevel(view, level) {
  view.level=level;
  view.scope=level==='project'?'all':level==='node'?'project':view.scope;
  view.focusId=null;
  view.highlightIds=[];
  view.highlightLabel=null;
}

export function drillGraph(view, project, id) {
  const index=project.graph;
  if(view.level==='project') {
    const group=index.projects.find(p=>p.id===id);
    if(!group)return;
    view.level='file';view.scope='all';view.projectId=id;
    view.highlightIds=[...group.file_ids];view.focusId=null;
    view.highlightLabel=group.id;
  } else if(view.level==='file') {
    const file=index.files.find(f=>f.id===id);
    if(!file)return;
    view.level='node';view.scope='project';view.projectId=file.project_id;
    view.highlightIds=[...file.node_ids];view.focusId=null;
    view.highlightLabel=file.id;
  }
}

export function graphProjection(project, view, selected) {
  const index=project.graph;
  let nodes=view.level==='project'?index.projects:view.level==='file'?index.files:project.nodes;
  let edges=view.level==='project'?index.project_edges:view.level==='file'?index.file_edges:project.edges;
  if(view.level!=='project' && view.scope==='project') {
    nodes=nodes.filter(n=>(view.level==='file'?n.project_id:index.node_projects[n.id])===view.projectId);
  }
  const ids=new Set(nodes.map(n=>n.id));
  edges=edges.filter(e=>ids.has(e.source)&&ids.has(e.target));
  const selectedNode=project.nodes.find(n=>n.id===selected);
  const current=view.level==='project'?view.projectId:view.level==='file'?selectedNode?.path:selected;
  const highlightIds=view.highlightIds.filter(id=>ids.has(id));
  const focusId=ids.has(view.focusId)?view.focusId:highlightIds.length?null:ids.has(current)?current:null;
  return {nodes,edges,selected:focusId,highlightIds};
}
