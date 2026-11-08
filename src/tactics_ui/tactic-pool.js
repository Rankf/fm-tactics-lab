'use strict';
const poolPanel=document.createElement('section');
poolPanel.className='card save-mode-panel tactic-pool-panel';
executionOptions.after(poolPanel);
poolPanel.hidden=saveMode==='save';
const poolDefaults=()=>({profile:'away-tactic-pool-v1',enabled:false,entries:[],uniform:{enabled:true,attribute_value:15}});
function poolData(){
 const pool=state.away_tactic_pool??=poolDefaults();
 pool.entries??=[];pool.uniform??={enabled:true,attribute_value:15};
 return pool;
}
const poolTotal=pool=>pool.entries.reduce((n,e)=>n+(e.weight||1),0);
async function poolSave(){
 try{state=(await api('/api/validate',clone(state))).scenario;save()}
 catch(e){toast('战术池保存失败：'+e.message)}
 drawPool();
}
function drawPool(){
 poolPanel.hidden=saveMode==='save';
 if(poolPanel.hidden||!state)return;
 const pool=poolData(),total=poolTotal(pool),uniform=pool.uniform;
 const rows=pool.entries.map((e,i)=>`<div class="pool-entry"><b title="${esc(e.tactic?.tactic_name||e.name)}">${esc(e.name)}</b><label>权重<input type="number" min="1" max="1000" step="1" value="${e.weight||1}" data-pool-weight="${i}"></label><span class="tag">${total?pct((e.weight||1)/total):'0%'}</span><button type="button" class="button small ghost" data-pool-remove="${i}">删除</button></div>`).join('');
 poolPanel.innerHTML=`<div class="card-head"><h3>客队战术池</h3><label class="raw-toggle"><input id="pool-enabled" type="checkbox" ${pool.enabled?'checked':''}>启用随机抽取</label></div><div class="card-body">${rows?`<div class="pool-entries">${rows}</div><p class="tiny muted">权重合计 ${total} · 单套概率按权重占比计算，同一实验内按种子可复现</p>`:'<p class="tiny muted">尚未导入战术。导入多个 FMF 后，每场按权重随机抽取一套客队战术。</p>'}<div class="save-team-controls"><button id="pool-import" class="button small">导入战术 FMF</button><input id="pool-file" type="file" accept=".fmf" multiple hidden><span class="tiny muted" id="pool-import-status"></span></div><div class="save-team-controls"><label class="raw-toggle"><input id="pool-uniform" type="checkbox" ${uniform.enabled?'checked':''}>统一客队球员属性</label><label>属性值<input id="pool-uniform-value" type="number" min="1" max="20" step="1" value="${uniform.attribute_value}" ${uniform.enabled?'':'disabled'}></label><span class="tiny muted">位置熟练度取该值，其余属性乘 5</span></div></div>`;
 poolPanel.querySelectorAll('[data-pool-weight]').forEach(input=>input.onchange=()=>{
  const weight=Number(input.value),entry=poolData().entries[+input.dataset.poolWeight];
  if(!Number.isInteger(weight)||weight<1||weight>1000){toast('权重须为 1–1000 的整数');drawPool();return}
  entry.weight=weight;poolSave();
 });
 poolPanel.querySelectorAll('[data-pool-remove]').forEach(button=>button.onclick=()=>{
  const pool=poolData();pool.entries.splice(+button.dataset.poolRemove,1);
  if(!pool.entries.length)pool.enabled=false;
  poolSave();
 });
 if($('#pool-enabled'))$('#pool-enabled').onchange=()=>{
  const pool=poolData(),enabled=$('#pool-enabled').checked;
  if(enabled&&!pool.entries.length){toast('请先导入至少一套战术 FMF');drawPool();return}
  pool.enabled=enabled;poolSave();
 };
 if($('#pool-import'))$('#pool-import').onclick=()=>$('#pool-file').click();
 if($('#pool-file'))$('#pool-file').onchange=poolImport;
 if($('#pool-uniform'))$('#pool-uniform').onchange=()=>{const enabled=$('#pool-uniform').checked;poolData().uniform.enabled=enabled;$('#pool-uniform-value').disabled=!enabled;poolSave()};
 if($('#pool-uniform-value'))$('#pool-uniform-value').onchange=()=>{
  const value=Number($('#pool-uniform-value').value);
  if(!Number.isInteger(value)||value<1||value>20){toast('统一属性值须为 1–20 的整数');drawPool();return}
  poolData().uniform.attribute_value=value;poolSave();
 };
}
async function poolImport(event){
 const files=[...event.target.files],failures=[];let imported=0;
 if(!files.length)return;
 for(const file of files){
  if(!/\.fmf$/i.test(file.name)){failures.push(file.name+'：请选择战术 FMF 文件');continue}
  if(file.size>4*1024*1024){failures.push(file.name+'：文件超过 4 MB');continue}
  try{
   const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
   const name=file.name.replace(/\.fmf$/i,'').trim().slice(0,60)||'未命名战术';
   const result=await api('/api/pool/import-fmf',{scenario:clone(state),file_base64:btoa(binary),name});
   state=result.scenario;save();imported++;
  }catch(e){failures.push(file.name+'：'+e.message)}
 }
 event.target.value='';
 drawPool();
 if(failures.length&&$('#pool-import-status'))$('#pool-import-status').innerHTML=failures.map(f=>`<span class="pool-import-error">${esc(f)}</span>`).join('');
 if(imported||failures.length)toast(`已导入 ${imported} 套战术${failures.length?`，${failures.length} 个失败`:''}`);
}
const poolBindPrevious=bind;
bind=function(){poolBindPrevious();drawPool()};
