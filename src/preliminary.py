"""Lista preliminar a partir das buscas por palavra-chave (antes da auditoria
das páginas): uma linha por anunciante com destino em site e sinal de COD.

Saídas: output/preliminar_cod_colombia.csv e output/preliminar_cod_colombia.md
"""
import collections
import csv
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
from analyze import md_escape, site_evidence  # noqa: E402
from offers import clean_url  # noqa: E402

LEVEL_RANK = {'documentado no site': 0, 'formulário COD detectado': 1, 'menção no código da página': 2}


def main():
    today = date.today()
    sites = C.load_sites()
    pages = collections.defaultdict(list)
    for a in C.load_search_ads():
        if C.destination(a) == 'website':
            pages[a['page_id']].append(a)

    rows = []
    for pid, ads in pages.items():
        uniq = {a['ad_archive_id']: a for a in ads}.values()
        oldest = min(uniq, key=lambda a: a.get('start_date') or '9999')
        urls = collections.Counter(clean_url(C.website_url(a)) for a in uniq)
        site, site_url = None, None
        for u, _ in urls.most_common():
            if u in sites:
                site, site_url = sites[u], u
                break
        ev = site_evidence(site)
        ad_cod = sorted({p for a in uniq for p in C.cod_phrases(C.ad_text(a))})
        cod_site = ev['level'] in ('documentado no site', 'formulário COD detectado')
        if not cod_site and not ad_cod and ev['level'] != 'menção no código da página':
            continue
        if ev['checked'] and not ev['ok'] and not ev.get('blocked'):
            continue  # destino quebrado ou redireciona para WhatsApp
        prova = []
        if ev['snippets']:
            prova.append('Site: "' + ev['snippets'][0][:140] + '"')
        elif ev['apps']:
            prova.append('Formulário COD no site (' + ', '.join(ev['apps'][:2]) + ')'
                         + (': "' + ev['code_snippets'][0][:100] + '"' if ev['code_snippets'] else ''))
        elif ev['code_snippets']:
            prova.append('Código da página: "' + ev['code_snippets'][0][:100] + '"')
        if ad_cod:
            prova.append('Texto do anúncio: ' + ', '.join(ad_cod[:3]))
        start = oldest.get('start_date')
        rows.append({
            'pagina_anunciante': oldest['page_name'],
            'page_id': pid,
            'link_biblioteca_pagina': C.lib_page_url(pid),
            'link_anuncio': C.lib_ad_url(oldest['ad_archive_id']),
            'link_site': site_url or urls.most_common(1)[0][0],
            'dominio': C.host(site_url or urls.most_common(1)[0][0]),
            'cod_no_site': ev['level'],
            'prova_cod': ' | '.join(prova),
            'preco_cop': ev['price'] or '',
            'anuncios_vistos_nas_buscas': len(uniq),
            'anuncio_mais_antigo_visto': start,
            'dias_no_ar': (today - date.fromisoformat(start)).days if start else '',
            'buscas_em_que_apareceu': '; '.join(sorted({a['_query'] for a in ads}))[:200],
            'verificado_em': today.isoformat(),
        })

    rows.sort(key=lambda r: (LEVEL_RANK.get(r['cod_no_site'], 3), -(r['dias_no_ar'] or 0), -r['anuncios_vistos_nas_buscas']))
    os.makedirs(C.OUTPUT, exist_ok=True)
    with open(os.path.join(C.OUTPUT, 'preliminar_cod_colombia.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    L = ['# Lista preliminar — anunciantes COD na Colômbia (Biblioteca de Anúncios da Meta)', '',
         f'Gerada em {today.isoformat()}. Filtro: país CO, todos os anúncios, anúncios ativos, todos os formatos, ordenado por impressões, '
         'anúncios iniciados há 30+ dias (exceto algumas buscas de pagamento contra entrega sem filtro de data).', '',
         '**Preliminar:** vem só das buscas por palavra-chave. A auditoria de cada página (total de anúncios, criativos, ofertas) ainda está rodando. '
         'Ficaram de fora anúncios que levam direto para WhatsApp/Messenger e sites quebrados.', '',
         f'Total: {len(rows)} anunciantes com destino em site e sinal de pagamento contra entrega. '
         f'{sum(r["cod_no_site"] in ("documentado no site", "formulário COD detectado") for r in rows)} com COD confirmado no próprio site.', '',
         '| # | Página | No ar desde | Dias | COD no site | Preço | Links |', '|---|---|---|---|---|---|---|']
    for i, r in enumerate(rows, 1):
        links = f"[Biblioteca]({r['link_biblioteca_pagina']}) · [Anúncio]({r['link_anuncio']}) · [Site]({r['link_site']})"
        L.append(f"| {i} | {md_escape(r['pagina_anunciante'])} | {r['anuncio_mais_antigo_visto']} | {r['dias_no_ar']} | "
                 f"{r['cod_no_site']} | {md_escape(r['preco_cop'] or '—')} | {links} |")
    L += ['', '## Prova de pagamento contra entrega', '']
    for i, r in enumerate(rows, 1):
        L.append(f"{i}. **{md_escape(r['pagina_anunciante'])}** ({r['dominio']}): {md_escape(r['prova_cod'])}")
    with open(os.path.join(C.OUTPUT, 'preliminar_cod_colombia.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(len(rows), 'anunciantes;', collections.Counter(r['cod_no_site'] for r in rows).most_common())


if __name__ == '__main__':
    main()
