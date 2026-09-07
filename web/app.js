'use strict';

/* ============================================================
 * 知微 · 消费者服务工作台 — 前端逻辑
 * 仅与本机 server.py 通信；所有内容经 escapeHtml 输出。
 * ========================================================== */

/* ---------- 工具 ---------- */
const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (s) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
const e = escapeHtml;
const hueOf = (text) => {
  let hash = 0;
  for (const ch of String(text)) hash = (hash * 31 + ch.codePointAt(0)) % 360;
  return hash;
};

async function api(path, body) {
  const response = await fetch(path, body === undefined
    ? {}
    : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败');
  return result;
}

let toastTimer;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4000);
}

/* ---------- 状态 ---------- */
const state = {
  overview: null,        // /api/overview 结果
  id: 'S00010',          // 当前会话
  cursor: 1,             // 回放时点（total + 1 表示归档快照）
  total: 1,
  data: null,            // /api/session 结果
  tab: 'insight',        // copilot 页签
  filter: 'all',         // 列表筛选
  view: 'desk',          // 当前视图
  request: 0,            // 会话请求序号，丢弃过期响应
  drafts: {},            // 每个会话的回复草稿
  sent: {},              // 每个会话的本地模拟发送
  modelBusy: false,
};

/* ---------- 通用模板片段 ---------- */
const ORDER_INTENTS = ['订单服务', '退款打款', '补发换货', '售后退货'];
const priorityClass = (priority) => priority === '高' ? 'red' : priority === '中' ? 'gold' : 'neutral';
const pill = (text, color = 'neutral') => `<span class="pill ${color}">${e(text)}</span>`;

/* ============================================================
 * 接待列表
 * ========================================================== */
function visibleSessions() {
  const query = $('#search').value.trim().toLowerCase();
  return state.overview.sessions
    .filter((s) => `${s.id} ${s.buyer} ${s.first}`.toLowerCase().includes(query))
    .filter((s) => state.filter === 'high' ? s.priority === '高'
      : state.filter === 'order' ? ORDER_INTENTS.includes(s.intent)
      : true);
}

function sessionItemHtml(s) {
  const active = s.id === state.id;
  return `<button class="session-item ${active ? 'active' : ''}" data-session="${e(s.id)}"
      aria-pressed="${active}" ${active ? 'aria-current="true"' : ''}>
    <span class="session-avatar hue-${hueOf(s.id) % 12}">${e(s.buyer[0])}</span>
    <span class="session-body">
      <span class="session-title">${e(s.buyer)}<time>${e(s.time.slice(5, 10))} · ${s.count} 条</time></span>
      <span class="session-preview">${e(s.first)}</span>
      <span class="session-tags">${pill(s.intent)}${s.priority === '高' ? pill('高关注', 'red') : ''}</span>
    </span>
  </button>`;
}

function renderList() {
  const items = visibleSessions();
  $('#list-count').textContent = items.length;
  $('#session-list').innerHTML = items.map(sessionItemHtml).join('')
    || '<p class="empty">没有匹配的会话。试试其他关键词或筛选。</p>';
}

/* ============================================================
 * 会话加载与聊天渲染
 * ========================================================== */
async function loadSession(id, cursor) {
  if (state.data) state.drafts[state.id] = $('#reply').value;
  const request = ++state.request;
  state.id = id;
  state.cursor = cursor;
  renderList();
  $('#copilot-content').setAttribute('aria-busy', 'true');
  try {
    const result = await api(`/api/session?id=${encodeURIComponent(id)}&cursor=${cursor}`);
    if (request !== state.request) return;
    state.data = result;
    state.total = result.total;
    renderConversation();
    renderCopilot();
    $('#reply').value = state.drafts[id] || '';
  } catch (err) {
    toast(err.message);
  } finally {
    if (request === state.request) $('#copilot-content').removeAttribute('aria-busy');
  }
}

