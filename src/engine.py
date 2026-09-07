"""Evidence-first deterministic baseline. Evaluation labels are never read here."""
from copy import deepcopy
import re

INTENTS = [
    ('不良反应', ['过敏', '红肿', '脸肿', '医院', '就医', '刺痒', '发红', '刺痛', '爆痘', '起疹', '瘙痒', '闷痘']),
    ('退款打款', ['到账', '打款', '补差', '价保', '保价', '少退', '漏退', '运费报销', '退运费', '退款进度', '退款怎么']),
    ('补发换货', ['漏发', '少发', '补发', '换货', '错发', '发错', '泵头', '加赠', '少了赠品']),
    ('售后退货', ['退货', '无理由', '仅退款', '空包', '退款', '拒收']),
    ('物流异常', ['没收到', '未收到', '不动', '停滞', '丢件', '破损', '碎了', '少件', '拦截', '改址', '签收了']),
    ('会员服务', ['积分', '会员等级', '会员权益', '会员怎么']),
    ('其他服务', ['发票', '好评', '回访']),
    ('订单服务', ['发货', '尾款', '预售', '取消订单', '地址', '订单', '付款']),
    ('物流服务', ['物流', '快递', '包裹', '到哪', '什么时候到']),
    ('产品咨询', ['精华', '面霜', '色号', '肤质', '敏感肌', '孕妇', '成分', '怎么用', '正品', '优惠', '赠品', '套装', '区别', '防晒', '推荐'])
]
NEGATIVE = ['投诉', '曝光', '差评', '骗人', '生气', '无语', '气死', '太差', '失望', '12315']
URGENT = ['急', '尽快', '还没', '多久', '一直', '催', '到底', '迟迟', '等了']
PATTERNS = [
    ('不良反应', r'过敏|红肿|脸肿|医院|就医|刺痒|发红|刺痛|爆痘|红疹|起.*疹|瘙痒|闷痘|针扎|眼皮.*鼓'),
    ('退款打款', r'补差|少退|漏退|报销|少了[\d.]+块|售后.*关|钱退不出|线下.*退|打款'),
    ('订单服务', r'尾款|预售|发票|降价|直播|主播|退款.*(到|进度|银行)|原路退回|订单号'),
    ('售后退货', r'退货|无理由|仅退款|空包|拒收|能退|想退|假货'),
    ('补发换货', r'漏发|少发|补发|换货|错发|发错|泵头|加赠|赠品.*(没|少|漏)|买.{0,8}(色|号).*收到|买的.*发来|拍的是.*收到|色差'),
    ('物流异常', r'没收到|未收到|不动|停滞|丢件|丢了|破损|碎了|少件|拦截|改址|地址填错|里面少了|两件.*一件|签收了'),
    ('会员服务', r'积分|会员等级|会员权益'),
    ('其他服务', r'夸夸|好评|回访'),
    ('物流服务', r'物流|快递|包裹|到哪|什么时候到|发货|单号'),
    ('订单服务', r'取消订单|付款|订单'),
    ('产品咨询', r'精华|面霜|色号|肤质|敏感肌|孕妇|成分|怎么用|正品|优惠|赠品|套装|区别|防晒|推荐|假的|眼影|唇|适合|顺序|酒精|香精')
]

POLICIES = {
    '不良反应': ('优先转专员核实', '记录买家自述、不适时间与已采取措施；不作诊断，不承诺医疗赔偿。', '看到您反馈使用后不适，我理解您的担心。我会优先转交售后专员，核实您已提供的信息，避免让您重复描述。'),
    '退款打款': ('核实退款与打款记录', '对齐原订单、退款编号和实际进度，重复付款前须人工复核。', '理解您一直等待退款的着急。我会先核对当前可见的订单及退款记录，确认进度后再向您反馈。'),
    '补发换货': ('核实商品与补发记录', '核对商品、数量、原物流与补发物流；已有工单优先跟进，避免重复补发。', '给您带来不便了。我会先核对收到的商品及当前可见售后记录，再为您确认下一步处理方案。'),
    '售后退货': ('核实退货条件与进度', '结合订单与现有售后工单确认流程，不凭关键词判定欺诈或自动拒绝。', '理解您希望尽快处理售后的心情。我会结合当前可见订单和已有记录核实处理进度，避免让您重复提供已有信息。'),
    '物流异常': ('核实异常包裹', '以对应物流单号联系物流专员；先核实再承诺补发或退款。', '理解您对包裹情况的担心。我会先核实当前可见物流和异常记录，再向您反馈处理进展。'),
}


