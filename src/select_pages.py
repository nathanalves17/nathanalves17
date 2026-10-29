"""Build data/audit_queue.json: discovered pages ranked by discovery signals.

Only pages with at least one ad pointing to a website are queued. Signals:
COD wording in the ad copy, number of distinct queries the page surfaced in,
appearance in the 30+ days slice, oldest start date seen, collation counts and
e-commerce shaped destinations.
"""
import collections
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402

ECOM_HINTS = ('/products/', '/product/', '/producto', '/collections/', '/tienda', '/shop', 'checkout', '/p/', 'oferta', 'promo')


def main():
    ads = C.load_search_ads()
    audited = set(C.load_pages())
    pages = collections.defaultdict(lambda: {
        'ads': {}, 'queries': set(), 'web': 0, 'msg': 0, 'cod': 0, 'v30': 0, 'min_start': None,
        'max_coll': 0, 'ecom': 0, 'domains': collections.Counter(), 'name': None,
    })
    for a in ads:
        p = pages[a['page_id']]
        p['name'] = a['page_name']
        p['queries'].add(a['_query'])
        if a['ad_archive_id'] in p['ads']:
            continue
        p['ads'][a['ad_archive_id']] = a
        dest = C.destination(a)
        if dest == 'website':
            p['web'] += 1
            u = C.website_url(a) or ''
            p['domains'][C.host(u)] += 1
            if any(h in u.lower() for h in ECOM_HINTS) or a.get('cta_type') in ('SHOP_NOW', 'BUY_NOW', 'ORDER_NOW', 'GET_OFFER', 'GET_OFFER_VIEW'):
                p['ecom'] += 1
        elif dest == 'messaging':
            p['msg'] += 1
        if C.cod_phrases(C.ad_text(a)):
            p['cod'] += 1
        if a['_variant'] in ('30d', '90d'):
            p['v30'] += 1
        if a['start_date'] and (p['min_start'] is None or a['start_date'] < p['min_start']):
            p['min_start'] = a['start_date']
        p['max_coll'] = max(p['max_coll'], a.get('collation_count') or 0)

    today = date.today()
    rows = []
    for pid, p in pages.items():
        if p['web'] == 0:
            continue
        age = (today - date.fromisoformat(p['min_start'])).days if p['min_start'] else 0
        score = (
            3 * min(p['cod'], 3) + 2 * min(len(p['queries']), 5) + 2 * min(p['ecom'], 3)
            + min(p['web'], 5) + (3 if p['v30'] else 0) + min(age // 30, 6) + min(p['max_coll'] // 5, 4)
            - (2 if p['msg'] > p['web'] else 0)
        )
        rows.append({
            'page_id': pid, 'page_name': p['name'], 'score': score, 'queries': len(p['queries']),
            'ads_seen': len(p['ads']), 'web_ads': p['web'], 'msg_ads': p['msg'], 'cod_ads': p['cod'],
            'min_start': p['min_start'], 'max_collation': p['max_coll'],
            'top_domain': p['domains'].most_common(1)[0][0] if p['domains'] else None,
            'audited': pid in audited,
        })
    rows.sort(key=lambda r: (-r['score'], r['page_id']))
    with open(os.path.join(C.DATA, 'audit_queue.json'), 'w') as f:
        json.dump(rows, f, ensure_ascii=False, indent=0)
    print(f'{len(pages)} pages discovered, {len(rows)} with website ads, {sum(r["audited"] for r in rows)} already audited')
    for r in rows[:25]:
        print(r['score'], r['page_name'], r['top_domain'], 'q=%d web=%d cod=%d min=%s' % (r['queries'], r['web_ads'], r['cod_ads'], r['min_start']))


if __name__ == '__main__':
    main()
