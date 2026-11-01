"""Monta a fila de busca por copy para os produtos mais escalados de um catálogo.

Para cada palavra-chave com sinal de escala (data/catalogos/<nome>_resultado.csv), pega o
anúncio de site da página que mais anuncia (o mais duplicado; empate: o mais antigo) e extrai
a frase de abertura da copy: primeira frase do texto, sem emojis e aspas, até 9 palavras.
Essa frase é buscada como frase exata pelo src/copy_search.js para ver quantos anúncios e
quantas lojas repetem a mesma copy (duplicação = escala).

usage: python3 src/catalog_copy_queue.py data/catalogos/nicol_rodriguez_resultado.csv L_catalogo_nicol [top_n]
  -> data/copy_queue_<categoria>.json (acrescenta só o que ainda não está na fila)
"""
import csv
import glob
import json
import os
import re
import sys
from datetime import date

from common import DATA
from catalog_report import is_web

EMOJI = re.compile('[\U0001F000-\U0001FFFF☀-➿️‍]')
# Frases de promoção, frete ou pagamento batem em qualquer anúncio: não servem para achar a copy.
GENERIC = re.compile(r'%|black|oferta|descuento|env[ií]o gratis|contra ?entrega|paga(s)? al recibir|pago al recibir|promo|cyber|solo por hoy|[uú]ltimas unidades|\{\{', re.I)


def slug(s):
    import unicodedata
    s = ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def opening_phrase(ad):
    for field in ('body', 'title'):
        txt = EMOJI.sub(' ', ad.get(field) or '')
        txt = re.sub(r'[“”"«»*_#|]+', ' ', txt)
        for line in txt.splitlines():
            line = line.strip(' -–•✅✔️👉¡!¿?.')
            if len(line.split()) < 4 or GENERIC.search(line):
                continue
            first = re.split(r'(?<=[.!?…])\s', line)[0].strip(' .!?…')
            words = first.split()
            if len(words) >= 4:
                return ' '.join(words[:9])
    return None


def main():
    res_csv, cat = sys.argv[1], sys.argv[2]
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    rows = list(csv.DictReader(open(res_csv, encoding='utf-8'), delimiter=';'))
    seen, picks = set(), []
    for r in rows:
        if not r.get('sinal_escala') or r['keyword'] in seen or not r.get('retornados_site') or r['retornados_site'] == '0':
            continue
        seen.add(r['keyword'])
        picks.append(r)
        if len(picks) >= top_n:
            break
    ads = {}
    for path in glob.glob(os.path.join(DATA, 'raw', 'search', '*__all.json')):
        d = json.load(open(path, encoding='utf-8'))
        if d.get('cat') == cat:
            ads.setdefault(d['term'], []).extend(d.get('ads', []))
    qpath = os.path.join(DATA, f'copy_queue_{cat}.json')
    queue = json.load(open(qpath, encoding='utf-8')) if os.path.exists(qpath) else []
    have = {q['id'] for q in queue}
    added = 0
    for r in picks:
        qid = f"{cat}_{slug(r['keyword'])}"
        if qid in have:
            continue
        site = [a for a in ads.get(r['keyword'], []) if is_web(a.get('link_url')) and a['page_name'] == r['pagina_top']]
        site.sort(key=lambda a: (-(a.get('collation_count') or 1), a.get('start_date') or '9999'))
        phrase = next((p for p in (opening_phrase(a) for a in site) if p), None)
        if not phrase:
            continue
        queue.append({'id': qid, 'page_id': site[0]['page_id'], 'page_name': r['pagina_top'], 'product': r['keyword'],
                      'copy': phrase, 'source_ad': site[0]['ad_archive_id']})
        added += 1
    json.dump(queue, open(qpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{added} copies novas, {len(queue)} na fila -> {qpath}')
    for q in queue[-added:] if added else []:
        print(f"  {q['product'][:28]:28s} | {q['page_name'][:22]:22s} | \"{q['copy']}\"")


if __name__ == '__main__':
    main()
