'use strict';
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
 render();
}
function poolView(){
 const pool=poolData(),total=poolTotal(pool),uniform=pool.uniform;
 const rows=pool.entries.map((e,i)=>`<div class="pool-entry"><b title="${esc(e.tactic?.tactic_name||e.name)}">${esc(e.name)}</b><label>权重<input type="number" min="1" max="1000" step="1" value="${e.weight||1}" data-pool-weight="${i}"></label><span class="tag">${total?pct((e.weight||1)/total):'0%'}</span><button type="button" class="button small ghost" data-pool-remove="${i}">删除</button></div>`).join('');
 return `<div class="card"><div class="card-head"><h2>客队战术池</h2><span class="tag">${pool.enabled?'随机模式已启用':'随机模式未启用'}</span></div><div class="card-body">${rows?`<div class="pool-entries">${rows}</div><p class="tiny muted">权重合计 ${total} · 单套概率按权重占比计算，同一实验内按种子可复现；随机模式由底栏开关控制。</p>`:`<div class="empty"><div class="symbol">⇄</div><h2>客队战术池还是空的</h2><p>在存档战术页面读取存档后，可把当前联赛对手的预设战术一次性导入。</p><button class="button" data-goto="library">前往存档战术页面</button></div>`}<div class="save-team-controls"><label class="raw-toggle"><input id="pool-uniform" type="checkbox" ${uniform.enabled?'checked':''}>统一客队球员属性</label><label>属性值<input id="pool-uniform-value" type="number" min="1" max="20" step="1" value="${uniform.attribute_value}" ${uniform.enabled?'':'disabled'}></label><span class="tiny muted">能力属性取该值；首发按抽中战术把对应位置熟练度设为最高</span></div></div></div>`;
}
function bindPool(){
 if(view!=='pool')return;
 $$('[data-pool-weight]').forEach(input=>input.onchange=()=>{
  const weight=Number(input.value),entry=poolData().entries[+input.dataset.poolWeight];
  if(!Number.isInteger(weight)||weight<1||weight>1000){toast('权重须为 1–1000 的整数');render();return}
  entry.weight=weight;poolSave();
 });
 $$('[data-pool-remove]').forEach(button=>button.onclick=()=>{
  const pool=poolData();pool.entries.splice(+button.dataset.poolRemove,1);
  if(!pool.entries.length)pool.enabled=false;
  poolSave();
 });
 if($('#pool-uniform'))$('#pool-uniform').onchange=()=>{const enabled=$('#pool-uniform').checked;poolData().uniform.enabled=enabled;$('#pool-uniform-value').disabled=!enabled;poolSave()};
 if($('#pool-uniform-value'))$('#pool-uniform-value').onchange=()=>{
  const value=Number($('#pool-uniform-value').value);
  if(!Number.isInteger(value)||value<1||value>20){toast('统一属性值须为 1–20 的整数');render();return}
  poolData().uniform.attribute_value=value;poolSave();
 };
}
const randomModeLabel=document.createElement('label');randomModeLabel.className='compare-toggle';
randomModeLabel.title='每场从客队战术池按权重抽取一套客队战术，同一实验内按种子可复现；需要先在客队战术池页面导入战术。';
randomModeLabel.innerHTML='<input id="random-mode" type="checkbox">随机模式';
$('#quick-score-mode').closest('label').after(randomModeLabel);
randomModeLabel.hidden=saveMode==='save';
function syncRandomMode(){
 const input=$('#random-mode');if(!input)return;
 const locked=saveMode==='save';
 randomModeLabel.hidden=locked;input.disabled=locked;
 input.checked=locked||!state?false:!!poolData().enabled;
}
if($('#random-mode'))$('#random-mode').onchange=()=>{
 const input=$('#random-mode');
 if(saveMode==='save'){input.checked=false;return}
 const pool=poolData();
 if(input.checked&&!pool.entries.length){input.checked=false;toast('请先在客队战术池页面导入战术');return}
 pool.enabled=input.checked;poolSave();
};
const poolBindPrevious=bind;
bind=function(){poolBindPrevious();syncRandomMode();bindPool()};
