"""Cruza o catálogo de um fornecedor com as buscas da Biblioteca de Anúncios (Colômbia).

Para cada palavra-chave do catálogo: anúncios ativos no país (contador da Biblioteca),
quantos dos anúncios retornados estão no ar há 30+ e 90+ dias, quantas páginas anunciam,
a página com mais anúncios, maior duplicação, quantos levam a site (e não só WhatsApp),
e menção a contraentrega. Só entram anúncios com destino em site (WhatsApp, Messenger e
redes sociais ficam de fora); "ativos_co" é o contador geral da Biblioteca para a frase.
A nota é só escala. Preço citado nos anúncios e preço mínimo de referência entram como informação,
sem excluir nenhum produto.

Nota final = sinal de escala + copy (anúncios com a mesma frase até 30, 2 por loja até 10, duplicação até 10).
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
PRICE_RE = re.compile(r'\$\s?(\d{2,3}(?:[.,]\d{3})+)')
# Só para comentário (não entra na nota nem exclui produto): preço mínimo com frete 30k, devolução 30k,
# CPA 15k, 80% de confirmação, 70% de entrega e lucro de 10k por pedido.
FREIGHT, RETURN, CPA, PROFIT, CONF, DELIV = 30000, 30000, 15000, 10000, 0.8, 0.7
OVERHEAD = FREIGHT + ((PROFIT + CPA) / CONF + (1 - DELIV) * RETURN) / DELIV


def is_web(url):
    host = urlparse(url or '').netloc.lower().replace('www.', '')
    return bool(host) and not any(host == h or host.endswith('.' + h) for h in MESSAGING_HOSTS + SOCIAL_HOSTS)


def lib_page(pid):
    return ('https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=CO&is_targeted_country=false'
            f'&media_type=all&search_type=page&sort_data%5Bdirection%5D=desc&sort_data%5Bmode%5D=total_impressions&view_all_page_id={pid}')


def main():
    kw_csv, cat = sys.argv[1], sys.argv[2]
    # Casa por palavra-chave, não por categoria: re-checagens rodam em outra categoria
    # (ex.: M_prioritarios_nicol) e valem para o mesmo produto.
    kwset = {r['keyword'] for r in csv.DictReader(open(kw_csv, encoding='utf-8'), delimiter=';') if r['keyword']}
    log = {}
    with open(os.path.join(DATA, 'search_log.jsonl'), encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            if r.get('variant') == 'all' and r.get('term') in kwset:
                log[r['term']] = r  # o último registro vale (re-checagens)
    ads_by_term = collections.defaultdict(dict)
    for path in glob.glob(os.path.join(DATA, 'raw', 'search', '*__all.json')):
        d = json.load(open(path, encoding='utf-8'))
        if d.get('term') in kwset:
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
        prices = sorted(v for v in (int(re.sub(r'[.,]', '', m)) for m in PRICE_RE.findall(text)) if 30000 <= v <= 1500000)
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
            'preco_anuncios': prices[len(prices) // 2] if prices else '',
            'pagina_top': names.get(top_pid, ''), 'link_biblioteca_pagina_top': lib_page(top_pid) if top_pid else '',
            'link_melhor_criativo': f"https://www.facebook.com/ads/library/?id={best['ad_archive_id']}" if best else '',
            'link_anuncio_mais_antigo': f"https://www.facebook.com/ads/library/?id={oldest['ad_archive_id']}" if oldest else '',
            'link_loja_top': web_url, 'sinal_escala': round(score, 1),
        }

    # Busca por copy (src/catalog_copy_queue.py + src/copy_search.js): quantos anúncios e lojas
    # repetem a frase de abertura do criativo mais escalado. Entra na nota final.
    copies = {}
    for path in glob.glob(os.path.join(DATA, 'raw', 'copy', f'{cat}_*.json')):
        d = json.load(open(path, encoding='utf-8'))
        cads = d.get('ads', [])
        copies[d['product']] = {
            'copy_frase': d.get('copy', ''), 'copy_anuncios': d.get('count') if d.get('ok') else '',
            'copy_lojas': len({a['page_id'] for a in cads}) if d.get('ok') else '',
            'copy_maior_dup': max((a.get('collation_count') or 1 for a in cads), default='') if d.get('ok') else '',
            'link_busca_copy': d.get('url', ''),
        }

    rows = list(csv.DictReader(open(kw_csv, encoding='utf-8'), delimiter=';'))
    out_rows = []
    for r in rows:
        s = stats.get(r['keyword'], {})
        c = copies.get(r['keyword'], {})
        cost = int(r['custo']) if r['custo'].isdigit() else None
        pmin = round(cost + OVERHEAD) if cost else ''
        market = s.get('preco_anuncios') if s else ''
        nota = s.get('sinal_escala') or 0
        if c.get('copy_anuncios') not in (None, ''):
            nota += min(30, c['copy_anuncios']) + min(10, 2 * (c.get('copy_lojas') or 0)) + min(10, c.get('copy_maior_dup') or 0)
        out_rows.append({**r, **s, **c, 'nota_final': round(nota, 1) if s else '', 'preco_minimo_ref': pmin,
                         'folga_vs_mercado': (market - pmin) if market and pmin else '', 'buscado': 'sim' if s else 'não'})
    out_rows.sort(key=lambda r: -(r.get('nota_final') or 0))
    fields = list(dict.fromkeys(k for r in out_rows for k in r))
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
        if not r.get('nota_final') or r['keyword'] in seen:
            continue
        seen.add(r['keyword'])
        print(f"{r['nota_final']:5} (escala {r['sinal_escala']}, copy {r.get('copy_anuncios','')}) {r['keyword'][:30]:30s} ativos={r['ativos_co']:<5} site={r['retornados_site']:<3} 30d+={r['com_30d']:<3} "
              f"90d+={r['com_90d']:<3} lojas={r['paginas']:<3} lojas2+={r['paginas_2mais']:<2} dup={r['maior_dup']:<3} top={r['pagina_top'][:22]} "
              f"| custo={r['custo']} mín={r['preco_minimo_ref']} anúncios={r['preco_anuncios']}")
        if len(seen) >= 40:
            break
    print('->', out)


if __name__ == '__main__':
    main()