def snapshot(session, cursor):
    s = deepcopy(session)
    s.pop('label', None); s.pop('minor_label', None)
    if cursor == len(s['messages']) + 1:
        s['archived'] = True
        s['cutoff'] = '归档快照（表格最终记录；非历史回放）'
        return s
    s['archived'] = False
    s['messages'] = s['messages'][:max(0, cursor)]
    cutoff = s['messages'][-1]['time'] if s['messages'] else ''
    s['cutoff'] = cutoff
    s['orders'] = [o for o in s['orders'] if o['created'] <= cutoff]
    for o in s['orders']:
        o['status'] = '历史状态待核实（无状态变更日志）'
        if not o.get('shipped') or o['shipped'] > cutoff:
            o['shipped'] = None; o['tracking'] = ''; o['carrier'] = None
        if o.get('paid') and o['paid'] > cutoff: o['paid'] = None
    s['tickets'] = [t for t in s['tickets'] if t['created'] <= cutoff]
    for t in s['tickets']:
        t['fields'] = {k: v for k, v in t.get('fields', {}).items()
                       if k in ('工单号', '会话ID', '关联订单号', '买家昵称', '店铺', '创建时间')}
        if not t.get('completed') or t['completed'] > cutoff:
            t['status'] = '历史状态待核实'; t['completed'] = None
        else: t['status'] = '已完成（依据完成时间）'
    return s


def _semantic_state(text, start, end, kind):
    before, after = text[max(0, start - 12):start], text[end:end + 12]
    nearby = before + text[start:end] + after
    if re.search(r'(没有|没发生|未发生|从未|并未|不是|无|没).{0,5}' + ('投诉' if kind == 'complaint' else r'(过敏|不适|红肿|红疹|起疹)'), nearby):
        return '否定'
    if kind == 'health' and re.search(r'(红|肿|痒|疹|刺痛|针扎)', nearby) and re.search(r'(额头|脸|眼皮|皮肤|身上|昨晚|今早|用后|用了)', text):
        return '实际发生'
    if re.search(r'(会不会|是否会|会引起|会导致|可能会|担心|想问|咨询|如果|假如).{0,10}', before + text[start:end]) or re.search(r'(吗|么|？|\?)', after[:4]):
        return '假设/咨询'
    if re.search(r'(以前|之前|曾经|过去).{0,8}$', before):
        return '既往情况'
    # Symptom descriptions are intentionally routed for verification even without an explicit causal phrase.
    if kind == 'health' and not re.search(r'用了|用后|使用后|涂了|擦了|敷了|喝了|吃了|脸上|眼皮|皮肤|身上|医院|就医', nearby):
        return '待核实'
    return '实际发生'


def detect_risk(messages):
    """One matching pass emits semantics, level and the exact supporting message IDs."""
    signals = []
    specs = [
        ('health', '使用不适需优先关注', PATTERNS[0][1]),
        ('complaint', '投诉或负向表达', r'投诉|曝光|差评|12315'),
    ]
    for m in messages:
        if m.get('role') != '买家': continue
        for kind, title, pattern in specs:
            matches = list(re.finditer(pattern, m.get('text', '')))
            if not matches: continue
            states = [_semantic_state(m['text'], x.start(), x.end(), kind) for x in matches]
            # Prefer an actual occurrence if a sentence contains several mentions.
            state = next((x for x in states if x == '实际发生'), states[0])
            actionable = state in ('实际发生', '待核实', '既往情况')
            level = '高' if state == '实际发生' else '中' if actionable else '提示'
            detail = ({
                '实际发生': '买家当前自述，需人工核实；该判断仅作服务分流依据。',
                '待核实': '出现相关线索但语境不足，按高关注线索人工核实，不作事实结论。',
                '既往情况': '买家提及既往情况，需确认是否与当前诉求相关。',
                '否定': '买家明确否定该情况，不作为已发生风险。',
                '假设/咨询': '买家是在咨询可能性，不作为已发生风险。',
            })[state]
            signals.append({'risk_type': kind, 'title': title, 'semantic_state': state,
                            'detail': detail, 'level': level, 'evidence_ids': [m['id']],
                            'actionable': actionable})
    return signals


