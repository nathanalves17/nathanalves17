"""Cruza o catálogo de um fornecedor com as buscas da Biblioteca de Anúncios (Colômbia).

Para cada palavra-chave do catálogo: anúncios ativos no país (contador da Biblioteca),
quantos dos anúncios retornados estão no ar há 30+ e 90+ dias, quantas páginas anunciam,
a página com mais anúncios, maior duplicação, quantos levam a site (e não só WhatsApp),
e menção a contraentrega. Só entram anúncios com destino em site (WhatsApp, Messenger e
redes sociais ficam de fora); "ativos_co" é o contador geral da Biblioteca para a frase.
Sem preço nem custo: aqui é só escala e links.

Sinal de escala (0-100): ativos no país (até 30) + anúncios de site com 30+ dias (até 30)
+ duplicação (até 15) + páginas com 2+ anúncios de site (até 15) + anúncios de site com 90+ dias (até 10).

usage: python3 src/catalog_report.py data/catalogos/nicol_rodriguez_keywords.csv L_catalogo_nicol
  -> data/catalogos/<nome>_resultado.csv
"""
import collections
import csv
import glob
import json
import math
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse

from common import DATA, COD_RE, MESSAGING_HOSTS, SOCIAL_HOSTS, fold

TODAY = date(2026, 11, 1)


def is_web(url):
    host = urlparse(url or '').netloc.lower().replace('www.', '')
    return bool(host) and not any(host == h or host.endswith('.' + h) for h in MESSAGING_HOSTS + SOCIAL_HOSTS)


def lib_page(pid):
    return ('https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CO&is_targeted_country=false'
            f'&media_type=all&search_type=page&sort_data%5Bdirection%5D=desc&sort_data%5Bmode%5D=total_impressions&view_all_page_id={pid}')


def main():
    kw_csv, cat = sys.argv[1], sys.argv[2]
    log = {}
    with open(os.path.join(DATA, 'search_log.jsonl'), encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('cat') == cat and r.get('variant') == 'all':
                log[r['term']] = r  # o último registro vale (re-checagens)
    ads_by_term = collections.defaultdict(dict)
    for path in glob.glob(os.path.join(DATA, 'raw', 'search', '*__all.json')):
        d = json.load(open(path, encoding='utf-8'))
        if d.get('cat') == cat:
            for a in d.get('ads', []):
                ads_by_term[d['term']][a['ad_archive_id']] = a

    stats = {}
    for term, rec in log.items():
        all_ads = list(ads_by_term.get(term, {}).values())
        ads = [a for a in all_ads if is_web(a.get('link_url'))]
        ages = [(TODAY - date.fromisoformat(a['start_date'])).days for a in ads if a.get('start_date')]
        pages = collections.Counter(a['page_id'] for a in ads)
        names = {a['page_id']: a['page_name'] for a in ads}
        top_pid = pages.most_common(1)[0][0] if pages else None
        top_ads = [a for a in ads if a['page_id'] == top_pid]
        best = max(top_ads, key=lambda a: ((a.get('collation_count') or 1), -(TODAY - date.fromisoformat(a['start_date'])).days if a.get('start_date') else 0), default=None)
        oldest = min(ads, key=lambda a: a.get('start_date') or '9999', default=None)
        text = ' '.join((a.get('title') or '') + ' ' + (a.get('body') or '') for a in ads)
        total = rec.get('count') or 0
        n30 = sum(1 for x in ages if x >= 30)
        n90 = sum(1 for x in ages if x >= 90)
        dup = max((a.get('collation_count') or 1 for a in ads), default=0)
        multi = sum(1 for c in pages.values() if c >= 2)
        score = (min(30, 10 * math.log10(1 + total)) + min(30, n30 * 2) + min(15, dup * 3) + min(15, multi * 5)
                 + min(10, n90 * 2)) if ads else 0
        web_url = next((a['link_url'] for a in top_ads), '')
        stats[term] = {
            'status': rec.get('status'), 'ativos_co': total, 'retornados': len(all_ads), 'retornados_site': len(ads),
            'com_30d': n30, 'com_90d': n90,
            'mais_antigo_dias': max(ages) if ages else '', 'paginas': len(pages), 'paginas_2mais': multi,
            'maior_dup': dup, 'cod': 'sim' if COD_RE.search(fold(text)) else 'não',
            'pagina_top': names.get(top_pid, ''), 'link_biblioteca_pagina_top': lib_page(top_pid) if top_pid else '',
            'link_melhor_criativo': f"https://www.facebook.com/ads/library/?id={best['ad_archive_id']}" if best else '',
            'link_anuncio_mais_antigo': f"https://www.facebook.com/ads/library/?id={oldest['ad_archive_id']}" if oldest else '',
            'link_loja_top': web_url, 'sinal_escala': round(score, 1),
        }

    rows = list(csv.DictReader(open(kw_csv, encoding='utf-8'), delimiter=';'))
    out_rows = []
    for r in rows:
        s = stats.get(r['keyword'], {})
        out_rows.append({**r, **s, 'buscado': 'sim' if s else 'não'})
    out_rows.sort(key=lambda r: -(r.get('sinal_escala') or 0))
    fields = list(out_rows[0].keys())
    for r in out_rows:
        for k in fields:
            r.setdefault(k, '')
    out = kw_csv.replace('_keywords.csv', '_resultado.csv')
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter=';')
        w.writeheader()
        w.writerows(out_rows)
    done = sum(1 for t in set(r['keyword'] for r in rows if r['keyword']) if t in stats)
    print(f"palavras buscadas: {done} de {len(set(r['keyword'] for r in rows if r['keyword']))}")
    seen = set()
    for r in out_rows:
        if not r.get('sinal_escala') or r['keyword'] in seen:
            continue
        seen.add(r['keyword'])
        print(f"{r['sinal_escala']:5}  {r['keyword'][:30]:30s} ativos={r['ativos_co']:<5} site={r['retornados_site']:<3} 30d+={r['com_30d']:<3} "
              f"90d+={r['com_90d']:<3} lojas={r['paginas']:<3} lojas2+={r['paginas_2mais']:<2} dup={r['maior_dup']:<3} top={r['pagina_top'][:22]}")
        if len(seen) >= 40:
            break
    print('->', out)


if __name__ == '__main__':
    main()
