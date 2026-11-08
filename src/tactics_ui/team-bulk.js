'use strict';
const teamBulkValues = [15, 15], teamBulkUndo = [null, null];
const teamBulkPositions = [7, 7], teamBulkPositionValues = [15, 15];
const teamBulkPersonality = ['professionalism','loyalty','sportsmanship','temperament','pressure','ambition','adaptability'];
const teamBulkPositionOptions = () => catalog.attributes.filter(a=>a.position&&a.name!=='UnusedSweeper');

const teamBulkPlayersPrevious = playersView;
playersView = function(){
 if(teamBulkUndo[side] && teamBulkUndo[side].owner!==team())teamBulkUndo[side]=null;
 const controls = `<section class="team-bulk-controls" aria-label="本队全员批量编辑"><div><h3>${esc(team().name)} · 全员批量编辑</h3><p class="tiny muted">包含门将、外场和全部替补。全属性包括技术、精神、身体、门将及隐藏性格属性；位置熟练度按所选位置单独设置。</p></div><div class="team-bulk-actions"><label class="field"><span>全属性显示值（1–20）</span><input id="team-all-attributes-value" type="number" min="1" max="20" step="0.2" value="${teamBulkValues[side]}" aria-label="本队全属性目标值"></label><button id="team-all-attributes" class="button">全员全属性设为指定值</button></div><div class="team-bulk-actions"><label class="field"><span>要修改熟练度的位置</span>${select(teamBulkPositionOptions().map(a=>({id:a.id,label:a.label+' · '+a.name})),teamBulkPositions[side],'id="team-position" aria-label="全员熟练度目标位置"')}</label><label class="field"><span>位置熟练度（0–20 整数）</span><input id="team-position-value" type="number" min="0" max="20" step="1" value="${teamBulkPositionValues[side]}" aria-label="全员位置熟练度目标值"></label><button id="team-position-apply" class="button">设置全员该位置熟练度</button><button id="team-bulk-undo" class="button ghost" ${teamBulkUndo[side]?'':'disabled'}>撤销本队上次批量修改</button></div><p class="tiny muted">仅修改所选位置，其他位置熟练度保留。直接修改模拟输入，不自动调整 CA。全属性的非整数显示值按内部精度取整；隐藏性格属性为 1–20 整数。</p></section>`;
 return teamBulkPlayersPrevious().replace('<div class="player-summary">', controls+'<div class="player-summary">');
};

function teamBulkRoster(t){if(t.squad&&typeof syncSquadFromMatch==='function')syncSquadFromMatch(t);return t.squad||t.players;}
function applyTeamBulk(kind, value, position){
 if(kind!=='attributes' && kind!=='position')throw Error('未知批量编辑操作');
 if(kind==='attributes' && (!Number.isFinite(value)||value<1||value>20)){
  toast('全属性显示值必须在 1–20 之间');return false;
 }
 const selected=teamBulkPositionOptions().find(a=>a.id===position);
 if(kind==='position'&&(!selected||!Number.isInteger(value)||value<0||value>20)){
  toast('请选择有效位置，并输入 0–20 之间的整数熟练度');return false;
 }
 const ids=kind==='position'?[selected.id]:catalog.attributes.filter(a=>!a.position).map(a=>a.id);
 const t=team(),roster=teamBulkRoster(t);
 teamBulkUndo[side]={owner:t,kind,ids,players:roster.map(p=>({native_id:p.source_uid??p.native_id,attributes:ids.map(id=>p.attributes[id]),personality:kind==='attributes'?Object.fromEntries(teamBulkPersonality.map(k=>[k,{present:Object.hasOwn(p.native_profile||{},k),value:p.native_profile?.[k]}])):null}))};
 for(const p of roster){
  for(const id of ids)p.attributes[id]=kind==='position'?value:Math.round(value*5);
  if(kind==='attributes'){
   p.native_profile??={};
   for(const key of teamBulkPersonality)p.native_profile[key]=Math.round(value);
  }
 }
 if(kind==='attributes')teamBulkValues[side]=value;
 else{teamBulkPositions[side]=position;teamBulkPositionValues[side]=value;}
 if(t.squad)syncMatchFromSquad(t);
 save();render();toast(`${t.name}：已将 ${roster.length} 名球员${kind==='position'?selected.label+'熟练度设为 '+value:'全属性设为 '+value}`);
 return true;
}

function undoTeamBulk(){
 const before=teamBulkUndo[side],t=team();if(!before)return;const roster=teamBulkRoster(t);
 if(before.owner!==t||roster.length!==before.players.length||roster.some((p,i)=>(p.source_uid??p.native_id)!==before.players[i].native_id)){
  teamBulkUndo[side]=null;render();toast('名单已变化，无法应用上次批量修改的撤销记录');return;
 }
 roster.forEach((p,i)=>{
  const old=before.players[i];before.ids.forEach((id,j)=>p.attributes[id]=old.attributes[j]);
  if(old.personality)for(const [key,entry]of Object.entries(old.personality)){
   if(entry.present)p.native_profile[key]=entry.value;else delete p.native_profile[key];
  }
 });
 teamBulkUndo[side]=null;if(t.squad)syncMatchFromSquad(t);save();render();toast('已撤销本队上次批量修改');
}

const teamBulkBindPrevious=bind;
bind=function(){
 teamBulkBindPrevious();if(view!=='players')return;
 $('#team-all-attributes').onclick=()=>applyTeamBulk('attributes',Number($('#team-all-attributes-value').value));
 $('#team-position').onchange=e=>teamBulkPositions[side]=Number(e.target.value);
 $('#team-position-apply').onclick=()=>applyTeamBulk('position',$('#team-position-value').value.trim()===''?NaN:Number($('#team-position-value').value),Number($('#team-position').value));
 $('#team-bulk-undo').onclick=undoTeamBulk;
};