def infer_intent(buyers):
    for message in buyers:
        health_signals = [x for x in detect_risk([message]) if x['risk_type'] == 'health']
        if re.search(r'(咨询|想问).{0,4}(如果|假如).*(丢件|补发)', message['text']):
            return '物流服务'
        for label, pattern in PATTERNS:
            if label == '不良反应' and health_signals and not any(
                    x['semantic_state'] in ('实际发生', '待核实') for x in health_signals):
                continue
            if re.search(pattern, message['text']): return label
    return '待确认'


def emotion(text):
    if any(w in text for w in NEGATIVE): return '负向', 3
    if any(w in text for w in URGENT): return '焦急', 2
    if any(w in text for w in ['谢谢', '满意', '感谢', '好评']): return '缓和', 0
    return '平稳', 1


def _emotion_escalation(buyers, trend):
    if len(buyers) < 2: return None
    visible = []
    for m in buyers:
        if any(w in m['text'] for w in NEGATIVE + URGENT): visible.append(m['id'])
    repeated = sum(any(w in m['text'] for w in URGENT) for m in buyers) >= 2
    conflict = any(any(w in m['text'] for w in NEGATIVE) for m in buyers[1:])
    if (repeated or conflict) and visible:
        return {'risk_type': 'emotion_escalation', 'title': '情绪有升级迹象', 'semantic_state': '实际发生',
                'detail': '可见连续催促或明确负向表达，建议优先解释当前进度。', 'level': '中',
                'evidence_ids': visible[-2:], 'actionable': True}
    return None


def _service_item(s, buyers, intent, action):
    known = []
    for m in buyers:
        if re.search(r'(订单号|单号)[是：:\s]*[A-Za-z0-9-]{4,}', m['text']):
            known.append({'text': '买家已提供订单/单号', 'source_type': 'message', 'source_id': m['id']})
    for o in s['orders']:
        known.append({'text': f"可见订单：{o.get('product', '商品待核实')}（{o.get('id', '编号待核实')}）", 'source_type': 'order', 'source_id': o.get('id', '')})
    for t in s['tickets']:
        known.append({'text': f"可见{t.get('kind', '工单')}：{t.get('status', '状态待核实')}", 'source_type': 'ticket', 'source_id': t.get('id', '')})
    need_order = intent in ('订单服务', '退款打款', '补发换货', '售后退货', '物流异常', '物流服务')
    missing = []
    if need_order and not s['orders'] and not any('订单/单号' in x['text'] for x in known):
        missing.append('关联订单或可查询单号')
    if intent == '不良反应': missing.append('不适出现时间及目前情况')
    handled = [{'text': f"已有{t.get('kind', '工单')}，优先核对避免重复创建", 'source_type': 'ticket', 'source_id': t.get('id', '')} for t in s['tickets']]
    return {'current_need': intent if intent != '待确认' else '具体诉求待确认', 'known_facts': known,
            'to_verify': missing or ['当前处理状态与消费者期望结果'], 'handled': handled or ['当前时点未见可确认的已执行处理'],
            'next_step': action}


def has_execution_basis(s, commitment_type):
    keywords = {'refund': ('退款', '打款', '转账'), 'reship': ('补发',), 'complete': ('完成', '完结')}.get(commitment_type, ())
    for t in s.get('tickets', []):
        corpus = t.get('kind', '') + t.get('status', '') + ' '.join(map(str, t.get('fields', {}).values()))
        if any(k in corpus for k in keywords) and ('已完成' in corpus or '成功' in corpus or t.get('completed')):
            return True
    return False