function orderCardHtml(s) {
  const o = s.orders[0];
  if (!o) {
    return `<div><h3>当前时点暂无可见订单</h3><p>咨询前置场景也能分析，不补造订单信息。</p></div>`;
  }
  return `<div>
      <h3>${e(o.product)}</h3>
      <p>订单 ${e(o.id)} · ${e(o.carrier || '物流待核实')} · ${e(o.source)}</p>
    </div>
    <div class="amount">¥${Number(o.amount).toFixed(2)}</div>`;
}

function messageHtml(m, buyer) {
  const isAgent = m.role === '客服';
  return `<article class="chat-row ${isAgent ? 'agent' : ''}" id="message-${e(m.id)}">
    <div class="chat-label">${isAgent ? '测试客服' : e(buyer)} · ${e(m.time.slice(11))}</div>
    <div class="bubble">${e(m.text)}${m.type === '图片'
      ? `<div class="image-placeholder">▧ 买家提及图片 · 原文件未提供<small>不进行图片识别或凭空核实内容</small></div>`
      : ''}</div>
  </article>`;
}

function renderConversation() {
  const s = state.data.session;
  $('#buyer-name').textContent = s.buyer;
  const avatar = $('#buyer-avatar');
  avatar.textContent = s.buyer[0];
  avatar.className = `avatar hue-${hueOf(s.id) % 12}`;
  $('#buyer-meta').textContent = `${s.id} · ${state.total} 条历史消息 · 脱敏昵称`;
  $('#order-card').innerHTML = orderCardHtml(s);

  const cursorInput = $('#cursor');
  cursorInput.max = state.total;
  cursorInput.value = Math.min(state.cursor, state.total);
  $('#replay-mode').textContent = s.archived ? '归档模式' : '历史回放';
  $('#cursor-label').textContent = s.archived ? '表格最终记录' : `${state.cursor} / ${state.total} 条`;
  $('#prev').disabled = state.cursor <= 1;
  $('#next').disabled = state.cursor >= state.total;
  $('#time-notice').textContent = s.archived
    ? '归档快照：包含聊天结束后创建的工单'
    : `当前时点 ${s.cutoff}`;

  $('#messages').innerHTML = s.messages.map((m) => messageHtml(m, s.buyer)).join('');
  for (const text of state.sent[state.id] || []) appendSimulated(text);
  $('#messages').scrollTop = $('#messages').scrollHeight;
}

function appendSimulated(text) {
  $('#messages').insertAdjacentHTML('beforeend',
    `<article class="chat-row agent simulated">
      <div class="chat-label">客服 · 本地模拟回复 · 不参与历史分析</div>
      <div class="bubble">${e(text)}</div>
    </article>`);
}

/* ============================================================
 * Copilot（即时洞察 / 服务轨迹）
 * ========================================================== */
function renderCopilot() {
  if (!state.data) return;
  const a = state.data.analysis;
  const s = state.data.session;
  $('#analysis-mode').textContent = a.mode === 'qwen'
    ? `${a.model} · ${a.cache_hit ? '缓存命中' : a.call_tokens + ' tokens'}`
    : '本地规则 · 建议需人工复核';
  $('#model-button').disabled = state.modelBusy;
  $('#model-button').textContent = state.modelBusy ? '正在分析…' : 'Qwen 分析 ↗';
  if (state.tab === 'journey') return renderJourney(s);
  renderInsight(a, s);
}

function riskCardHtml(r, s) {
  const level = (r.level === '高' ? '高' : r.level === '中' ? '中' : '') + '关注';
  const links = r.evidence_ids
    .filter((id) => s.messages.some((m) => m.id === id))
    .slice(0, 2)
    .map((id) => `<button class="evidence-link" data-evidence="${e(id)}">查看原话 ↗</button>`)
    .join(' ');
  return `<section class="risk-card ${r.level === '高' ? 'high' : ''}">
    <div class="risk-title">${e(r.title)} ${pill(level, priorityClass(r.level))}</div>
    <p>${e(r.detail)}</p>${links}
  </section>`;
}

function sourceLinkHtml(item) {
  if (item.source_type === 'message') {
    return `<button class="evidence-link" data-evidence="${e(item.source_id)}">原话 ↗</button>`;
  }
  return `<span class="source-tag">${e(item.source_type)} · ${e(item.source_id)}</span>`;
}

