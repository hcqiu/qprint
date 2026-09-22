const duration = seconds => `${Math.floor((seconds || 0) / 60)}分${Math.floor((seconds || 0) % 60)}秒`;
const mib = bytes => `${(bytes / 1048576).toFixed(1)} MiB`;

export function formatImportJob(job) {
  if (job.status === 'queued') return '等待下载…';
  if (job.status === 'failed') return `导入失败：${job.error}`;
  if (job.status === 'succeeded') {
    const result = job.result;
    const names = {passed:'通过',incomplete:'未通过（见报告）',error:'发生错误',unsupported:'该语言暂不支持',not_run:'已关闭'};
    const verification = result?.verification;
    const lines = [`下载完成${verification ? ` · 验证：${names[verification.status] || verification.status}` : ''}`,
      result?.path || result?.pdf || '', result?.tex || ''];
    if (verification?.message) lines.push(verification.message);
    if (verification?.report_error) lines.push(verification.report_error);
    if (verification && !['passed','not_run','unsupported'].includes(verification.status) && !verification.reports?.length)
      lines.push('未生成可用报告，请查看上方错误信息。');
    return lines.filter(Boolean).join('\n');
  }
  const progress = job.progress;
  const lines = [progress?.message || (job.phase === 'verifying' ? '下载完成，正在准备环境并验证…' : '正在下载和校验文件…')];
  if (progress?.bytes != null) {
    let detail = mib(progress.bytes);
    if (progress.total_bytes > 0) detail += ` / ${mib(progress.total_bytes)}（${Math.min(100, progress.bytes / progress.total_bytes * 100).toFixed(1)}%）`;
    lines.push(detail);
  }
  if (progress?.completed_files != null) lines.push(`${progress.completed_files} / ${progress.total_files} 项`);
  if (progress?.attempt > 1) lines.push(`第 ${progress.attempt} 次下载尝试`);
  if (progress?.output_bytes != null) lines.push(`工具链输出 ${mib(progress.output_bytes)}`);
  if (job.elapsed_seconds != null) lines.push(`任务已运行 ${duration(job.elapsed_seconds)}`);
  return lines.join('\n');
}

export function renderReports(container, reports) {
  const document = container.ownerDocument;
  for (const report of reports || []) {
    const card = document.createElement('section');
    card.className = 'import-report';
    const title = document.createElement('strong');
    title.textContent = `${report.project || '形式化项目'} · ${report.status}`;
    const message = document.createElement('p');
    message.textContent = [report.message || report.diagnosis?.code || '', report.report_error || ''].filter(Boolean).join('\n');
    card.append(title, message);
    for (const [key, label] of [['report_url', '查看错误/验证报告'], ['download_url', '下载完整 JSON']]) {
      // Links come from the workspace-scoped API, never compiler/project HTML.
      if (!report[key]?.startsWith('/api/formal-report?')) continue;
      const link = document.createElement('a');
      link.href = report[key]; link.textContent = label;
      link.target = '_blank'; link.rel = 'noopener';
      card.append(link);
    }
    if (report.report_path) {
      const path = document.createElement('small');
      path.textContent = `报告文件：${report.report_path}`;
      card.append(path);
    }
    container.append(card);
  }
}

export function renderImportJob(container, job) {
  container.textContent = formatImportJob(job);
  renderReports(container, job.result?.verification?.reports);
}