def guard_reply(reply, s):
    """Downgrade unsupported execution claims and return auditable reasons."""
    reasons = []
    checks = [
        ('refund', r'已(?:经)?(?:为您)?(?:完成|线下)?(?:退款|打款)|退款已(?:完成|成功)|已经退款'),
        ('reship', r'已(?:为您)?补发|已经补发'),
        ('complete', r'已(?:为您)?完成|已经完成'),
    ]
    for kind, pattern in checks:
        if re.search(pattern, reply) and not has_execution_basis(s, kind): reasons.append('缺少可见执行回执：' + kind)
    if re.search(r'保证|一定(?:会)?到账|肯定到账|明天到账|\d{1,2}月\d{1,2}日到账|\d+个?工作日(?:内)?到账', reply):
        reasons.append('包含无依据的保证或具体到账时效')
    if re.search(r'(赔付|赔偿|补偿)\s*(?:人民币|¥|￥)?\s*\d+(?:\.\d+)?\s*元?', reply):
        reasons.append('包含无可见政策依据的赔付金额')
    if not reasons: return {'reply': reply, 'blocked': False, 'reasons': []}
    return {'reply': '我先为您核实相关记录和当前处理进度，确认后再同步可核实的结果与时间。',
            'blocked': True, 'reasons': list(dict.fromkeys(reasons))}


def analyze(session, cursor):
    s = snapshot(session, cursor)
    buyers = [m for m in s['messages'] if m['role'] == '买家']
    intent = infer_intent(buyers)
    trend = [{'seq': m['seq'], 'emotion': emotion(m['text'])[0], 'level': emotion(m['text'])[1]} for m in buyers]
    current = trend[-1]['emotion'] if trend else '待判断'
    signals = detect_risk(buyers)
    risks = [x for x in signals if x['actionable']]
    escalation = _emotion_escalation(buyers, trend)
    if escalation: risks.append(escalation)
    repeat_words = ['又来', '问过', '好几次', '上次', '再次', '重复']
    repeat_ids = [m['id'] for m in buyers if any(w in m['text'] for w in repeat_words)]
    if repeat_ids:
        risks.append({'risk_type': 'repeat_contact', 'title': '疑似重复进线', 'semantic_state': '待核实',
                      'detail': '仅来自当前会话自述；脱敏昵称不能证明跨会话为同一人。', 'level': '中',
                      'evidence_ids': repeat_ids, 'actionable': True})
    if s['tickets']:
        risks.append({'risk_type': 'linked_ticket', 'title': '存在关联工单', 'semantic_state': '实际发生',
                      'detail': '继续操作前核对原工单，避免重复创建或重复赔付。', 'level': '中',
                      'evidence_ids': [t['id'] for t in s['tickets']], 'actionable': True})
    # Every displayed deterministic risk has evidence from the exact matching pass.
    risks = [r for r in risks if r['evidence_ids']]
    health_gate = any(r['risk_type'] == 'health' and r['semantic_state'] in ('实际发生', '待核实') for r in risks)
    priority = '高' if health_gate or any(r['level'] == '高' for r in risks) else '中' if risks or current == '焦急' else '普通'
    routing = '不良反应' if health_gate else intent
    action, policy_guard, reply = POLICIES.get(routing, ('核实需求并提供信息', '先澄清具体问题；产品功效、活动规则与发货时效应以经审核资料为准。', '收到您的咨询。我会先确认您的具体需求和相关信息，再为您提供准确的说明。'))
    guarded = guard_reply(reply, s)
    evidence = [{'id': m['id'], 'source': m.get('source', ''), 'text': m['text'], 'seq': m['seq']} for m in buyers]
    summary = f"当前可见 {len(s['messages'])} 条消息，{len(s['orders'])} 笔订单，{len(s['tickets'])} 张工单。"
    if buyers: summary += ' 买家最近表示：' + buyers[-1]['text'][:120]
    return {'mode': 'rules', 'intent': intent, 'emotion': current, 'priority': priority, 'summary': summary,
            'risks': risks, 'risk_signals': signals, 'trend': trend, 'evidence': evidence, 'action': action,
            'guard': policy_guard, 'reply': guarded['reply'], 'reply_guard': guarded,
            'service_item': _service_item(s, buyers, intent, action), 'human_required': True,
            'uncertainty': '关键词规则基线，非模型置信度；请结合原文复核。',
            'trace': [{'step': '数据对齐', 'detail': '按会话 ID 关联聊天、订单、工单'},
                      {'step': '时点过滤', 'detail': s['cutoff'] or '无可见消息'},
                      {'step': '风险与证据同源', 'detail': '同一次语义匹配产生状态、等级与引用'},
                      {'step': '回复安全门', 'detail': '无回执的执行承诺降级为核实表达'},
                      {'step': '人工确认', 'detail': '回复和后续操作由客服决定'}]}
