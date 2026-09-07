"""Versioned business definitions, independent of evaluation sample labels."""
import re

VERSION = 'business-intent-v2'
DEFINITIONS = {
    '不良反应': '主要诉求是使用后的健康不适处理，如泛红刺痒、过敏就医、闷痘爆痘。不要仅因提及敏感肌或询问成分就判此类。',
    '产品咨询': '购买决策或使用知识：套装推荐、正品咨询、优惠赠品咨询、色号选择、肤质成分、比价、使用方法、孕妇能否使用。仅问候没有主诉时待确认。',
    '会员服务': '积分兑换、会员等级及权益规则咨询。已购订单缺少会员赠品属于补发换货。',
    '其他服务': '好评回访、致谢反馈等非交易服务；不要把无法判断的对话全部归到此类。',
    '售后退货': '主要请求退货/仅退款/拒收，包含七天无理由、使用不适退货、质疑假货、自己选错色号、拆封少件拒收。使用不适风险另行保留。',
    '物流异常': '履约运输异常：显示签收未收到、包裹破损、包裹少件、停滞疑似丢件、拦截改址。后来客服决定补发或退款不改变原始主诉。',
    '物流服务': '正常物流查询、催发货、索要单号；只有等待或询问时间，不足以推断丢件。',
    '补发换货': '商品交付差错或功能破损：泵头损坏要求处理、卖家发错色号、少发正装、漏发赠品、会员赠品补发。买家自己选错不等于卖家发错。',
    '订单服务': '订单流程：预售尾款、退款进度/退款未到账、价保资格或申请被拒、直播间承诺纠纷、发票申请。普通退款进度不是补打款。',
    '退款打款': '需单独核对补打款的诉求：少退漏退金额、退货运费报销、价保补差款、售后入口关闭需线下退款。不能见到退款二字就判此类。',
    '待确认': '可见买家信息只有问候、表情或无明确需求，不能根据商品、客服营销话术或未来消息猜测主诉。',
}


def prompt_taxonomy():
    return '\n'.join(f'- {name}：{definition}' for name, definition in DEFINITIONS.items())


def strong_anchor(messages):
    """A narrow evidence rule for preserving reliable baseline decisions.

    Stop at the first substantive buyer turn; later resolutions must not reclassify it.
    No order IDs, sample IDs, gold labels or model confidence scores are used.
    """
    from src.engine import infer_intent
    for message in messages:
        if message['role'] != '买家':
            continue
        text = message['text']
        if infer_intent([message]) == '待确认':
            continue
        anchors = [
            ('退款打款', r'少退|漏退|报销|退运费|售后.*关|线下.*退|补差'),
            ('订单服务', r'退款.*(到账|没到|未到|进度|哪去|成功)|原路退回|发票|尾款|预售|直播|主播'),
            ('售后退货', r'退货|无理由|仅退款|拒收|假货'),
            ('补发换货', r'漏发|少发|补发|错发|发错|泵头|赠品.*(没|少|漏)'),
            ('物流异常', r'签收.*(没|未).*收|包裹.*(破|碎|少件)|拦截|改址|地址填错|停滞|丢件'),
            ('会员服务', r'积分.*兑换'),
        ]
        for label, pattern in anchors:
            if re.search(pattern, text):
                return label, message['id']
        return None, None
    return None, None