function serviceItemHtml(item) {
  const facts = item.known_facts.map((v) => `<li>${e(v.text)} ${sourceLinkHtml(v)}</li>`).join('');
  const handled = item.handled.map((v) => typeof v === 'string' ? `<li>${e(v)}</li>`
    : `<li>${e(v.text)} ${sourceLinkHtml(v)}</li>`).join('');
  return `<section class="service-item-card">
    <div class="section-heading"><h3>当前服务事项</h3>${pill('时点内事实', 'green')}</div>
    <dl><dt>当前诉求</dt><dd>${e(item.current_need)}</dd>
      <dt>已知事实</dt><dd><ul>${facts || '<li>当前时点暂无结构化事实</li>'}</ul></dd>
      <dt>待核实</dt><dd><ul>${item.to_verify.map((v) => `<li>${e(v)}</li>`).join('')}</ul></dd>
      <dt>已有处理</dt><dd><ul>${handled}</ul></dd>
      <dt>下一步</dt><dd>${e(item.next_step)}</dd></dl>
  </section>`;
}

function renderInsight(a, s) {
  const risks = a.risks.map((r) => riskCardHtml(r, s)).join('');
  const emotionColor = a.emotion === '负向' ? 'red' : a.emotion === '焦急' ? 'gold' : 'neutral';
  const chart = a.trend.map((t) => `<div class="emotion-step">
      <div class="emotion-bar level-${t.level}"></div><small>#${t.seq} ${e(t.emotion)}</small>
    </div>`).join('');
  const evidences = a.evidence.map((v) => `<div class="evidence-card">
      <p>${e(v.text)}</p>
      <button class="evidence-link" data-evidence="${e(v.id)}">回到对话 #${v.seq} ↗</button>
    </div>`).join('');
  $('#copilot-content').innerHTML = `
    ${a.model_error ? `<div class="error-box">${e(a.model_error)}</div>` : ''}
    ${serviceItemHtml(a.service_item)}
    <section class="insight-card">
      <div class="section-heading"><h3>即时洞察</h3></div>
      <div class="summary-tags">${pill(a.intent, 'green')}${pill('情绪 · ' + a.emotion, emotionColor)}</div>
      <p>${e(a.summary)}</p>
      <div class="emotion-chart" aria-label="买家消息情绪变化">${chart}</div>
    </section>
    <div class="section-heading"><h3>需要留意</h3><span class="muted">${a.risks.length} 项</span></div>
    ${risks || '<section class="insight-card"><p>当前未触发规则风险。</p></section>'}
    <section class="reply-card">
      <div class="section-heading"><h3>建议回应</h3>${a.reply_guard?.blocked ? pill('已安全降级', 'gold') : ''}</div>
      <p>${e(a.reply)}</p>
      ${a.reply_guard?.blocked ? `<small class="guard-reason">${e(a.reply_guard.reasons.join('；'))}</small>` : ''}
      <button id="adopt-reply">采用建议 ↙</button>
    </section>
    <div class="action-row"><h3>${e(a.action)}</h3><button id="create-task" class="primary">创建跟进</button></div>
    <div class="section-heading"><h3>买家原话</h3><span class="muted">${a.evidence.length} 条</span></div>
    ${evidences}
    <p class="guard">${e(a.guard)} ${e(a.uncertainty)}</p>`;
}

