import test from 'node:test';
import assert from 'node:assert/strict';
import {formatImportJob} from '../qprint/static/import-progress.js';

test('toolchain download distinguishes bytes and elapsed time from verification', () => {
  const text = formatImportJob({status:'running',phase:'verifying',elapsed_seconds:483,
    progress:{stage:'download',message:'正在下载 lean-4.34.0-rc2-windows.zip',bytes:104857600,total_bytes:209715200}});
  assert.match(text,/正在下载 lean/);
  assert.match(text,/100.0 MiB \/ 200.0 MiB（50.0%）/);
  assert.match(text,/8分3秒/);
});
test('extraction and unknown-size downloads do not invent percentages', () => {
  const text = formatImportJob({status:'running',elapsed_seconds:2,progress:{message:'正在解压工具链',completed_files:5,total_files:20}});
  assert.match(text,/5 \/ 20 项/);
  assert.doesNotMatch(text,/%/);
  assert.doesNotMatch(formatImportJob({status:'running',progress:{message:'download',bytes:5}}),/NaN|undefined|%/);
});
test('successful import still exposes verification failure', () => {
  assert.match(formatImportJob({status:'succeeded',result:{verification:{status:'incomplete',reports:[]}}}),/未通过/);
});
test('old servers remain usable', () => {
  assert.match(formatImportJob({status:'running',phase:'verifying'}),/正在准备环境并验证/);
});
test('missing report and storage errors are explicit without a raw JSON dump', () => {
  const text = formatImportJob({status:'succeeded',result:{path:'lean/FLT3',verification:{
    status:'error',message:'installer failed',report_error:'无法保存验证报告：permission denied',reports:[]}}});
  assert.match(text,/installer failed/);
  assert.match(text,/无法保存验证报告/);
  assert.match(text,/未生成可用报告/);
  assert.doesNotMatch(text,/"verification"/);
});
test('paper import retains PDF and source destinations', () => {
  const text = formatImportJob({status:'succeeded',result:{pdf:'pdf/Paper.pdf',tex:'tex/Paper'}});
  assert.match(text,/pdf\/Paper.pdf/);
  assert.match(text,/tex\/Paper/);
});
