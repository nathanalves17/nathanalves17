"""Resumo das buscas por copy (data/raw/copy/*.json).

Para cada copy: total de anúncios ativos na CO com a frase, páginas distintas
entre os primeiros resultados, anúncios por página (contando duplicatas),
domínios de destino e anúncio mais antigo.
"""
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402


def summarize(d):
    groups = collections.defaultdict(list)
    for a in d['ads']:
        groups[(a['page_id'], a.get('collation_id') or a['ad_archive_id'])].append(a)
    per_page = collections.defaultdict(lambda: {'ads': 0, 'name': None, 'domains': collections.Counter(), 'oldest': None, 'max_dup': 0})
    for (pid, _), members in groups.items():
        size = max(len(members), max((m.get('collation_count') or 1) for m in members))
        p = per_page[pid]
        p['ads'] += size
        p['max_dup'] = max(p['max_dup'], size)
        p['name'] = members[0]['page_name']
        for m in members:
            u = C.website_url(m)
            p['domains'][C.host(u) if u else C.destination(m)] += 1
            if m.get('start_date') and (p['oldest'] is None or m['start_date'] < p['oldest']):
                p['oldest'] = m['start_date']
    return per_page


def load():
    out = {}
    for f in sorted(glob.glob(os.path.join(C.DATA, 'raw', 'copy', '*.json'))):
        d = json.load(open(f))
        out[d['id']] = (d, summarize(d))
    return out


def main():
    for cid, (d, per_page) in load().items():
        print(f"\n## {d['page_name']} — {d['product']}\ncopy: \"{d['copy']}\" → {d['count']} anúncios ativos na CO, {len(per_page)} páginas nos primeiros resultados")
        for pid, p in sorted(per_page.items(), key=lambda kv: -kv[1]['ads']):
            own = ' (a própria)' if pid == d['page_id'] else ''
            print(f"   {p['ads']:>3} anúncios (maior dup {p['max_dup']}x) desde {p['oldest']} | {p['name']}{own} | {', '.join(k for k, _ in p['domains'].most_common(2))}")


if __name__ == '__main__':
    main()