function renderJourney(s) {
  const events = [];
  s.orders.forEach((o) => {
    events.push({ time: o.created, title: '订单创建', detail: `${o.product} · ¥${o.amount}`, source: o.source });
    if (o.paid) events.push({ time: o.paid, title: '订单付款', detail: '付款时间来自订单表', source: o.source });
    if (o.shipped) events.push({ time: o.shipped, title: '订单发货', detail: `${o.carrier} · ${o.tracking}`, source: o.source });
  });
  s.messages.forEach((m) => events.push({
    time: m.time, title: m.role === '买家' ? '买家表达' : '客服回应',
    detail: m.text, source: m.source, id: m.id,
  }));
  s.tickets.forEach((t) => {
    events.push({ time: t.created, title: t.kind + '创建', detail: `${t.id} · ${t.status}`, source: t.source });
    if (t.completed) events.push({ time: t.completed, title: '工单完成', detail: t.id, source: t.source });
  });
  events.sort((x, y) => x.time.localeCompare(y.time));

  const archivedTickets = s.archived ? s.tickets.map((t) => `<section class="insight-card">
      <h3>${e(t.kind)} ${pill(t.status, 'gold')}</h3>
      <p>${e(t.id)} · ${e(t.source)}</p>
      <p>${e(t.fields['售后原因'] || t.fields['问题类型'] || t.fields['退款问题类型']
        || t.fields['症状描述'] || t.fields['退货原因'] || '详见原始表格')}</p>
    </section>`).join('') : '';

  $('#copilot-content').innerHTML = `
    <div class="section-heading"><h3>服务轨迹</h3><span class="muted">${events.length} 个节点</span></div>
    ${archivedTickets}
    <div class="timeline">${events.map((v) => `<div class="timeline-item">
        <time>${e(v.time)}</time><h3>${e(v.title)}</h3><p>${e(v.detail)}</p>
        ${v.id ? `<button class="evidence-link" data-evidence="${e(v.id)}">定位消息 ↗</button>` : ''}
      </div>`).join('')}</div>`;
}

/* ============================================================
 * 其他视图（跟进 / 洞察 / 说明）
 * ========================================================== */
function tasksViewHtml(tasks) {
  const items = tasks.map((t) => `<article class="task-item">
      <div>
        <h3>${e(t.title)} ${pill(t.status, t.status === '已完成' ? 'green' : 'gold')}</h3>
        <p>${e(t.note)}</p>
        <small>${e(t.session)} · 回放 #${t.cursor} · ${e(t.created)}</small>
      </div>
      <div>
        <button data-open-task="${e(t.session)}" data-cursor="${t.cursor}">查看会话</button>
        ${t.status !== '已完成' ? `<button class="primary" data-complete="${t.id}">标记完成</button>` : ''}
      </div>
    </article>`).join('');
  return `<section class="data-panel">
    <h3>跟进任务 <span class="count">${tasks.length}</span></h3>
    ${items || '<p class="empty">还没有跟进任务。在右侧辅助区创建一条，经确认后会显示在这里。</p>'}
  </section>`;
}

function metricsViewHtml(v) {
  const release = v.release_summary;
  const challenge = release?.challenge_metrics;
  const table = v.by_class
    ? `<table><thead><tr><th>官方场景</th><th>样本</th><th>正确</th><th>召回率</th></tr></thead>
       <tbody>${v.by_class.map((c) => `<tr>
          <td>${e(c.label)}</td><td>${c.support}</td><td>${c.correct}</td><td>${(c.recall * 100).toFixed(1)}%</td>
        </tr>`).join('')}</tbody></table>`
    : '<p>请运行 python scripts/evaluate.py 生成报告。</p>';
  return `<div class="stats-grid">
      <div class="stat-tile"><small>官方会话</small><b>138</b><small>10 类主场景</small></div>
      <div class="stat-tile"><small>聊天消息</small><b>998</b><small>按回放时点过滤</small></div>
      <div class="stat-tile"><small>订单 / 工单</small><b>113 / 80</b><small>按会话 ID 对齐</small></div>
      <div class="stat-tile"><small>首条消息意图准确率</small>
        <b>${v.accuracy == null ? '待评估' : (v.accuracy * 100).toFixed(1) + '%'}</b>
        <small>同源 MOCK 诊断集，非独立测试集</small></div>
    </div>
    ${challenge ? `<section class="data-panel"><h3>独立 Challenge Set <span class="count">50</span></h3>
      <p class="muted">人工编写语义边界集，与官方 138 会话分开；版本 ${e(release.version)}。</p>
      <div class="summary-tags">${pill('Intent ' + (challenge.intent_accuracy*100).toFixed(1) + '%','green')}
        ${pill('Risk Recall ' + (challenge.risk_recall*100).toFixed(1) + '%','green')}
        ${pill('Evidence ' + (challenge.evidence_support_rate*100).toFixed(1) + '%','green')}
        ${pill('Unsafe ' + (challenge.unsafe_commitment_recall*100).toFixed(1) + '%','green')}</div>
    </section>` : ''}
    <section class="data-panel"><h3>各场景识别情况</h3>
      <p class="muted">场景标签只用于离线评估，不进入规则或模型输入。</p>${table}
    </section>`;
}

