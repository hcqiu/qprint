export async function requestJson(path,options={},timeoutMs=60000){
  const controller=new AbortController();
  // Time out reads, including response bodies. Writes may still be running on
  // the server and must not be presented as safe to retry after a client timeout.
  const timer=(!options.method||options.method==='GET')?setTimeout(()=>controller.abort(),timeoutMs):null;
  try{
    const response=await fetch(path,{...options,signal:controller.signal});
    let result;
    try{result=await response.json();}catch(error){if(controller.signal.aborted)throw error;throw new Error(`服务响应异常 (${response.status})`);}
    if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:JSON.stringify(result.detail));
    return result;
  }catch(error){
    if(controller.signal.aborted)throw new Error(`读取知识库超时：${path.split('?')[0]}。请检查本地服务后重试。`);
    throw error;
  }finally{clearTimeout(timer);}
}
