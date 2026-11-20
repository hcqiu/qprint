// Static snapshot transport. Relative URLs support GitHub project Pages.
let routes;
async function readJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`静态文件加载失败 (${response.status})：${url}`);
  return response.json();
}
export async function requestJson(path, options = {}) {
  if ((options.method || 'GET').toUpperCase() !== 'GET') {
    throw new Error('这是只读演示。编辑、导入和 Agent 对话请在本地 Qprint 中使用。');
  }
  if (!routes) routes = readJson(new URL('../data/routes.json', import.meta.url)).catch(error => { routes = null; throw error; });
  const url = new URL(path, 'https://qprint.invalid');
  // URLSearchParams matches Python urlencode (including spaces and Unicode).
  const query = url.searchParams.toString().replace(/%7E/g, '~').replace(/\*/g, '%2A');
  const key = url.pathname + (url.search ? '?' + query : '');
  const target = (await routes)[key];
  if (!target) throw new Error('此功能需要本地 Qprint 服务。');
  return readJson(new URL('../' + target, import.meta.url));
}