function aboutViewHtml() {
  return `<section class="data-panel"><h3>使用说明</h3>
      <p>① 左侧选择会话，可搜索或筛选高关注内容。</p>
      <p>② 拖动聊天上方进度条回放历史，观察风险与建议随消息推进的变化。</p>
      <p>③ 右侧查看洞察与服务轨迹，采用建议后编辑回复；模拟发送仅保存在本页。</p>
      <p>④ 「创建跟进」经确认后写入本机 SQLite，在跟进页可查看与标记完成。</p>
    </section>
    <section class="data-panel"><h3>说明</h3>
      <p>默认离线规则分析。配置服务端环境变量 DASHSCOPE_API_KEY（可选 QWEN_BASE_URL、QWEN_MODEL）并重启后，可点击「Qwen 分析」；失败时明确降级，不伪称模型结果。</p>
      <p>本页面为官方虚构数据的本地竞赛 Demo，未连接真实千牛、支付或物流系统。
        <a href="https://tianchi.aliyun.com/competition/entrance/532503/information" target="_blank" rel="noreferrer">官方赛题 ↗</a></p>
    </section>`;
}

async function switchView(view) {
  state.view = view;
  document.querySelectorAll('[data-view]').forEach((b) =>
    b.classList.toggle('selected', b.dataset.view === view));
  $('#desk-view').hidden = view !== 'desk';
  $('#alternate-view').hidden = view === 'desk';
  if (view === 'desk') return;
  $('#alternate-view').innerHTML = '<p class="empty">正在载入…</p>';
  try {
    if (view === 'tasks') {
      const data = await api('/api/tasks');
      if (state.view !== view) return;
      $('#alternate-view').innerHTML = tasksViewHtml(data.tasks);
    } else if (view === 'metrics') {
      const v = await api('/api/evaluation');
      if (state.view !== view) return;
      $('#alternate-view').innerHTML = metricsViewHtml(v);
    } else {
      $('#alternate-view').innerHTML = aboutViewHtml();
    }
  } catch (err) {
    $('#alternate-view').innerHTML = `<div class="error-box">${e(err.message)}。请重试左侧导航。</div>`;
  }
}

/* ============================================================
 * 事件
 * ========================================================== */
function highlightMessage(id) {
  const element = document.getElementById('message-' + id);
  if (!element) return;
  document.querySelectorAll('.message-highlight').forEach((x) => x.classList.remove('message-highlight'));
  element.classList.add('message-highlight');
  element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(() => element.classList.remove('message-highlight'), 4000);
}

document.addEventListener('click', async (event) => {
  const b = event.target.closest('button');
  if (!b) return;
  if (b.dataset.session) return loadSession(b.dataset.session, 1);
  if (b.dataset.view) return switchView(b.dataset.view);
  if (b.dataset.filter) {
    state.filter = b.dataset.filter;
    document.querySelectorAll('.filter').forEach((x) => x.classList.toggle('active', x === b));
    return renderList();
  }
  if (b.dataset.tab) {
    state.tab = b.dataset.tab;
    document.querySelectorAll('.tab').forEach((x) => {
      x.classList.toggle('active', x === b);
      x.setAttribute('aria-selected', String(x === b));
    });
    return renderCopilot();
  }
  if (b.dataset.evidence) return highlightMessage(b.dataset.evidence);
  if (b.dataset.complete) {
    try {
      await api('/api/tasks/complete', { task_id: Number(b.dataset.complete) });
      await switchView('tasks');
      toast('跟进任务已标记完成');
    } catch (err) { toast(err.message); }
    return;
  }
  if (b.dataset.openTask) {
    await switchView('desk');
    return loadSession(b.dataset.openTask, Number(b.dataset.cursor));
  }
  if (b.id === 'adopt-reply') {
    $('#reply').value = state.data.analysis.reply;
    state.drafts[state.id] = $('#reply').value;
    $('#reply').focus();
    toast('建议已填入，您可以继续修改');
  }
  if (b.id === 'create-task') {
    $('#task-title').value = state.data.analysis.action;
    $('#task-note').value = state.data.analysis.guard;
    $('#task-dialog').showModal();
  }
});

