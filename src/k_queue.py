"""Monta a fila de auditoria só com as páginas achadas nas buscas de candidatos (categoria K_).

Entra na fila a página que tem anúncio levando para site (não só WhatsApp/rede social)
e que já mostra algum sinal: anúncio no ar há 30+ dias, 3+ anúncios ou anúncio duplicado.
Ordena por tempo no ar, depois por quantidade de anúncios.

usage: python3 src/k_queue.py [max_paginas]   ->  data/audit_queue_k.json
"""
import collections
import json
import os
import sys
from datetime import date
from urllib.parse import urlparse

from common import DATA, MESSAGING_HOSTS, SOCIAL_HOSTS, load_search_ads

MAX = int(sys.argv[1]) if len(sys.argv) > 1 else 14
TODAY = date(2026, 11, 1)
SKIP_PAGES = {'Mercado Libre', 'Compensar', 'Shark Home Colombia', 'Black+Decker Hogar Colombia'}  # marcas/varejo, não dropshipping


def is_web(url):
    host = urlparse(url or '').netloc.lower().replace('www.', '')
    return bool(host) and not any(host == h or host.endswith('.' + h) for h in MESSAGING_HOSTS + SOCIAL_HOSTS)


def main():
    meta = json.load(open(os.path.join(DATA, '..', 'keywords_colombia.json'), encoding='utf-8'))
    terms = {t for c, ts in meta['categories'].items() if c.startswith('K_') for t in ts}
    pages = collections.defaultdict(lambda: {'ads': {}, 'terms': set(), 'web': 0, 'max_coll': 1, 'min_start': None, 'name': ''})
    for a in load_search_ads():
        if a['_query'] not in terms:
            continue
        p = pages[a['page_id']]
        p['name'] = a['page_name']
        p['terms'].add(a['_query'])
        p['ads'][a['ad_archive_id']] = a
        p['web'] += is_web(a.get('link_url'))
        p['max_coll'] = max(p['max_coll'], a.get('collation_count') or 1)
        s = a.get('start_date')
        if s and (p['min_start'] is None or s < p['min_start']):
            p['min_start'] = s
    rows = []
    for pid, p in pages.items():
        if not p['web'] or p['name'] in SKIP_PAGES:
            continue
        days = (TODAY - date.fromisoformat(p['min_start'])).days if p['min_start'] else 0
        if days >= 30 or len(p['ads']) >= 3 or p['max_coll'] >= 3:
            rows.append({'page_id': pid, 'page_name': p['name'], 'terms': sorted(p['terms']), 'ads_seen': len(p['ads']),
                         'max_collation': p['max_coll'], 'min_start': p['min_start'], 'days': days})
    rows.sort(key=lambda r: (-r['days'], -r['ads_seen']))
    rows = rows[:MAX]
    out = os.path.join(DATA, 'audit_queue_k.json')
    json.dump(rows, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for r in rows:
        print(f"{r['days']:4d}d  {r['page_name'][:28]:28s} ads={r['ads_seen']:2d} dup={r['max_collation']:2d}  {', '.join(r['terms'])}")
    print('->', out)


if __name__ == '__main__':
    main()
