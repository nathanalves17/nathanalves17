"""Expand keywords_colombia.json from what real ads say.

Sources (website-destination ads only, preferring ones with COD wording):
  - recurring 2–3 word product phrases from titles / first lines of copy that
    appear across several distinct advertisers;
  - brand + model pairs for third-party brands (e.g. footwear);
  - store domains of strong pages (a domain search surfaces sister pages that
    advertise the same store).
Each new term is stored with its origin; existing terms are never duplicated.

usage: python3 src/expand_keywords.py [--max-phrases 60] [--max-domains 40] [--dry-run]
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
from analyze import NICHES, THIRD_PARTY_BRANDS  # noqa: E402

STOP = set('''de la el los las un una unos unas y o a en con por para del al que se su sus tu tus mi mis es son lo le les
mas muy ya no si sin sobre entre hasta desde este esta estos estas ese esa eso aqui ahi hoy solo cada todo toda todos todas
tienda store shop oficial colombia envio envios gratis pago contra entrega contraentrega pagas paga recibir recibe casa
compra compras comprar pide pedido ordena ahora oferta ofertas descuento promo promocion precio precios unidad unidades
nuevo nueva nuevos nuevas mejor mejores calidad garantia original originales disponible disponibles haz clic aqui link
ya te tu nuestro nuestra nuestros puedes quieres tiene tienen dia dias vez veces envio pagar domicilio toda tiempo limitado'''.split())
PRODUCT_WORDS = {w.strip() for _, ws in NICHES for w in ws}


def tokens(text):
    return re.findall(r'[a-z0-9ñ]+', C.fold(text))


def phrases_of(ad):
    lines = [ad.get('title') or '', (ad.get('body') or '').split('\n')[0][:200]]
    lines += [c.get('title') or '' for c in ad.get('cards') or []]
    out = set()
    for line in lines:
        t = tokens(line)
        for n in (2, 3):
            for i in range(len(t) - n + 1):
                g = t[i:i + n]
                if g[0] in STOP or g[-1] in STOP or any(w.isdigit() and len(w) < 3 for w in g):
                    continue
                if sum(w in STOP for w in g) > 1:
                    continue
                phrase = ' '.join(g)
                if any(pw in phrase for pw in PRODUCT_WORDS):
                    out.add(phrase)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-phrases', type=int, default=60)
    ap.add_argument('--max-domains', type=int, default=40)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    path = os.path.join(C.ROOT, 'keywords_colombia.json')
    kw = json.load(open(path))
    existing = set()
    for terms in kw['categories'].values():
        for t in terms:
            existing.add(C.fold(t if isinstance(t, str) else t['term']))

    ads = [a for a in C.load_search_ads() if C.destination(a) == 'website']
    for rec in C.load_pages().values():
        for sl in rec['slices'].values():
            ads += [a for a in sl['ads'] if C.destination(a) == 'website']

    phrase_pages = collections.defaultdict(set)
    brand_models = collections.defaultdict(set)
    domain_score = collections.Counter()
    for a in ads:
        cod = bool(C.cod_phrases(C.ad_text(a)))
        for p in phrases_of(a):
            phrase_pages[p].add(a['page_id'])
        ft = C.fold(C.ad_text(a))
        for b in THIRD_PARTY_BRANDS:
            for m in re.finditer(r'\b' + re.escape(b) + r'\s+([a-z0-9]{2,12})\b', ft):
                if m.group(1) not in STOP:
                    brand_models[f'{b} {m.group(1)}'].add(a['page_id'])
        d = C.host(C.website_url(a) or '')
        if d and not d.endswith('myshopify.com'):
            domain_score[d] += 2 if cod else 1

    new = []
    for p, pgs in sorted(phrase_pages.items(), key=lambda kv: -len(kv[1])):
        if len(pgs) < 3 or C.fold(p) in existing:
            continue
        # skip phrases fully contained in an already chosen longer/shorter one
        if any(p in n['term'] or n['term'] in p for n in new if n['origin'] == 'frase_recorrente'):
            continue
        new.append({'term': p, 'origin': 'frase_recorrente', 'advertisers': len(pgs)})
        if sum(n['origin'] == 'frase_recorrente' for n in new) >= args.max_phrases:
            break
    for bm, pgs in sorted(brand_models.items(), key=lambda kv: -len(kv[1])):
        if len(pgs) >= 2 and C.fold(bm) not in existing:
            new.append({'term': bm, 'origin': 'marca_modelo', 'advertisers': len(pgs)})
    for d, s in domain_score.most_common(args.max_domains):
        if C.fold(d) not in existing:
            new.append({'term': d, 'origin': 'dominio_loja', 'weight': s})

    print(f'{len(new)} new terms')
    for n in new:
        print(' ', n)
    if not args.dry_run:
        kw['categories']['expansao'].extend(new)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(kw, f, ensure_ascii=False, indent=2)
            f.write('\n')


if __name__ == '__main__':
    main()
