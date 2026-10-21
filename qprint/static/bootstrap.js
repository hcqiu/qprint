// Catch module loading errors as well as API/rendering failures during startup.
try {
  const {startApp}=await import('./app.js?v=20261015');
  await startApp();
} catch(error) {
  console.error('Qprint startup failed',error);
  const panel=document.createElement('div');panel.className='empty-state';panel.setAttribute('role','alert');
  const title=document.createElement('h1');title.textContent='知识库加载失败';
  const detail=document.createElement('p');detail.textContent=error?.message||String(error);
  const help=document.createElement('p');help.textContent='请确认本地 Qprint 服务正在运行。若刚更新程序，请按 Ctrl+F5 强制刷新。';
  const retry=document.createElement('button');retry.className='primary';retry.textContent='重新加载';retry.onclick=()=>location.reload();
  panel.append(title,detail,help,retry);document.querySelector('#content').replaceChildren(panel);
}