async function sendReply() {
  const text = $('#reply').value.trim();
  if (!text) return toast('请先输入或采用一条回复建议');
  try {
    const checked = await api('/api/reply/guard', { id: state.id, cursor: state.cursor, reply: text });
    if (checked.blocked) {
      $('#reply').value = checked.reply;
      state.drafts[state.id] = checked.reply;
      toast(`已拦截无依据承诺：${checked.reasons.join('；')}。请确认安全版本后再次发送`);
      return;
    }
    (state.sent[state.id] ??= []).push(checked.reply);
    appendSimulated(checked.reply);
    $('#reply').value = '';
    state.drafts[state.id] = '';
    $('#messages').scrollTop = $('#messages').scrollHeight;
    toast('已通过承诺检查并本地模拟发送，未联系任何消费者');
  } catch (err) { toast(err.message); }
}

$('#search').addEventListener('input', renderList);
$('#prev').onclick = () => loadSession(state.id, Math.max(1, state.cursor - 1));
$('#next').onclick = () => loadSession(state.id, Math.min(state.total, state.cursor + 1));
$('#show-all').onclick = () => loadSession(state.id, state.total);
$('#archive').onclick = () => loadSession(state.id, state.total + 1);
$('#cursor').addEventListener('input', () => loadSession(state.id, Number($('#cursor').value)));
$('#about-button').onclick = () => switchView('about');
$('#close-dialog').onclick = () => $('#task-dialog').close();
$('#reply').addEventListener('input', () => { state.drafts[state.id] = $('#reply').value; });
$('#reply').addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') sendReply();
});
$('#send').onclick = sendReply;

$('#task-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const submit = event.submitter;
  submit.disabled = true;
  try {
    await api('/api/tasks', {
      id: state.id, cursor: state.cursor,
      title: $('#task-title').value, note: $('#task-note').value,
    });
    $('#task-dialog').close();
    toast('已创建本地跟进任务；相同任务自动去重');
  } catch (err) {
    toast(err.message);
  } finally {
    submit.disabled = false;
  }
});

$('#model-button').onclick = async () => {
  if (!state.data || state.modelBusy) return;
  const request = state.request;
  state.modelBusy = true;
  renderCopilot();
  try {
    const result = await api('/api/analyze', { id: state.id, cursor: state.cursor });
    if (request === state.request) {
      state.data.analysis = result;
      toast(result.model_error || 'Qwen 分析完成，建议仍需人工审核');
    }
  } catch (err) {
    toast(err.message);
  } finally {
    state.modelBusy = false;
    renderCopilot();
  }
};

$('#export-button').onclick = () => {
  if (!state.data) return;
  const body = {
    ...state.data,
    local_draft: $('#reply').value,
    local_simulated_messages: state.sent[state.id] || [],
    notice: '官方MOCK数据；只导出当前回放时点',
  };
  const url = URL.createObjectURL(new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = `zhiwei-${state.id}-${state.cursor}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};

/* ============================================================
 * 启动
 * ========================================================== */
(async () => {
  try {
    state.overview = await api('/api/overview');
    $('#session-count').textContent = state.overview.meta.sessions;
    if (state.overview.model_configured) $('#mode-label').textContent = 'Qwen 已配置 · 点击触发';
    await loadSession(state.id, 1);
  } catch (err) {
    $('#session-list').innerHTML =
      `<div class="error-box">加载失败：${e(err.message)}。请确认服务已启动并刷新页面。</div>`;
  }
})();
