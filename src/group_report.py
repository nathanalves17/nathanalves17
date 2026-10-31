"""Resumo das ofertas indicadas (data/raw/group/*.json + sites verificados).

Para cada oferta: anúncios do produto (link para o produto), duplicações,
criativos distintos, tempo no ar, continuidade, escala da página principal,
busca da copy e evidência de COD/preço no site.
"""
import collections
import json
import os
import re
import sys
from datetime import date
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
from analyze import site_evidence  # noqa: E402


def handle(url):
    m = re.search(r'/products?/([^/?#]+)', url or '')
    return re.sub(r'-\d{1,2}$', '', m.group(1).lower()) if m else None


def product_stats(ads, domain, prod_handle, today):
    groups = collections.defaultdict(list)
    for a in ads:
        links = C.ad_links(a)
        if not any(C.host(l) == domain for l in links):
            continue
        if prod_handle and not any(handle(l) == prod_handle for l in links):
            continue
        groups[a.get('collation_id') or a['ad_archive_id']].append(a)
    sizes = [max(len(m), max((x.get('collation_count') or 1) for x in m)) for m in groups.values()]
    flat = [a for m in groups.values() for a in m]
    media = set()
    for a in flat:
        media.update(a.get('media_keys') or [])
    starts = sorted(a['start_date'] for a in flat if a.get('start_date'))
    return {
        'ads': sum(sizes), 'groups': len(sizes), 'max_dup': max(sizes) if sizes else 0,
        'creatives': len(media), 'oldest': starts[0] if starts else None, 'newest': starts[-1] if starts else None,
        'age': (today - date.fromisoformat(starts[0])).days if starts else 0,
        'recent': sum(1 for s in starts if (today - date.fromisoformat(s)).days < 30),
        'top_ad': flat[0]['ad_archive_id'] if flat else None,
        'pages': sorted({a['page_name'] for a in flat}),
    }


def dedupe(ads):
    return list({a['ad_archive_id']: a for a in ads}.values())


def main():
    today = date.today()
    sites = C.load_sites()
    offers = json.load(open(os.path.join(C.DATA, 'group_offers.json')))
    out = []
    for o in offers:
        f = os.path.join(C.DATA, 'raw', 'group', f"{o['id']}.json")
        if not os.path.exists(f):
            print(f"\n## {o['product']} — ainda não analisada")
            continue
        r = json.load(open(f))
        domain = C.host(o['product_url'])
        h = handle(o['product_url'])
        pool = r['domain_search']['ads'] + [a for p in r.get('pages', {}).values() for s in p['slices'].values() for a in s['ads']]
        pool = dedupe(pool)
        prod = product_stats(pool, domain, h, today)
        store = product_stats(pool, domain, None, today)
        ev = site_evidence(sites.get(o['product_url']))
        site = sites.get(o['product_url']) or {}
        og = site.get('og') or {}
        price = ev['price'] or (f"{og.get('og:price:amount')} {og.get('og:price:currency')}" if og.get('og:price:amount') else '')
        print(f"\n## {o['product']} ({o['pais']}) — {domain}")
        print(f"   busca do domínio: {r['domain_search'].get('count')} anúncios ativos")
        for p in r.get('pages', {}).values():
            s = p['slices']
            print(f"   página {p['page_name']} ({p['page_id']}): total {s['all'].get('count')} | 30d+ {s['30d'].get('count')} | 90d+ {s.get('90d', {}).get('count', '-')}")
        print(f"   PRODUTO: {prod['ads']} anúncios (grupos {prod['groups']}, maior duplicação {prod['max_dup']}x), {prod['creatives']} criativos, "
              f"desde {prod['oldest']} ({prod['age']} d), mais novo {prod['newest']}, novos 30d {prod['recent']}, páginas {prod['pages']}")
        print(f"   LOJA (todos os produtos): {store['ads']} anúncios, {store['creatives']} criativos, desde {store['oldest']}")
        cs = r.get('copy_search')
        if cs:
            pages = collections.Counter(a['page_name'] for a in cs['ads'])
            print(f"   COPY \"{cs['copy']}\": {cs.get('count')} anúncios, páginas {dict(pages.most_common(5))}")
        print(f"   SITE: {ev['level']} | preço {price} | {(ev['snippets'] or ev['code_snippets'] or [''])[0][:100]} | final {site.get('final_url')}")
        out.append({'offer': o, 'product': prod, 'store': store, 'copy': cs and {'copy': cs['copy'], 'count': cs.get('count'), 'url': cs['url']},
                    'pages': {pid: {k: v.get('count') for k, v in p['slices'].items()} for pid, p in r.get('pages', {}).items()},
                    'site': {'level': ev['level'], 'price': price, 'final_url': site.get('final_url')}})
    json.dump(out, open(os.path.join(C.DATA, 'group_summary.json'), 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
