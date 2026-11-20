// Expansion is a user preference, independent of the selected node or search.
export function createTreeExpansionStore(storage){
  const workspaces=new Map();
  return workspace=>{
    if(workspaces.has(workspace))return workspaces.get(workspace);
    const key=`qprint.tree.expanded.v1:${workspace}`;
    const expanded=new Set();
    try{
      const saved=JSON.parse(storage().getItem(key)||'[]');
      if(Array.isArray(saved))for(const item of saved)if(typeof item==='string')expanded.add(item);
    }catch{/* Storage may be blocked or contain an older/corrupt value. */}
    const update=entries=>{
      let changed=false;
      for(const [id,open] of entries){
        if(expanded.has(id)===open)continue;
        open?expanded.add(id):expanded.delete(id);changed=true;
      }
      if(changed)try{storage().setItem(key,JSON.stringify([...expanded]));}catch{/* Keep in-memory state. */}
    };
    const state={
      isOpen:id=>expanded.has(id),
      setOpen:(id,open)=>update([[id,open]]),
      // Native toggle events are queued: capture before replacing the DOM so
      // immediate search/navigation cannot discard the user's latest click.
      capture:tree=>update([...tree.querySelectorAll('details[data-tree-key]')].map(el=>[el.dataset.treeKey,el.open])),
    };
    workspaces.set(workspace,state);
    return state;
  };
}
