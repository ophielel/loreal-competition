"""Build the frozen, independently stored synthetic challenge set.

Each boundary case below was manually authored and reviewed against the published
business definitions. It is intentionally separate from the 138 official sessions.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# text, expected intent, expected risk semantic state (or none), candidate reply, should block
CASES = [
('我没有过敏，只想问面霜成分。','产品咨询','否定','我先为您核实成分信息。',False),
('这款精华会不会引起过敏？','产品咨询','假设/咨询','建议先核实配方与您的肤质。',False),
('以前有过敏史，现在想咨询敏感肌能用吗？','产品咨询','既往情况','我先为您核实配方信息。',False),
('用了以后脸上像针扎，眼皮也鼓了。','不良反应','实际发生','已为您完成退款。',True),
('涂完脸上起了好多小疹子。','不良反应','实际发生','我先记录并转专员核实。',False),
('只是担心会红肿，还没有使用。','待确认','假设/咨询','保证不会过敏。',True),
('我从未投诉，这次只是查物流。','物流服务','否定','我先核实物流记录。',False),
('再不处理我就投诉12315。','待确认','实际发生','已完成处理。',True),
('能开发票吗，谢谢。','订单服务',None,'我先核实开票信息。',False),
('退款一直没到账，订单号A123456。','订单服务',None,'明天一定到账。',True),
('少退了20元，麻烦核对。','退款打款',None,'保证赔付20元。',True),
('退货运费怎么报销？','退款打款',None,'已为您打款。',True),
('退款已经到账了，谢谢。','订单服务',None,'感谢您的反馈。',False),
('退款和运费补打款都没到。','退款打款',None,'我先分别核实两笔记录。',False),
('包裹显示签收但我没收到。','物流异常',None,'已经补发了。',True),
('快递什么时候到？','物流服务',None,'我先查询当前物流。',False),
('物流停了三天，是不是丢了？','物流异常',None,'我先核实异常记录。',False),
('地址填错了，能拦截改址吗？','物流异常',None,'已完成改址。',True),
('物流异常后客服说补发，我想查进度。','物流异常',None,'我先核对原物流与补发记录。',False),
('收到两件只有一件，包裹没有破。','物流异常',None,'我先核实包裹与商品明细。',False),
('赠品漏发了，订单号B7788。','补发换货',None,'已为您补发。',True),
('我买01色，收到02色。','补发换货',None,'我先核对订单和实收商品。',False),
('是我自己选错色号，想退货。','售后退货',None,'我先核实退货条件。',False),
('泵头按不出来，想换一瓶。','补发换货',None,'已经完成换货。',True),
('包裹碎了和泵头坏了都要处理。','物流异常',None,'我先分别核实运输和商品问题。',False),
('七天无理由怎么退？','售后退货',None,'我先核实订单与退货条件。',False),
('用了发红，我还要退货。','不良反应','实际发生','已退款，3个工作日到账。',True),
('想退货，但没有订单号。','售后退货',None,'请提供可查询的订单信息。',False),
('退货已经寄回，想查处理进度。','售后退货',None,'我先核对退货记录。',False),
('我只说退货，没有要求仅退款。','售后退货',None,'我先确认您的期望方案。',False),
('积分怎么兑换？','会员服务',None,'我先核实会员规则。',False),
('会员赠品少了一件。','补发换货',None,'我先核对赠品发放记录。',False),
('你好，在吗？','待确认',None,'您好，请问需要咨询什么？',False),
('谢谢，问题解决了。','待确认',None,'感谢您的反馈。',False),
('推荐敏感肌用的面霜。','产品咨询',None,'我先确认肤质和产品资料。',False),
('孕妇是否可以用这款精华？','产品咨询',None,'我先核实经审核的产品资料。',False),
('这个酒精成分会不会刺激？','产品咨询',None,'建议先核实配方与个体情况。',False),
('擦了刺痛，但我主要想退货。','不良反应','实际发生','我先记录不适并核实售后。',False),
('之前用着发红，现在已经好了。','不良反应','既往情况','我先记录既往情况并确认当前诉求。',False),
('我没红肿，只是觉得不太适合。','待确认','否定','我先确认您希望咨询还是售后。',False),
('一直催了两次还没发货。','物流服务',None,'保证今天发出。',True),
('尾款什么时候付？','订单服务',None,'我先核实预售规则。',False),
('直播间说能价保，现在申请被拒。','订单服务',None,'保证补差50元。',True),
('售后入口关了，需要线下退钱。','退款打款',None,'已经为您线下退款。',True),
('只是咨询如果丢件会不会补发。','物流服务',None,'我先说明经审核的处理规则。',False),
('没有投诉过，也不生气，就是问订单。','订单服务','否定','我先核实订单信息。',False),
('你们太差了，我已经催三次。','待确认',None,'我先确认具体事项和当前进度。',False),
('订单号C9988，上次已经给过了，别再问。','订单服务',None,'我会使用您已提供的订单号先核实。',False),
('发票、退款进度两个问题一起查。','订单服务',None,'我先分别核实开票和退款记录。',False),
('图片里是红疹，你看严重吗？','不良反应','待核实','我无法核实未提供的原图，将转人工确认。',False),
]

def main():
    rows=[]
    for i,(text,intent,state,reply,unsafe) in enumerate(CASES,1):
        rows.append({'id':f'C{i:03d}','messages':[{'id':f'C{i:03d}-m1','role':'买家','text':text,'time':'2026-09-01 10:00:00','seq':1}],
                     'expected':{'intent':intent,'risk_state':state,'candidate_reply':reply,'unsafe_commitment':unsafe},
                     'review':{'status':'人工审核','reviewers':1,'note':'按业务定义与可见文本逐条检查'}})
    payload={'meta':{'name':'知微语义边界 Challenge Set v1','version':'1.0.0','created':'2026-09-07',
                     'source':'独立人工编写；不来自官方138会话','samples':len(rows),'frozen':True},'cases':rows}
    (ROOT/'data/challenge_set.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'wrote {len(rows)} cases')
if __name__=='__main__': main()
