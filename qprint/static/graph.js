const NS = 'http://www.w3.org/2000/svg';
const color = {complete:'#7cb8a5',in_progress:'#ccb073',not_started:'#9481b8'};
const svgElement = (tag, attrs = {}) => {const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};

export class KnowledgeGraph {
  constructor(svg, onPreview, onOpen) {
    this.svg=svg;this.onPreview=onPreview;this.onOpen=onOpen;this.points=[];this.edges=[];
    this.transform={x:0,y:0,k:1};this.frame=0;this.tick=0;
    this.svg.addEventListener('wheel',e=>{e.preventDefault();const r=svg.getBoundingClientRect();const x=e.clientX-r.left,y=e.clientY-r.top;const before=this.transform.k;this.transform.k=Math.max(.18,Math.min(4,before*Math.exp(-e.deltaY*.001)));const ratio=this.transform.k/before;this.transform.x=x-(x-this.transform.x)*ratio;this.transform.y=y-(y-this.transform.y)*ratio;this.applyTransform();},{passive:false});
    this.svg.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      const element=e.target.closest('.graph-node');const point=element?this.points.find(p=>p.id===element.dataset.id):null;
      this.drag={point,x:e.clientX,y:e.clientY,moved:false};this.svg.setPointerCapture(e.pointerId);
    });
    this.svg.addEventListener('pointermove',e=>{
      if(!this.drag)return;const dx=e.clientX-this.drag.x,dy=e.clientY-this.drag.y;
      if(Math.abs(dx)+Math.abs(dy)>2)this.drag.moved=true;
      if(this.drag.point){this.drag.point.x+=dx/this.transform.k;this.drag.point.y+=dy/this.transform.k;this.drag.point.vx=0;this.drag.point.vy=0;this.draw();}
      else{this.transform.x+=dx;this.transform.y+=dy;this.applyTransform();}
      this.drag.x=e.clientX;this.drag.y=e.clientY;
    });
    this.svg.addEventListener('pointerup',()=>{
      if(this.drag?.point&&!this.drag.moved){const point=this.drag.point;const now=performance.now();if(this.lastClick?.id===point.id&&now-this.lastClick.time<350){clearTimeout(this.clickTimer);this.lastClick=null;this.onOpen(point.id);}else{this.lastClick={id:point.id,time:now};this.select(point.id);this.clickTimer=setTimeout(()=>this.onPreview(point),220);}}
      this.drag=null;
    });
    this.svg.addEventListener('pointercancel',()=>this.drag=null);
    this.resize=new ResizeObserver(()=>{if(!this.svg.closest('.hidden')&&this.points.length)this.focus();});this.resize.observe(svg);
  }
  stop(){cancelAnimationFrame(this.frame);clearTimeout(this.clickTimer);}
  render(project,selected,options){
    this.stop();this.selected=selected;this.layout=options.layout;
    const neighbors=new Set([selected]);for(const e of project.edges){if(e.source===selected)neighbors.add(e.target);if(e.target===selected)neighbors.add(e.source);}
    const filtered=project.nodes.filter(n=>(!options.kind||n.kind===options.kind)&&(!options.status||n.status===options.status)&&(!options.local||neighbors.has(n.id)));
    const count=filtered.length;this.points=filtered.map((n,i)=>({...n,x:Math.cos(i*2.399)*Math.sqrt(i+1)*65,y:Math.sin(i*2.399)*Math.sqrt(i+1)*65,vx:0,vy:0}));
    const byId=new Map(this.points.map(p=>[p.id,p]));this.edges=project.edges.filter(e=>byId.has(e.source)&&byId.has(e.target)).map(e=>({...e,a:byId.get(e.source),b:byId.get(e.target)}));
    if(this.layout==='layered')this.layer();
    this.svg.replaceChildren();
    const defs=svgElement('defs');const marker=svgElement('marker',{id:'arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.append(svgElement('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'#79708d'}));defs.append(marker);this.svg.append(defs);
    this.group=svgElement('g');this.svg.append(this.group);
    for(const e of this.edges){e.el=svgElement('path',{class:`graph-edge ${e.kind}`,'marker-end':'url(#arrow)',fill:'none'});this.group.append(e.el);}
    for(const p of this.points){const el=svgElement('g',{class:'graph-node',tabindex:0,role:'button','aria-label':p.title,'data-id':p.id});p.el=el;
      el.append(svgElement('rect',{x:-Math.max(35,Math.min(120,p.title.length*3.3)),y:-15,width:Math.max(70,Math.min(240,p.title.length*6.6)),height:48,fill:'transparent','pointer-events':'all'}));
      el.append(svgElement('circle',{r:p.kind==='theorem'?9:6.5,fill:color[p.status],stroke:color[p.status]+'33','stroke-width':7}));
      const title=svgElement('text',{x:0,y:27,'text-anchor':'middle'});title.textContent=p.title.length>38?p.title.slice(0,35)+'…':p.title;el.append(title);
      const tooltip=svgElement('title');tooltip.textContent=p.id;el.append(tooltip);
      el.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();this.onOpen(p.id);}if(e.key===' '){e.preventDefault();this.select(p.id);this.onPreview(p);}});
      this.group.append(el);
    }
    if(!count){const t=svgElement('text',{x:'50%',y:'50%','text-anchor':'middle',fill:'#9790aa'});t.textContent='没有符合筛选条件的节点';this.svg.append(t);}
    document.querySelector('#graph-count').textContent=`${count} nodes · ${this.edges.length} links`;
    this.select(selected);this.draw();this.focus();this.tick=0;if(this.layout==='force')this.animate();
  }
  layer(){
    // Condense strongly connected components so cycles do not inflate layer depth.
    const adjacency=new Map(this.points.map(p=>[p.id,[]]));for(const e of this.edges.filter(e=>e.kind==='uses'))adjacency.get(e.source).push(e.target);
    let index=0;const indices=new Map(),low=new Map(),stack=[],active=new Set(),components=[];
    const visit=id=>{indices.set(id,index);low.set(id,index++);stack.push(id);active.add(id);for(const next of adjacency.get(id)){if(!indices.has(next)){visit(next);low.set(id,Math.min(low.get(id),low.get(next)));}else if(active.has(next))low.set(id,Math.min(low.get(id),indices.get(next)));}if(low.get(id)===indices.get(id)){const component=[];let item;do{item=stack.pop();active.delete(item);component.push(item);}while(item!==id);components.push(component);}};
    for(const p of this.points)if(!indices.has(p.id))visit(p.id);
    const componentOf=new Map();components.forEach((c,i)=>c.forEach(id=>componentOf.set(id,i)));
    const parents=components.map(()=>new Set());for(const e of this.edges.filter(e=>e.kind==='uses')){const a=componentOf.get(e.source),b=componentOf.get(e.target);if(a!==b)parents[b].add(a);}
    const memo=new Map();const level=i=>{if(!memo.has(i))memo.set(i,parents[i].size?1+Math.max(...[...parents[i]].map(level)):0);return memo.get(i);};
    const layers=new Map();for(const p of this.points){const l=level(componentOf.get(p.id));if(!layers.has(l))layers.set(l,[]);layers.get(l).push(p);}
    for(const [l,items] of layers)items.forEach((p,i)=>{p.x=(i-(items.length-1)/2)*215;p.y=l*130;});
  }
  animate(){
    const step=()=>{
      const alpha=Math.max(.02,1-this.tick/260);
      // Exact forces for small libraries; sample repulsion for larger vaults.
      const stride=Math.max(1,Math.ceil(this.points.length/250));
      for(let i=0;i<this.points.length;i++){const a=this.points[i];for(let j=i+1;j<this.points.length;j+=stride){const b=this.points[j];let dx=a.x-b.x,dy=a.y-b.y;const d2=Math.max(200,dx*dx+dy*dy);const force=900*alpha/d2;a.vx+=dx*force;b.vx-=dx*force;a.vy+=dy*force;b.vy-=dy*force;}}
      for(const e of this.edges){const dx=e.b.x-e.a.x,dy=e.b.y-e.a.y;const length=Math.max(1,Math.hypot(dx,dy));const force=(length-155)*.016*alpha;e.a.vx+=dx/length*force;e.a.vy+=dy/length*force;e.b.vx-=dx/length*force;e.b.vy-=dy/length*force;}
      for(const p of this.points){if(this.drag?.point===p)continue;p.vx=(p.vx-p.x*.0008)*.8;p.vy=(p.vy-p.y*.0008)*.8;p.x+=Math.max(-9,Math.min(9,p.vx));p.y+=Math.max(-9,Math.min(9,p.vy));}
      this.draw();if(++this.tick<300)this.frame=requestAnimationFrame(step);
    };this.frame=requestAnimationFrame(step);
  }
  select(id){this.selected=id;const neighbors=new Set([id]);for(const e of this.edges){if(e.source===id)neighbors.add(e.target);if(e.target===id)neighbors.add(e.source);e.el.style.opacity=e.source===id||e.target===id?'.9':'.25';}
    for(const p of this.points){p.el.classList.toggle('selected',p.id===id);p.el.style.opacity=!id||neighbors.has(p.id)?'1':'.4';p.el.querySelector('circle').setAttribute('stroke',p.id===id?'#e2d0ff':color[p.status]+'33');}
  }
  draw(){for(const p of this.points)p.el?.setAttribute('transform',`translate(${p.x},${p.y})`);for(const e of this.edges){if(e.a===e.b){e.el.setAttribute('d',`M ${e.a.x} ${e.a.y-8} C ${e.a.x+60} ${e.a.y-80},${e.a.x-60} ${e.a.y-80},${e.a.x-7} ${e.a.y-5}`);continue;}const dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,d=Math.max(1,Math.hypot(dx,dy));e.el.setAttribute('d',`M ${e.a.x+dx/d*10} ${e.a.y+dy/d*10} L ${e.b.x-dx/d*14} ${e.b.y-dy/d*14}`);}}
  focus(){const r=this.svg.getBoundingClientRect();if(!r.width||!this.points.length)return;const p=this.points.find(p=>p.id===this.selected);const xs=this.points.map(p=>p.x),ys=this.points.map(p=>p.y);const width=Math.max(...xs)-Math.min(...xs)+250,height=Math.max(...ys)-Math.min(...ys)+250;const k=Math.max(.2,Math.min(1.15,(r.width-100)/width,(r.height-200)/height));const x=p?.x??(Math.max(...xs)+Math.min(...xs))/2,y=p?.y??(Math.max(...ys)+Math.min(...ys))/2;this.transform={x:r.width/2-x*k,y:r.height/2+25-y*k,k};this.applyTransform();}
  applyTransform(){this.group?.setAttribute('transform',`translate(${this.transform.x},${this.transform.y}) scale(${this.transform.k})`);}
}
