// View-only grouping: the Markdown node schema remains unchanged.
export function createGraphView() {
  return {level:'node', scope:'project', projectId:null, milestoneId:null, focusId:null, highlightIds:[], highlightLabel:null};
}

export function syncGraphContext(view, project, selected, reset=false) {
  const index=project.graph;
  const selectedFile=project.nodes.find(n=>n.id===selected)?.path;
  const selectedProject=index.node_projects[selected];
  let changed=false;
  if(reset || !index.projects.some(p=>p.id===view.projectId)) {
    view.projectId=selectedProject??index.projects[0]?.id??null;
    changed=true;
  }
  const files=index.files.filter(f=>f.project_id===view.projectId);
  if(reset || !files.some(f=>f.id===view.milestoneId)) {
    view.milestoneId=files.find(f=>f.id===selectedFile)?.id??files[0]?.id??null;
    changed=true;
  }
  if(changed) {
    view.focusId=null;
    view.highlightIds=[];
    view.highlightLabel=null;
  }
}

export function changeGraphLevel(view, level) {
  view.level=level;
  view.focusId=null;
  view.highlightIds=[];
  view.highlightLabel=null;
}

export function changeGraphScope(view, project, scope, selected) {
  // Capture the graph selection before clearing aggregate focus/highlights.
  const current=(view.level==='node'&&project.nodes.find(n=>n.id===view.focusId))
    ||project.nodes.find(n=>n.id===selected);
  view.scope=scope;
  view.focusId=null;
  view.highlightIds=[];
  view.highlightLabel=null;
  if(scope==='milestone') {
    const file=project.graph.files.find(f=>f.id===current?.path);
    if(file) {
      view.projectId=file.project_id;
      view.milestoneId=file.id;
    }
    // A project bubble cannot expose the contents of a single milestone.
    if(view.level==='project')view.level='node';
  }
  syncGraphContext(view,project,selected);
  if(scope==='milestone'&&view.level==='node'&&current?.path===view.milestoneId) {
    view.focusId=current.id;
  }
}

export function drillGraph(view, project, id) {
  const index=project.graph;
  if(view.level==='project') {
    const group=index.projects.find(p=>p.id===id);
    if(!group)return;
    view.level='file';view.scope='all';view.projectId=id;
    view.milestoneId=group.file_ids.includes(view.milestoneId)?view.milestoneId:group.file_ids[0]??null;
    view.highlightIds=[...group.file_ids];view.focusId=null;
    view.highlightLabel=group.id;
  } else if(view.level==='file') {
    const file=index.files.find(f=>f.id===id);
    if(!file)return;
    view.level='node';view.scope='project';view.projectId=file.project_id;
    view.milestoneId=file.id;
    view.highlightIds=[...file.node_ids];view.focusId=null;
    view.highlightLabel=file.id;
  }
}

export function graphProjection(project, view, selected) {
  const index=project.graph;
  let nodes=view.level==='project'?index.projects:view.level==='file'?index.files:project.nodes;
  let edges=view.level==='project'?index.project_edges:view.level==='file'?index.file_edges:project.edges;
  if(view.scope==='project') {
    nodes=nodes.filter(n=>(view.level==='project'?n.id:view.level==='file'?n.project_id:index.node_projects[n.id])===view.projectId);
  } else if(view.scope==='milestone') {
    const file=index.files.find(f=>f.id===view.milestoneId&&f.project_id===view.projectId);
    nodes=file?nodes.filter(n=>view.level==='project'?n.id===file.project_id:view.level==='file'?n.id===file.id:n.path===file.id):[];
  }
  const ids=new Set(nodes.map(n=>n.id));
  edges=edges.filter(e=>ids.has(e.source)&&ids.has(e.target));
  const selectedNode=project.nodes.find(n=>n.id===selected);
  const current=view.level==='project'?view.projectId:view.level==='file'?selectedNode?.path:selected;
  const highlightIds=view.highlightIds.filter(id=>ids.has(id));
  const focusId=ids.has(view.focusId)?view.focusId:highlightIds.length?null:ids.has(current)?current:null;
  return {nodes,edges,selected:focusId,highlightIds};
}
