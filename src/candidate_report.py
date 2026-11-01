"""Resume as buscas da Biblioteca para os produtos candidatos (categoria K_).

Para cada termo: total de anúncios ativos na CO, quantos estão no ar há 30+ dias,
e por página anunciante: anúncios, duplicações, início mais antigo, preços citados
no texto, menção a contraentrega e domínio de destino.

usage: python3 src/candidate_report.py [prefixo_categoria]   (padrão: K_)
"""
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date
from urllib.parse import urlparse

from common import DATA, COD_RE, fold

PREFIX = sys.argv[1] if len(sys.argv) > 1 else 'K_'
PRICE_RE = re.compile(r'\$\s?(\d{2,3}(?:[.,]\d{3})+)')
TODAY = date(2026, 11, 1)


def load_log():
    log = {}
    with open(os.path.join(DATA, 'search_log.jsonl'), encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('cat', '').startswith(PREFIX):
                log[(r['term'], r['variant'])] = r
    return log


def prices(text):
    out = []
    for m in PRICE_RE.findall(text or ''):
        v = int(re.sub(r'[.,]', '', m))
        if 20000 <= v <= 2000000:
            out.append(v)
    return out


def main():
    log = load_log()
    terms = list(dict.fromkeys(t for t, _ in log))
    for term in terms:
        a, b = log.get((term, 'all'), {}), log.get((term, '30d'), {})
        print(f"\n=== {term}: {a.get('count')} ativos | {b.get('count')} com 30+ dias "
              f"(status {a.get('status')}/{b.get('status')})")
        ads = {}
        for path in glob.glob(os.path.join(DATA, 'raw', 'search', '*.json')):
            d = json.load(open(path, encoding='utf-8'))
            if d.get('term') != term:
                continue
            for ad in d.get('ads', []):
                ads[ad['ad_archive_id']] = ad
        pages = defaultdict(list)
        for ad in ads.values():
            pages[(ad['page_id'], ad['page_name'])].append(ad)
        rows = []
        for (pid, name), lst in pages.items():
            text = ' '.join((x.get('title') or '') + ' ' + (x.get('body') or '') + ' ' + (x.get('link_description') or '') for x in lst)
            start = min(x['start_date'] for x in lst if x.get('start_date'))
            days = (TODAY - date.fromisoformat(start)).days
            dup = max(x.get('collation_count') or 1 for x in lst)
            ps = sorted(set(prices(text)))
            cod = bool(COD_RE.search(fold(text)))
            hosts = {urlparse(x.get('link_url') or '').netloc.replace('www.', '') for x in lst} - {''}
            rows.append((days, name, len(lst), dup, ps, cod, ', '.join(sorted(hosts))[:40]))
        for days, name, n, dup, ps, cod, hosts in sorted(rows, reverse=True)[:8]:
            print(f"  {days:4d}d  {name[:30]:30s} anúncios={n:2d} dup={dup:2d} COD={'sim' if cod else 'não'} "
                  f"preços={','.join(f'{p:,}' for p in ps[:3]) or '-'}  {hosts}")


if __name__ == '__main__':
    main()
