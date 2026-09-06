'use strict';
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (s) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const e = escapeHtml;
const state = {overview:null, id:'S00010', cursor:1, total:1, data:null, tab:'insight', filter:'all', view:'desk', request:0, drafts:{}, sent:{}, modelBusy:false};
let toastTimer;
function toast(message) { $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').hidden=true,4000); }
async function api(path, body) {
  const response=await fetch(path,body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const result=await response.json();
  if(!response.ok) throw new Error(result.error || '请求失败');
  return result;
}
const priorityClass = (priority) => priority==='高'?'red':priority==='中'?'gold':'neutral';
const pill = (text, color='neutral') => `<span class="pill ${color}">${e(text)}</span>`;
function renderList() {
  const query=$('#search').value.trim().toLowerCase();
  const items=state.overview.sessions.filter(s=>`${s.id} ${s.buyer} ${s.first}`.toLowerCase().includes(query))
    .filter(s=>state.filter==='high'?s.priority==='高':state.filter==='order'?['订单服务','退款打款','补发换货','售后退货'].includes(s.intent):true);
  $('#list-count').textContent=items.length;
  $('#session-list').innerHTML=items.map(s=>`<button class="session-item ${s.id===state.id?'active':''}" data-session="${e(s.id)}" aria-pressed="${s.id===state.id}"><span class="avatar">${e(s.buyer[0])}</span><span class="session-body"><span class="session-title">${e(s.buyer)}<time>${e(s.time.slice(5,10))}</time></span><span class="session-preview">${e(s.first)}</span><span class="session-tags">${pill(s.intent)}${s.priority==='高'?pill('高关注','red'):''}<span class="muted small">${e(s.id)}</span></span></span></button>`).join('') || '<p class="empty">没有匹配的会话。试试其他关键词或筛选。</p>';
}
async function loadSession(id, cursor) {
  if(state.data) state.drafts[state.id]=$('#reply').value;
  const request=++state.request;
  state.id=id; state.cursor=cursor;
  renderList();
  $('#copilot-content').setAttribute('aria-busy','true');
  try {
    const result=await api(`/api/session?id=${encodeURIComponent(id)}&cursor=${cursor}`);
    if(request!==state.request) return;
    state.data=result; state.total=result.total;
    renderConversation(); renderCopilot();
    $('#reply').value=state.drafts[id] || '';
  } catch(err) { toast(err.message); }
  finally { if(request===state.request) $('#copilot-content').removeAttribute('aria-busy'); }
}
function renderConversation() {
  const s=state.data.session;
  $('#buyer-name').textContent=s.buyer;
  $('#buyer-avatar').textContent=s.buyer[0];
  $('#buyer-meta').textContent=`${s.id} · ${state.total} 条历史消息 · 脱敏昵称`;
  const o=s.orders[0];
  $('#order-card').innerHTML=o ? `<div class="product-icon">▯</div><div><h3>${e(o.product)}</h3><p>订单 ${e(o.id)}</p><p>${e(o.carrier||'物流待核实')} · ${e(o.source)}</p></div><div class="amount">¥${Number(o.amount).toFixed(2)}</div>` : '<div class="product-icon">◇</div><div><h3>当前时点暂无可见订单</h3><p>咨询前置场景也能分析，不补造订单信息。</p></div>';
  $('#cursor').max=state.total; $('#cursor').value=Math.min(state.cursor,state.total);
  $('#replay-mode').textContent=s.archived?'归档模式':'历史回放';
  $('#cursor-label').textContent=s.archived?'表格最终记录':`${state.cursor} / ${state.total} 条`;
  $('#prev').disabled=state.cursor<=1; $('#next').disabled=state.cursor>=state.total;
  $('#time-notice').textContent=s.archived?'▣ 归档快照：包含聊天结束后创建的工单，不代表当时已知信息。':`◷ 当前时点 ${s.cutoff} · 仅分析此前已出现的信息`;
  $('#messages').innerHTML=s.messages.map(m=>`<article class="chat-row ${m.role==='客服'?'agent':''}" id="message-${e(m.id)}"><div class="chat-label">${m.role==='客服'?'测试客服':e(s.buyer)} · ${e(m.time.slice(11))} · #${m.seq}</div><div class="bubble">${e(m.text)}${m.type==='图片'?`<div class="image-placeholder">▧ 买家提及图片 · 原文件未提供<small>不进行图片识别或凭空核实内容</small></div>`:''}</div></article>`).join('');
  for(const text of state.sent[state.id]||[]) appendSimulated(text);
  $('#messages').scrollTop=$('#messages').scrollHeight;
}
function appendSimulated(text) {
  $('#messages').insertAdjacentHTML('beforeend',`<article class="chat-row agent simulated"><div class="chat-label">客服 · 本地模拟回复 · 不参与历史分析</div><div class="bubble">${e(text)}</div></article>`);
}
function renderCopilot() {
  if(!state.data) return;
  const a=state.data.analysis,s=state.data.session;
  $('#analysis-mode').textContent=a.mode==='qwen'?`${a.model} · ${a.cache_hit?'缓存命中':a.call_tokens+' tokens'}`:'规则基线 · 需人工复核';
  $('#model-button').disabled=state.modelBusy;
  $('#model-button').textContent=state.modelBusy?'正在分析…':'Qwen 分析 ↗';
  if(state.tab==='journey') return renderJourney(s);
  if(state.tab==='evidence') return renderEvidence(a,s);
  const risks=a.risks.map(r=>`<section class="risk-card ${r.level==='高'?'high':''}"><div class="risk-title">${r.level==='高'?'!':'◇'} ${e(r.title)} ${pill(r.level+'关注',priorityClass(r.level))}</div><p>${e(r.detail)}</p>${r.evidence_ids.filter(id=>s.messages.some(m=>m.id===id)).map(id=>`<button class="evidence-link" data-evidence="${e(id)}">查看原话 ↗</button>`).slice(0,2).join(' ')}</section>`).join('');
  $('#copilot-content').innerHTML=`${a.model_error?`<div class="error-box">${e(a.model_error)}</div>`:''}<section class="insight-card"><div class="section-heading"><h3>此刻，消费者需要什么</h3>${pill(a.priority+'关注',priorityClass(a.priority))}</div><div class="summary-tags">${pill(a.intent,'green')}${pill('情绪 · '+a.emotion,a.emotion==='负向'?'red':a.emotion==='焦急'?'gold':'neutral')}</div><p>${e(a.summary)}</p><div class="emotion-chart" aria-label="买家消息情绪变化">${a.trend.map(t=>`<div class="emotion-step"><div class="emotion-bar level-${t.level}"></div><small>#${t.seq} ${e(t.emotion)}</small></div>`).join('')}</div><p class="footnote">情绪为启发式线索，不代表心理诊断。</p></section><div class="section-heading"><h3>需要留意</h3><span class="muted">${a.risks.length} 项提示</span></div>${risks||'<section class="insight-card"><p>当前未触发规则风险，仍需结合原文判断。</p></section>'}<section class="reply-card"><div class="section-heading"><h3>建议怎么回应</h3><span class="muted">可编辑草稿</span></div><p>${e(a.reply)}</p><button id="adopt-reply">采用建议 ↙</button></section><div class="action-row"><h3>${e(a.action)}</h3><button id="create-task" class="primary">创建跟进</button></div><p class="guard">${e(a.guard)}</p><p class="guard">${e(a.uncertainty)}</p>`;
}
function renderJourney(s) {
  const events=[];
  s.orders.forEach(o=>{
    events.push({time:o.created,title:'订单创建',detail:`${o.product} · ¥${o.amount}`,source:o.source});
    if(o.paid) events.push({time:o.paid,title:'订单付款',detail:'付款时间来自订单表',source:o.source});
    if(o.shipped) events.push({time:o.shipped,title:'订单发货',detail:`${o.carrier} · ${o.tracking}`,source:o.source});
  });
  s.messages.forEach(m=>events.push({time:m.time,title:m.role==='买家'?'买家表达':'客服回应',detail:m.text,source:m.source,id:m.id}));
  s.tickets.forEach(t=>{
    events.push({time:t.created,title:t.kind+'创建',detail:`${t.id} · ${t.status}`,source:t.source});
    if(t.completed) events.push({time:t.completed,title:'工单完成',detail:t.id,source:t.source});
  });
  events.sort((a,b)=>a.time.localeCompare(b.time));
  $('#copilot-content').innerHTML=`<div class="section-heading"><h3>一条可追溯的服务路径</h3>${pill(events.length+' 个节点','green')}</div><p class="muted">${s.archived?'归档模式：展示聊天与事后工单的完整路径。':'聊天、订单、工单按时间对齐。工单晚于当前时点时暂不显示。'}</p>${s.archived?s.tickets.map(t=>`<section class="insight-card"><h3>${e(t.kind)} ${pill(t.status,'gold')}</h3><p>${e(t.id)} · ${e(t.source)}</p><p>${e(t.fields['售后原因']||t.fields['问题类型']||t.fields['退款问题类型']||t.fields['症状描述']||t.fields['退货原因']||'详见原始表格')}</p></section>`).join(''):''}<div class="timeline">${events.map(v=>`<div class="timeline-item"><time>${e(v.time)}</time><h3>${e(v.title)}</h3><p>${e(v.detail)}</p><p>${e(v.source)}</p>${v.id?`<button class="evidence-link" data-evidence="${e(v.id)}">定位消息 ↗</button>`:''}</div>`).join('')}</div><div class="insight-card"><h3>数据边界</h3><p>无状态变更日志，无法还原订单与进行中工单的历史状态。脱敏昵称不能支持确定性的跨会话归并。</p></div>`;
}
function renderEvidence(a,s) {
  $('#copilot-content').innerHTML=`<div class="section-heading"><h3>Agent 工作流</h3>${pill(a.mode==='qwen'?'Qwen + 规则':'本地规则','green')}</div>${a.trace.map((v,i)=>`<div class="trace-step"><span>${i+1}</span><div><h3>${e(v.step)}</h3><p>${e(v.detail)}</p></div></div>`).join('')}<section class="insight-card"><h3>事实与判断分开呈现</h3><p>下方是直接引用的原始消息。意图、情绪和风险属于推断，需要人工复核。${a.mode==='qwen'?'模型引用已通过 ID 存在性检查，语义是否充分仍需审核。':''}</p></section><h3>买家原话 · ${a.evidence.length} 条</h3>${a.evidence.map(v=>`<div class="evidence-card"><small>${e(v.source)} · 消息 #${v.seq}${a.evidence_ids?.includes(v.id)?' · 模型已引用':''}</small><p>${e(v.text)}</p><button class="evidence-link" data-evidence="${e(v.id)}">回到对话 ↗</button></div>`).join('')}<p class="footnote">工作簿 SHA-256</p><p class="muted source-id">${e(state.overview.meta.sha256)}</p>`;
}
async function switchView(view) {
  state.view=view;
  document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('selected',b.dataset.view===view));
  $('#desk-view').hidden=view!=='desk'; $('#alternate-view').hidden=view==='desk';
  if(view==='desk') return;
  $('#alternate-view').innerHTML='<p class="empty">正在载入…</p>';
  try {
    if(view==='tasks') {
      const data=await api('/api/tasks'); if(state.view!==view) return;
      $('#alternate-view').innerHTML=`<span class="eyebrow">FOLLOW THROUGH</span><h2>把关心，跟进到底。</h2><p class="muted">本地任务闭环 · 人工确认 · SQLite 持久保存</p><section class="data-panel"><h3>跟进任务 <span class="count">${data.tasks.length}</span></h3>${data.tasks.map(t=>`<article class="task-item"><div><h3>${e(t.title)} ${pill(t.status,t.status==='已完成'?'green':'gold')}</h3><p>${e(t.note)}</p><small>${e(t.session)} · 回放 #${t.cursor} · ${e(t.created)}</small></div><div><button data-open-task="${e(t.session)}" data-cursor="${t.cursor}">查看会话</button> ${t.status!=='已完成'?`<button class="primary" data-complete="${t.id}">标记完成</button>`:''}</div></article>`).join('')||'<p class="empty">还没有跟进任务。在右侧辅助区创建一条，经确认后会显示在这里。</p>'}</section>`;
    } else if(view==='metrics') {
      const v=await api('/api/evaluation'); if(state.view!==view) return;
      const counts=state.overview.meta.counts;
      $('#alternate-view').innerHTML=`<span class="eyebrow">EVIDENCE, BEFORE CLAIMS</span><h2>让效果，经得起核实。</h2><p class="muted">数据概览与本地规则基线评估 · 不代表大模型成绩或真实业务提升</p><div class="stats-grid"><div class="stat-tile"><small>官方会话</small><b>138</b><small>10 类主场景</small></div><div class="stat-tile"><small>聊天消息</small><b>998</b><small>按回放时点过滤</small></div><div class="stat-tile"><small>订单 / 工单</small><b>113 / 80</b><small>按会话 ID 对齐</small></div><div class="stat-tile"><small>首条消息意图准确率</small><b>${v.accuracy==null?'待评估':(v.accuracy*100).toFixed(1)+'%'}</b><small>同源 MOCK 诊断集，非独立测试集</small></div></div><section class="data-panel"><h3>各场景识别情况</h3>${v.by_class?`<table><thead><tr><th>官方场景</th><th>样本</th><th>正确</th><th>召回率</th></tr></thead><tbody>${v.by_class.map(c=>`<tr><td>${e(c.label)}</td><td>${c.support}</td><td>${c.correct}</td><td>${(c.recall*100).toFixed(1)}%</td></tr>`).join('')}</tbody></table>`:'<p>请运行 python scripts/evaluate.py 生成报告。</p>'}</section><section class="data-panel"><h3>评估边界</h3><p>场景标签只用于评估，不进入规则或模型输入。以每个会话第一条买家消息预测主场景；模板化数据无法证明真实业务泛化。</p><p>情绪标签、真实重复进线身份、处理耗时和客服满意度基准缺失，因此不报告这些准确率或提升百分比。Qwen 尚未在本交付中完成在线实测。</p><p>后续验证：人工双标情绪与风险集、独立场景盲测、客服交叉试用，记录定位耗时、证据一致性和实际 token 使用。</p></section>`;
    } else {
      $('#alternate-view').innerHTML=`<span class="eyebrow">BEAUTY CARE COPILOT</span><h2>知微：从看见数据，到理解处境。</h2><p class="muted">赛题一 · 数据共情者 — 消费者的 AI 管家</p><section class="data-panel"><h3>三分钟上手</h3><p>① 在接待列表选择会话，可搜索或筛选高关注内容。</p><p>② 拖动聊天上方进度条，观察同一会话随消息推进产生的风险与建议。</p><p>③ 在右侧查看即时洞察、服务轨迹和原文证据，采用建议后编辑回复。</p><p>④ 点击“创建跟进”，确认后进入任务列表。模拟发送不会联系消费者。</p></section><section class="data-panel"><h3>工作流与模型</h3><div class="flow"><span>关联多源数据</span><span>过滤未来信息</span><span>识别意图与风险</span><span>建议与证据</span><span>人工确认</span></div><p>默认离线规则。设置服务端环境变量 DASHSCOPE_API_KEY，可选 QWEN_BASE_URL 和 QWEN_MODEL，重启后点击“Qwen 分析”。响应须通过字段与证据 ID 校验，失败时明确降级。</p><p>请求采用最小上下文与缓存。模拟图片只有路径，未提供原文件，因此不展示虚构图像识别结论。</p></section><section class="data-panel"><h3>项目范围</h3><p>这是基于官方虚构数据的本地竞赛 Demo。未连接真实千牛、支付或物流系统。规则分析不是模型评测，人工审核仍是最终决策环节。</p><p>所有原始文件与生成产物位于 D:\\oly1。展示文档、录屏和源码包位于 deliverables 文件夹。队伍名称需要参赛者填写。</p><p><a href="https://tianchi.aliyun.com/competition/entrance/532503/information" target="_blank" rel="noreferrer">查看官方赛题 ↗</a></p></section>`;
    }
  } catch(err) { $('#alternate-view').innerHTML=`<div class="error-box">${e(err.message)}。请重试左侧导航。</div>`; }
}
document.addEventListener('click',async(event)=>{
  const b=event.target.closest('button'); if(!b) return;
  if(b.dataset.session) return loadSession(b.dataset.session,1);
  if(b.dataset.view) return switchView(b.dataset.view);
  if(b.dataset.filter) {state.filter=b.dataset.filter;document.querySelectorAll('.filter').forEach(x=>x.classList.toggle('active',x===b));return renderList();}
  if(b.dataset.tab) {state.tab=b.dataset.tab;document.querySelectorAll('.tab').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-selected',String(x===b));});return renderCopilot();}
  if(b.dataset.evidence) {const element=document.getElementById('message-'+b.dataset.evidence);if(element){document.querySelectorAll('.message-highlight').forEach(x=>x.classList.remove('message-highlight'));element.classList.add('message-highlight');element.scrollIntoView({behavior:'smooth',block:'center'});}return;}
  if(b.dataset.complete) {try{await api('/api/tasks/complete',{task_id:Number(b.dataset.complete)});await switchView('tasks');toast('跟进任务已标记完成');}catch(err){toast(err.message);}return;}
  if(b.dataset.openTask) {await switchView('desk');return loadSession(b.dataset.openTask,Number(b.dataset.cursor));}
  if(b.id==='adopt-reply') {$('#reply').value=state.data.analysis.reply;state.drafts[state.id]=$('#reply').value;$('#reply').focus();toast('建议已填入，您可以继续修改');}
  if(b.id==='create-task') {$('#task-title').value=state.data.analysis.action;$('#task-note').value=state.data.analysis.guard;$('#task-dialog').showModal();}
});
$('#search').addEventListener('input',renderList);
$('#prev').onclick=()=>loadSession(state.id,Math.max(1,state.cursor-1));
$('#next').onclick=()=>loadSession(state.id,Math.min(state.total,state.cursor+1));
$('#show-all').onclick=()=>loadSession(state.id,state.total);
$('#archive').onclick=()=>loadSession(state.id,state.total+1);
$('#cursor').addEventListener('input',()=>loadSession(state.id,Number($('#cursor').value)));
$('#about-button').onclick=()=>switchView('about');
$('#close-dialog').onclick=()=>$('#task-dialog').close();
$('#reply').addEventListener('input',()=>state.drafts[state.id]=$('#reply').value);
$('#send').onclick=()=>{
  const text=$('#reply').value.trim();if(!text) return toast('请先输入或采用一条回复建议');
  (state.sent[state.id]??=[]).push(text);appendSimulated(text);$('#reply').value='';state.drafts[state.id]='';
  $('#messages').scrollTop=$('#messages').scrollHeight;toast('已本地模拟发送，未联系任何消费者');
};
$('#task-form').addEventListener('submit',async(event)=>{
  event.preventDefault();const submit=event.submitter;submit.disabled=true;
  try {await api('/api/tasks',{id:state.id,cursor:state.cursor,title:$('#task-title').value,note:$('#task-note').value});$('#task-dialog').close();toast('已创建本地跟进任务；相同任务自动去重');}catch(err){toast(err.message);}finally{submit.disabled=false;}
});
$('#model-button').onclick=async()=>{
  if(!state.data||state.modelBusy) return;
  const request=state.request;state.modelBusy=true;renderCopilot();
  try {const result=await api('/api/analyze',{id:state.id,cursor:state.cursor});if(request===state.request){state.data.analysis=result;toast(result.model_error||'Qwen 分析完成，建议仍需人工审核');}}
  catch(err){toast(err.message);}finally{state.modelBusy=false;renderCopilot();}
};
$('#export-button').onclick=()=>{
  if(!state.data)return;
  const body={...state.data,local_draft:$('#reply').value,local_simulated_messages:state.sent[state.id]||[],notice:'官方MOCK数据；只导出当前回放时点'};
  const url=URL.createObjectURL(new Blob([JSON.stringify(body,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download=`zhiwei-${state.id}-${state.cursor}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
(async()=>{try{state.overview=await api('/api/overview');$('#session-count').textContent=state.overview.meta.sessions;if(state.overview.model_configured)$('#mode-label').textContent='Qwen 已配置 · 点击触发';await loadSession(state.id,1);}catch(err){$('#session-list').innerHTML=`<div class="error-box">加载失败：${e(err.message)}。请确认服务已启动并刷新页面。</div>`;}})();
