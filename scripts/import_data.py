"""Import competition workbook without treating masked nicknames as unique IDs."""
import collections
import hashlib
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = next(ROOT.glob('*业务数据.xlsx'))
    workbook = openpyxl.load_workbook(source, data_only=True)
    sessions = {}
    counts = {}
    for sheet in workbook:
        if sheet.title == '数据说明':
            continue
        rows = list(sheet.values)
        headers = rows[0]
        counts[sheet.title] = len(rows) - 1
        for rownum, values in enumerate(rows[1:], 2):
            row = dict(zip(headers, values))
            sid = row['会话ID']
            s = sessions.setdefault(sid, {'id': sid, 'buyer': row['买家昵称'], 'messages': [], 'orders': [], 'tickets': []})
            ref = f'{sheet.title}!{rownum}'
            if sheet.title == '聊天记录':
                s['label'] = row['scene_major']
                s['minor_label'] = row['scene_minor']
                s['messages'].append({'id': str(row['message_id']), 'seq': row['消息序号'],
                    'time': str(row['发送时间']), 'role': row['角色'], 'text': row['message_text'] or '',
                    'type': row['内容类型'], 'image': row['image_path'], 'source': ref,
                    'order_id': str(row['关联订单号'] or ''), 'ticket_id': str(row['关联工单号'] or '')})
            elif sheet.title == '订单':
                s['orders'].append({'id': str(row['订单号']), 'created': str(row['下单时间']),
                    'paid': row['付款时间'], 'shipped': row['发货时间'], 'product': row['商品名称'],
                    'amount': row['实付金额(元)'], 'quantity': row['数量'], 'status': row['订单状态'],
                    'carrier': row['快递公司'], 'tracking': str(row['物流单号'] or ''), 'source': ref})
            else:
                s['tickets'].append({'id': str(row['工单号']), 'kind': sheet.title,
                    'created': str(row['创建时间']), 'completed': row['完成时间'],
                    'status': row.get('工单状态') or row.get('任务状态'), 'source': ref,
                    'fields': {k: v for k, v in row.items() if v is not None}})
    for s in sessions.values():
        s['messages'].sort(key=lambda m: m['seq'])
    dataset = {'meta': {'mock': True, 'source': source.name, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
               'counts': counts, 'sessions': len(sessions)}, 'sessions': sorted(sessions.values(), key=lambda s: s['id'])}
    (ROOT / 'data/dataset.json').write_text(json.dumps(dataset, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dataset['meta'], ensure_ascii=True))


if __name__ == '__main__':
    main()
