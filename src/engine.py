"""Evidence-first deterministic baseline. Evaluation labels are never read here."""
from copy import deepcopy
import re

# Ordered by safety/business specificity, evaluated against buyer text only.
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
    ('不良反应', r'过敏|红肿|脸肿|医院|就医|刺痒|发红|刺痛|爆痘|起.*疹|瘙痒|闷痘'),
    ('退款打款', r'补差|少退|漏退|报销|少了[\d.]+块|售后.*关|钱退不出|线下.*退|打款'),
    ('订单服务', r'尾款|预售|发票|降价|直播|主播|退款.*(到|进度|银行)|原路退回'),
    ('售后退货', r'退货|无理由|仅退款|空包|拒收|能退|想退|假货'),
    ('补发换货', r'漏发|少发|补发|换货|错发|发错|泵头|加赠|赠品.*(没|少|漏)|买的.*发来|拍的是.*收到|色差'),
    ('物流异常', r'没收到|未收到|不动|停滞|丢件|丢了|破损|碎了|少件|拦截|改址|地址填错|里面少了|两件.*一件|签收了'),
    ('会员服务', r'积分|会员等级|会员权益'),
    ('其他服务', r'夸夸|好评|回访'),
    ('物流服务', r'物流|快递|包裹|到哪|什么时候到|发货|单号'),
    ('订单服务', r'取消订单|付款|订单'),
    ('产品咨询', r'精华|面霜|色号|肤质|敏感肌|孕妇|成分|怎么用|正品|优惠|赠品|套装|区别|防晒|推荐|假的|眼影|唇|适合|顺序|酒精|香精')
]


def infer_intent(buyers):
    # Infer the first substantive request instead of letting a later “谢谢/退款” erase it.
    for message in buyers:
        for label, pattern in PATTERNS:
            if re.search(pattern, message['text']):
                return label
    return '待确认'
POLICIES = {
    '不良反应': ('优先转专员核实', '记录买家自述、不适时间与已采取措施；不作诊断，不承诺医疗赔偿。', '看到您反馈使用后不适，我理解您的担心。我会优先转交售后专员，核实您已提供的信息，避免让您重复描述。'),
    '退款打款': ('核实退款与打款记录', '对齐原订单、退款编号和实际进度，重复付款前须人工复核。', '理解您一直等待退款的着急。我会先核对订单及退款记录，确认目前进度后给您明确反馈。'),
    '补发换货': ('核实商品与补发记录', '核对商品、数量、原物流与补发物流；已有工单优先跟进，避免重复补发。', '给您带来不便了。我会先核对收到的商品及现有售后记录，为您确认下一步处理方案。'),
    '售后退货': ('核实退货条件与进度', '结合订单与现有售后工单确认流程，不凭关键词判定欺诈或自动拒绝。', '理解您希望尽快处理售后的心情。我会结合订单和已有记录核实处理进度，尽量减少您的重复操作。'),
    '物流异常': ('核实异常包裹', '以对应物流单号联系物流专员；先核实再承诺补发或退款。', '理解您对包裹情况的担心。我会先核实对应物流单号和异常记录，再向您反馈处理进展。'),
}


def snapshot(session, cursor):
    s = deepcopy(session)
    s.pop('label', None)
    s.pop('minor_label', None)
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
            o['shipped'] = None
            o['tracking'] = ''
            o['carrier'] = None
        if o.get('paid') and o['paid'] > cutoff:
            o['paid'] = None
    s['tickets'] = [t for t in s['tickets'] if t['created'] <= cutoff]
    for t in s['tickets']:
        # Snapshot fields may have been written later. Only identity/create-time fields are safe.
        t['fields'] = {k: v for k, v in t.get('fields', {}).items()
                       if k in ('工单号', '会话ID', '关联订单号', '买家昵称', '店铺', '创建时间')}
        if not t.get('completed') or t['completed'] > cutoff:
            t['status'] = '历史状态待核实'
            t['completed'] = None
        else:
            t['status'] = '已完成（依据完成时间）'
    return s


def emotion(text):
    if any(w in text for w in NEGATIVE):
        return '负向', 3
    if any(w in text for w in URGENT):
        return '焦急', 2
    if any(w in text for w in ['谢谢', '满意', '感谢', '好评']):
        return '缓和', 0
    return '平稳', 1


def analyze(session, cursor):
    s = snapshot(session, cursor)
    buyers = [m for m in s['messages'] if m['role'] == '买家']
    text = '\n'.join(m['text'] for m in buyers)
    intent = infer_intent(buyers)
    trend = [{'seq': m['seq'], 'emotion': emotion(m['text'])[0], 'level': emotion(m['text'])[1]} for m in buyers]
    current = trend[-1]['emotion'] if trend else '待判断'
    risks = []
    def risk(title, detail, level, keywords):
        evidence = [m['id'] for m in buyers if any(w in m['text'] for w in keywords)]
        risks.append({'title': title, 'detail': detail, 'level': level, 'evidence_ids': evidence})
    if re.search(PATTERNS[0][1], text):
        risk('使用不适需优先关注', '买家自述，仅作服务分流依据；转人工专员核实。', '高', INTENTS[0][1])
    if any(w in text for w in NEGATIVE):
        risk('投诉或负向表达', '存在投诉相关表达，不能据此断定投诉已经发生。', '高', NEGATIVE)
    if len(trend) > 1 and trend[-1]['level'] > trend[0]['level']:
        risk('情绪有升级迹象', '末条买家消息比首条更焦急或负向，建议优先解释进度。', '中', NEGATIVE + URGENT)
    if any(w in text for w in ['又来', '问过', '好几次', '上次', '再次', '重复']):
        risk('疑似重复进线', '仅来自当前会话自述；脱敏昵称不能证明跨会话为同一人。', '中', ['又来', '问过', '好几次', '上次', '再次', '重复'])
    if s['tickets']:
        risks.append({'title': '存在关联工单', 'detail': '继续操作前核对原工单，避免重复创建或重复赔付。', 'level': '中', 'evidence_ids': [t['id'] for t in s['tickets']]})
    priority = '高' if any(r['level'] == '高' for r in risks) else '中' if risks or current == '焦急' else '普通'
    routing = '不良反应' if any(r['title'] == '使用不适需优先关注' for r in risks) else intent
    action, guard, reply = POLICIES.get(routing, ('核实需求并提供信息', '先澄清具体问题；产品功效、活动规则与发货时效应以经审核资料为准。', '收到您的咨询。我会先确认您的具体需求和相关信息，再为您提供准确的说明。'))
    evidence = [{'id': m['id'], 'source': m.get('source', ''), 'text': m['text'], 'seq': m['seq']} for m in buyers]
    summary = f"当前可见 {len(s['messages'])} 条消息，{len(s['orders'])} 笔订单，{len(s['tickets'])} 张工单。"
    if buyers:
        summary += ' 买家最近表示：' + buyers[-1]['text'][:120]
    return {'mode': 'rules', 'intent': intent, 'emotion': current, 'priority': priority,
            'summary': summary, 'risks': risks, 'trend': trend, 'evidence': evidence,
            'action': action, 'guard': guard, 'reply': reply, 'human_required': True,
            'uncertainty': '关键词规则基线，非模型置信度；请结合原文复核。',
            'trace': [{'step': '数据对齐', 'detail': '按会话 ID 关联聊天、订单、工单'},
                      {'step': '时点过滤', 'detail': s['cutoff'] or '无可见消息'},
                      {'step': '意图与风险', 'detail': '仅使用可见买家原文，不读取场景标签'},
                      {'step': '人工确认', 'detail': '回复和后续操作由客服决定'}]}
