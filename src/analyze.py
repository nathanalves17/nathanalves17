"""Score offers from audited pages + destination checks; write CSV and Markdown.

Outputs:
  output/ranking_cod_colombia.csv
  output/relatorio_cod_colombia.md
  output/nao_elegiveis.csv            (pages/offers outside the COD ranking, with reason)
"""
import collections
import csv
import json
import os
import re
import sys
from datetime import date
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402
from offers import build_offers  # noqa: E402

COD_APPS = ('releasit', 'easysell', 'easy-sell', 'cod-form', 'codform', 'cod_form', '_rsi_cod', 'ecomsell',
            'cod-order-form', 'rapidcod', 'zipcod', 'codmonster', 'cod monster', 'sellgo', 'formulario-cod',
            'cod-button', 'buy-cod', 'cod_button', 'hulkapps.*cod')

NICHES = [
    ('Calçado', ['tenis', 'zapato', 'zapatilla', 'calzado', 'botas', 'bota ', 'sandalia', 'chancla', 'crocs', 'sneaker', 'mocasin', 'baleta']),
    ('Moda/Vestuário', ['jean', 'pantalon', 'camisa', 'camiseta', 'blusa', 'vestido', 'chaqueta', 'ropa', 'faja', 'brasier', 'leggin', 'conjunto',
                        'hoodie', 'buzo', 'pijama', 'short', 'lenceria', 'boxer', 'medias', 'enterizo', 'sudadera', 'gorra']),
    ('Joias/Relógios/Acessórios', ['reloj', 'joya', 'anillo', 'collar', 'arete', 'pulsera', 'gafas de sol', 'bolso', 'cartera', 'billetera',
                                   'morral', 'maleta', 'plata 925', 'oro laminado', 'manilla', 'cadena']),
    ('Beleza/Cuidados pessoais', ['serum', 'crema', 'facial', 'piel', 'cabello', 'capilar', 'maquillaje', 'perfume', 'fragancia', 'pestan', 'cejas',
                                  'unas', 'depila', 'arrugas', 'manchas', 'acne', 'labial', 'shampoo', 'colageno', 'skincare', 'locion', 'barba']),
    ('Saúde/Bem-estar', ['dolor', 'plantilla', 'espolon', 'postura', 'rodilla', 'varices', 'masaje', 'sueno', 'dormir', 'ronquido', 'suplemento',
                         'vitamina', 'adelgaz', 'bajar de peso', 'articula', 'tapones', 'oido', 'lectura', 'prostata', 'hemorroide', 'ortopedic',
                         'presion arterial', 'glucosa', 'bienestar']),
    ('Casa/Cozinha', ['cocina', 'olla', 'sarten', 'cuchillo', 'licuadora', 'freidora', 'hogar', 'limpieza', 'organizador', 'colchon', 'almohada',
                      'sabana', 'toalla', 'cortina', 'lampara', 'decoracion', 'bano', 'trapeador', 'aspiradora', 'ventilador', 'calentador', 'mueble']),
    ('Tecnologia/Gadgets', ['celular', 'cargador', 'audifono', 'smartwatch', 'reloj inteligente', 'camara', 'proyector', 'parlante', 'bluetooth',
                            'led', 'usb', 'tablet', 'computador', 'consola', 'power bank', 'iphone', 'airpods', 'tecnolog', 'gadget']),
    ('Automotivo/Ferramentas', ['carro', 'moto', 'vehiculo', 'automo', 'taladro', 'herramienta', 'compresor', 'llanta', 'casco', 'pulidora']),
    ('Fitness/Esporte', ['gym', 'fitness', 'ejercicio', 'deport', 'yoga', 'pesas', 'bicicleta', 'entrenamiento', 'abdominal']),
    ('Pets', ['perro', 'gato', 'mascota', 'canino', 'felino']),
    ('Infantil/Bebê', ['bebe', 'nino', 'nina', 'infantil', 'juguete', 'panal', 'escolar']),
]

CLAIM_WORDS = ['dolor', 'alivia', 'cura', 'adelgaz', 'bajar de peso', 'elimina', 'desinflama', 'antes y despues', 'clinicamente', 'garantizad',
               'manchas', 'arrugas', 'crecimiento del cabello', 'calvicie', 'rejuvenece', 'quema grasa', 'medico', 'tratamiento']
THIRD_PARTY_BRANDS = ['nike', 'adidas', 'new balance', 'jordan', 'puma', 'vans', 'converse', 'crocs', 'skechers', 'asics', 'under armour',
                      'lacoste', 'tommy', 'rolex', 'casio', 'ray-ban', 'rayban', 'apple', 'airpods', 'iphone', 'jbl', 'samsung', 'louis vuitton',
                      'gucci', 'michael kors', 'calvin klein', 'diesel', 'hugo boss', 'salomon', 'on cloud', 'hoka', 'birkenstock', 'reebok',
                      'fila', 'dior', 'chanel', 'versace', 'carolina herrera', 'paco rabanne', 'invicta', 'tissot', 'stanley', 'dyson']

TIERS = ['Forte candidata a escala', 'Candidata promissora', 'Necessita de verificação', 'Não elegível para o ranking COD']


def parse_amount(v):
    """Parse '79.900,00', '79900.00', '79,900' or 79900 into a number."""
    t = str(v).strip()
    if re.fullmatch(r'\d{1,3}(\.\d{3})+(,\d+)?', t):
        t = t.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'\d{1,3}(,\d{3})+(\.\d+)?', t):
        t = t.replace(',', '')
    else:
        t = t.replace(',', '.')
    try:
        return float(t)
    except ValueError:
        return None


def fmt_cop(v):
    n = parse_amount(v)
    # Prices in COP below 1.000 are a parsing artifact, not a real price.
    if not n or n < 1000:
        return None
    return 'COP ' + f'{int(round(n)):,}'.replace(',', '.')


def site_evidence(site):
    ev = {'checked': bool(site), 'ok': False, 'level': 'não verificado', 'snippets': [], 'apps': [], 'code_snippets': [], 'currency': None,
          'price': None, 'platform': None, 'colombia': False, 'checked_at': None, 'final_url': None, 'name': None, 'reason': None}
    if not site:
        return ev
    ev['checked_at'] = site.get('checked_at', '')[:10]
    ev['final_url'] = site.get('final_url')
    if site.get('error'):
        ev['reason'] = 'erro ao abrir: ' + site['error'].split('\n')[0][:120]
        ev['level'] = 'site inacessível'
        return ev
    if site.get('status') in (401, 403, 405, 429, 503):
        ev['reason'] = f'HTTP {site["status"]}: site bloqueou o acesso automatizado (verificar manualmente)'
        ev['level'] = 'acesso bloqueado'
        ev['blocked'] = True
        return ev
    if (site.get('status') or 0) >= 400:
        ev['reason'] = f'HTTP {site["status"]}: destino quebrado na verificação'
        ev['level'] = 'site inacessível'
        return ev
    fh = C.host(site.get('final_url') or '')
    if any(fh.endswith(m) for m in C.MESSAGING_HOSTS):
        ev['reason'] = 'destino redireciona para mensageria'
        ev['level'] = 'redireciona para WhatsApp/Messenger'
        return ev
    text = site.get('text') or ''
    # COD landing pages are often a stack of images plus a buy button, so only a
    # page with neither visible text nor a sizeable document counts as empty.
    if len(text.strip()) < 20 and (site.get('html_len') or 0) < 50000:
        ev['reason'] = 'página sem conteúdo renderizado'
        ev['level'] = 'site sem conteúdo'
        return ev
    ev['ok'] = True
    ev['snippets'] = C.cod_snippets(text)
    ev['apps'] = [m for m in site.get('app_markers', []) if m in COD_APPS]
    # COD wording configured inside the page code (e.g. the COD form app's button
    # or header), cleaned of JSON/HTML noise.
    ev['code_snippets'] = []
    for raw in site.get('cod_html_snippets') or []:
        clean = re.sub(r'<[^>]+>|\\u[0-9a-f]{4}|[{}\[\]"\\]', ' ', raw)
        clean = re.sub(r'\b\w+(?:Style|Color|Enabled|Type|Pos|Factor)\b\s*:?', ' ', clean)
        for snip in C.cod_snippets(clean, width=35, limit=1):
            snip = re.sub(r'\s*[:,]\s*', ' ', snip).strip()
            if snip not in ev['code_snippets']:
                ev['code_snippets'].append(snip)
    noise = lambda t: len(re.findall(r'rgba|true|false|style|[<>=]|\d{2,}', t))
    ev['code_snippets'].sort(key=noise)
    ft = C.fold(text)
    ev['colombia'] = bool(C.COLOMBIA_RE.search(ft))
    cur = collections.Counter(re.findall(r'"([A-Z]{3})"', ' '.join(site.get('currency_hints') or [])))
    for o in site.get('jsonld_offers') or []:
        if o.get('currency'):
            cur[o['currency']] += 2
    og = site.get('og') or {}
    if og.get('og:price:currency'):
        cur[og['og:price:currency']] += 2
    ev['currency'] = cur.most_common(1)[0][0] if cur else None
    price = None
    for o in site.get('jsonld_offers') or []:
        if (o.get('currency') in (None, 'COP')) and o.get('price'):
            price = fmt_cop(o['price'])
            if price:
                break
    if not price and og.get('og:price:amount') and og.get('og:price:currency', 'COP') == 'COP':
        price = fmt_cop(og['og:price:amount'])
    if not price and ev['currency'] in (None, 'COP'):
        m = re.search(r'\$\s?(\d{1,3}(?:\.\d{3})+)(?!\d)', text)
        if m:
            price = 'COP ' + m.group(1) + ' (lido do texto da página, conferir)'
    if ev['currency'] not in (None, 'COP'):
        price = None
    ev['price'] = price
    ev['platform'] = 'Shopify' if site.get('shopify') else ', '.join(site.get('platform_hints') or []) or None
    names = [o.get('name') for o in site.get('jsonld_offers') or [] if o.get('name')]
    ev['name'] = names[0] if names else (og.get('og:title') or site.get('title'))
    if ev['snippets']:
        ev['level'] = 'documentado no site'
    elif ev['apps']:
        ev['level'] = 'formulário COD detectado'
    elif site.get('cod_html_snippets'):
        ev['level'] = 'menção no código da página'
    else:
        ev['level'] = 'não encontrado no site'
    return ev


def niche_of(text):
    ft = C.fold(text)
    best, best_hits = 'Outros', 0
    for name, words in NICHES:
        hits = sum(ft.count(w) for w in words)
        if hits > best_hits:
            best, best_hits = name, hits
    return best


GENERIC_TITLE = re.compile(r'(unidades limitadas|ultimas unidades|paga contra entrega|envio gratis|oferta|compra ya|pide ya|\{\{)')


def product_name(offer, ev):
    n = ev.get('name')
    if n:
        n = re.split(r'\s+[–|—-]\s+', n)[0].strip()
        if 3 <= len(n) <= 120 and '{{' not in n and not re.fullmatch(r'(inicio|home|tienda|shop)', C.fold(n)):
            return n
    m = re.search(r'/products?/([^/?#]+)', offer['key']) or re.search(r'/producto/([^/?#]+)', offer['key'])
    if m:
        handle = re.sub(r'[^\w\s-]', '', unquote(m.group(1)))
        return re.sub(r'\s+', ' ', handle.replace('-', ' ')).strip().capitalize()
    for a in offer['ads']:
        t = (a.get('title') or a.get('link_description') or '').strip()
        if t and not GENERIC_TITLE.search(C.fold(t)):
            return t[:100]
    return C.host(offer['url'])


def score_offer(o, page, ev):
    age, cr, rep = o['age_days'], o['distinct_creatives'], o['represented_ads']
    s_long = 25 if age >= 180 else 20 if age >= 90 else 15 if age >= 60 else 10 if age >= 30 else 0
    s_cr = 20 if cr >= 20 else 15 if cr >= 10 else 10 if cr >= 5 else 5 if cr >= 3 else 0
    s_ads = 15 if rep >= 30 else 12 if rep >= 20 else 8 if rep >= 10 else 4 if rep >= 5 else 0
    s_cont = 10 if (o['recent_ads'] and o['older_ads']) else 3 if o['older_ads'] else 0
    total = page['slices']['all'].get('count') or 0
    s_page = 10 if total >= 200 else 7 if total >= 100 else 4 if total >= 50 else 0
    cod_doc = ev['level'] in ('documentado no site', 'formulário COD detectado')
    cod_partial = (not cod_doc) and (ev['level'] == 'menção no código da página' or bool(o['ad_cod_phrases']))
    s_cod = 15 if cod_doc else 6 if cod_partial else 0
    s_site = 5 if ev['ok'] else 0
    parts = dict(longevidade=s_long, criativos=s_cr, anuncios=s_ads, continuidade=s_cont, escala_pagina=s_page, cod=s_cod, site=s_site)
    return sum(parts.values()), parts, cod_doc, cod_partial


def classify(o, ev, score, cod_doc, cod_partial):
    if not ev['checked']:
        return TIERS[2], 'destino ainda não verificado'
    if ev.get('blocked'):
        return TIERS[2], ev['reason']
    if not ev['ok']:
        return TIERS[3], ev['reason'] or ev['level']
    if ev['currency'] not in (None, 'COP') and not ev['colombia']:
        return TIERS[3], f'site em outra moeda ({ev["currency"]})'
    scale = o['distinct_creatives'] >= 10 or o['represented_ads'] >= 10
    if cod_doc and o['age_days'] >= 30 and scale and score >= 65:
        return TIERS[0], None
    if (cod_doc or cod_partial) and o['age_days'] >= 30 and score >= 45:
        return TIERS[1], None
    return TIERS[2], None


def justify(o, page, ev, parts, cod_doc):
    bits = []
    bits.append(f"{o['n_ads']} anúncios observados ligados à oferta ({o['represented_ads']} contando duplicatas agrupadas), {o['distinct_creatives']} criativos distintos")
    if o['oldest_start']:
        bits.append(f"anúncio mais antigo ativo desde {o['oldest_start']} ({o['age_days']} dias)")
    if o['recent_ads'] and o['older_ads']:
        bits.append(f"continuidade: {o['older_ads']} anúncios com 30+ dias e {o['recent_ads']} lançados nos últimos 30 dias")
    total = page['slices']['all'].get('count')
    c30 = page['slices']['30d'].get('count')
    bits.append(f"página com {total} resultados ativos na CO ({c30} iniciados há 30+ dias)")
    if cod_doc:
        bits.append('COD confirmado no destino (' + ('texto visível' if ev['snippets'] else 'formulário COD: ' + ', '.join(ev['apps'])) + ')')
    elif o['ad_cod_phrases']:
        bits.append('COD citado apenas no texto do anúncio, não confirmado no site')
    elif ev['ok']:
        bits.append('COD não encontrado no site')
    return '; '.join(bits) + '.'


def alerts(o, ev, text):
    out = []
    ft = C.fold(text)
    claims = sorted({w for w in CLAIM_WORDS if w in ft})
    if claims:
        out.append('alegações do anunciante (não verificadas): ' + ', '.join(claims[:5]))
    brands = sorted({b for b in THIRD_PARTY_BRANDS if re.search(r'\b' + re.escape(b) + r'\b', ft)})
    if brands:
        out.append('marcas de terceiros citadas (autenticidade/autorização não comprovada): ' + ', '.join(brands[:5]))
    if ev.get('ok') and not ev.get('colombia') and ev.get('currency') is None:
        out.append('site sem indicação clara de Colômbia/COP')
    if o['key'].rstrip('/').count('/') <= 2:
        out.append('anúncios levam à home da loja (oferta = loja)')
    fh = C.host(ev.get('final_url') or '')
    if fh and fh != C.host(o['url']):
        out.append(f'destino redireciona para outro domínio: {fh}')
    return out


def confidence(o, page, ev, cod_doc):
    pts = 0
    pts += 1 if page.get('validated') else 0
    pts += 1 if page['slices'].get('30d', {}).get('ok') else 0
    pts += 1 if ev['ok'] else 0
    pts += 1 if cod_doc and ev['snippets'] else 0
    pts += 1 if o['n_ads'] >= 5 else 0
    return 'alta' if pts >= 5 else 'média' if pts >= 3 else 'baixa'


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    return [json.loads(l) for l in open(path) if l.strip()]


def main():
    today = date.today()
    search_ads = C.load_search_ads()
    search_by_page = collections.defaultdict(list)
    for a in search_ads:
        search_by_page[a['page_id']].append(a)
    pages = C.load_pages()
    sites = C.load_sites()

    rows, inelig = [], []
    for pid, page in pages.items():
        offers, dest_counts, all_ads = build_offers(page, search_by_page, today)
        n_seen = sum(dest_counts.values())
        msg_pct = round(100 * dest_counts.get('messaging', 0) / n_seen) if n_seen else 0
        page_name = page.get('page_name') or (all_ads[0]['page_name'] if all_ads else '')
        if not offers:
            inelig.append({'pagina': page_name, 'page_id': pid, 'link_biblioteca': C.lib_page_url(pid),
                           'total_resultados': page['slices']['all'].get('count'),
                           'motivo': f'nenhum anúncio observado leva a site (mensageria {dest_counts.get("messaging", 0)}, '
                                     f'social {dest_counts.get("social", 0)}, sem link {dest_counts.get("none", 0)} de {n_seen})',
                           'verificado_em': page['audited_at'][:10]})
            continue
        for o in offers:
            if o['represented_ads'] < 3 and o['age_days'] < 30:
                continue
            site = next((sites[u] for u in o['urls'] if u in sites), None)
            ev = site_evidence(site)
            score, parts, cod_doc, cod_partial = score_offer(o, page, ev)
            tier, reason = classify(o, ev, score, cod_doc, cod_partial)
            text = ' '.join(C.ad_text(a) for a in o['ads']) + ' ' + o['url'] + ' ' + (ev.get('name') or '')
            name = product_name(o, ev)
            cod_ev = []
            if ev['snippets']:
                cod_ev.append('Site: "' + ev['snippets'][0][:160] + '"')
            if ev['apps']:
                cod_ev.append('Formulário COD instalado no site (' + ', '.join(ev['apps'][:3]) + ')'
                              + (': "' + ev['code_snippets'][0][:120] + '"' if ev.get('code_snippets') else ''))
            elif ev.get('code_snippets'):
                cod_ev.append('Código da página: "' + ev['code_snippets'][0][:120] + '"')
            if o['ad_cod_phrases']:
                cod_ev.append('Anúncio: ' + ', '.join(o['ad_cod_phrases'][:3]))
            row = {
                'classificacao': tier, 'pontuacao': score, 'confianca': confidence(o, page, ev, cod_doc),
                'produto': name, 'nicho': niche_of(text), 'pagina_anunciante': page_name, 'page_id': pid,
                'total_resultados_pagina': page['slices']['all'].get('count'),
                'resultados_pagina_30d_mais': page['slices']['30d'].get('count'),
                'resultados_pagina_90d_mais': page['slices'].get('90d', {}).get('count', ''),
                'anuncios_oferta_observados': o['n_ads'], 'anuncios_oferta_com_duplicatas': o['represented_ads'],
                'criativos_distintos': o['distinct_creatives'], 'textos_distintos': o['distinct_copies'],
                'inicio_mais_antigo': o['oldest_start'], 'dias_veiculacao': o['age_days'],
                'anuncios_novos_30d': o['recent_ads'], 'anuncios_30d_mais': o['older_ads'],
                'link_biblioteca_pagina': C.lib_page_url(pid), 'link_anuncio_principal': C.lib_ad_url(o['top_ad']),
                'link_anuncio_mais_antigo': C.lib_ad_url(o['oldest_ad']), 'link_site': o['url'], 'dominio': C.host(o['url']),
                'evidencia_cod': ' | '.join(cod_ev) or 'nenhuma encontrada', 'nivel_cod': ev['level'],
                'preco_cop': ev['price'] or '', 'moeda_site': ev['currency'] or '', 'plataforma': ev['platform'] or '',
                'pct_anuncios_pagina_para_mensageria': msg_pct, 'formatos': ', '.join(o['formats']),
                'componentes_pontuacao': json.dumps(parts, ensure_ascii=False),
                'alertas': ' | '.join(alerts(o, ev, text)), 'motivo_inelegibilidade': reason or '',
                'justificativa': justify(o, page, ev, parts, cod_doc),
                'verificacao_biblioteca': page['audited_at'][:10], 'verificacao_site': ev['checked_at'] or '',
            }
            rows.append(row)

    rows.sort(key=lambda r: (TIERS.index(r['classificacao']), -r['pontuacao'], -r['anuncios_oferta_com_duplicatas']))
    for i, r in enumerate(rows, 1):
        r['rank'] = i
    os.makedirs(C.OUTPUT, exist_ok=True)
    fields = ['rank'] + [k for k in rows[0].keys() if k != 'rank'] if rows else ['rank']
    with open(os.path.join(C.OUTPUT, 'ranking_cod_colombia.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    if inelig:
        with open(os.path.join(C.OUTPUT, 'paginas_sem_destino_site.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=list(inelig[0].keys()))
            w.writeheader()
            w.writerows(inelig)
    write_markdown(rows, inelig, pages, search_ads, sites, today)
    c = collections.Counter(r['classificacao'] for r in rows)
    print(f'{len(rows)} offers from {len(pages)} audited pages; ' + ', '.join(f'{k}: {v}' for k, v in c.items()))


def md_escape(s):
    return str(s).replace('|', '\\|').replace('\n', ' ')


def write_markdown(rows, inelig, pages, search_ads, sites, today):
    log = read_jsonl(os.path.join(C.DATA, 'search_log.jsonl'))
    ok_terms = {(r['term'], r['variant']) for r in log if r['status'] == 'ok'}
    failed = {(r['term'], r['variant']) for r in log if r['status'] != 'ok'} - ok_terms
    discovered_pages = {a['page_id'] for a in search_ads}
    kw = json.load(open(os.path.join(C.ROOT, 'keywords_colombia.json')))
    n_terms = sum(len(v) for v in kw['categories'].values())
    by_tier = collections.defaultdict(list)
    for r in rows:
        by_tier[r['classificacao']].append(r)
    L = []
    L.append('# Descoberta de ofertas COD — Meta Ads, Colômbia')
    L.append('')
    L.append(f'Gerado em {today.isoformat()}. Fonte: Biblioteca de Anúncios da Meta (país CO, "Todos os anúncios", anúncios ativos, todos os formatos, ordenação por impressões), acessada sem login.')
    L.append('')
    L.append('## Cobertura')
    L.append('')
    L.append(f'- Termos no banco de palavras-chave: {n_terms} (sementes + expansão).')
    L.append(f'- Consultas executadas com sucesso: {len(ok_terms)} (termo × recorte de data); falhas sem recuperação: {len(failed)}.')
    L.append(f'- Anúncios distintos coletados nas buscas: {len({a["ad_archive_id"] for a in search_ads})}; páginas anunciantes distintas: {len(discovered_pages)}.')
    L.append(f'- Páginas auditadas individualmente (URL da página na Biblioteca): {len(pages)}.')
    L.append(f'- Destinos (landing pages) abertos e analisados: {len(sites)}.')
    L.append(f'- Ofertas avaliadas: {len(rows)} → ' + ', '.join(f'{t}: {len(by_tier[t])}' for t in TIERS) + '.')
    L.append('')
    L.append('## Limitações de acesso (importante)')
    L.append('')
    L.append('- Sem login, a Biblioteca entrega apenas a **primeira página de resultados (até 30 grupos de anúncios) por URL**; a paginação (rolagem) responde "Rate limit exceeded". Por isso, para cada página foram feitas até 3 leituras com recortes diferentes (todos os ativos; iniciados há 30+ dias; iniciados há 90+ dias). As contagens de anúncios **por oferta são mínimos observados**, não totais.')
    L.append('- "Total de resultados da página" é o contador exibido pela própria Biblioteca para a página (anúncios ativos entregues na CO).')
    L.append('- A Biblioteca não fornece impressões, gasto ou vendas para anúncios comerciais fora da UE. **Nenhuma oferta aqui é comprovadamente lucrativa**; os sinais são de longevidade, volume criativo e continuidade.')
    L.append('- A evidência de COD vem do site renderizado (texto visível, apps de formulário COD como Releasit/EasySell) e do texto dos anúncios. Formulários não foram enviados.')
    L.append('- Alegações médicas/cosméticas e de marcas de terceiros são registradas como **alegações do anunciante**, sem verificação.')
    L.append('')
    L.append('## Critérios de pontuação (0–100)')
    L.append('')
    L.append('| Componente | Regra | Máx. |')
    L.append('|---|---|---|')
    L.append('| Longevidade | anúncio mais antigo ativo da oferta: 30+ d=10, 60+=15, 90+=20, 180+=25 | 25 |')
    L.append('| Criativos distintos | mídia distinta (vídeo/imagem): 3+=5, 5+=10, 10+=15, 20+=20 | 20 |')
    L.append('| Anúncios da oferta | inclui duplicatas agrupadas pela Biblioteca: 5+=4, 10+=8, 20+=12, 30+=15 | 15 |')
    L.append('| Continuidade | anúncios com 30+ dias **e** anúncios novos (<30 d)=10; só antigos=3 | 10 |')
    L.append('| Escala da página | resultados ativos: 50+=4, 100+=7, 200+=10 | 10 |')
    L.append('| COD | documentado no site ou formulário COD=15; só no anúncio/código=6 | 15 |')
    L.append('| Site funcional | página abriu com conteúdo | 5 |')
    L.append('')
    L.append('**Forte candidata**: COD documentado no destino, 30+ dias, 10+ criativos ou 10+ anúncios, pontuação ≥ 65. **Promissora**: COD documentado ou citado, 30+ dias, pontuação ≥ 45. **Necessita verificação**: destino é site, mas faltam provas. **Não elegível**: destino inacessível, redireciona a mensageria ou outra moeda/país.')
    L.append('')
    for tier in TIERS:
        items = by_tier.get(tier, [])
        if not items:
            continue
        L.append(f'## {tier} ({len(items)})')
        L.append('')
        L.append('| # | Produto | Nicho | Página | Total pág. | Anúncios oferta | Criativos | Desde | Pontos | Conf. | Preço | Links |')
        L.append('|---|---|---|---|---|---|---|---|---|---|---|---|')
        for r in items:
            links = f"[Biblioteca]({r['link_biblioteca_pagina']}) · [Anúncio]({r['link_anuncio_principal']}) · [Site]({r['link_site']})"
            L.append(f"| {r['rank']} | {md_escape(r['produto'])} | {r['nicho']} | {md_escape(r['pagina_anunciante'])} | {r['total_resultados_pagina']} | "
                     f"{r['anuncios_oferta_observados']} ({r['anuncios_oferta_com_duplicatas']}) | {r['criativos_distintos']} | {r['inicio_mais_antigo']} | "
                     f"{r['pontuacao']} | {r['confianca']} | {md_escape(r['preco_cop'] or '—')} | {links} |")
        L.append('')
        if tier in TIERS[:2]:
            L.append('### Detalhes')
            L.append('')
            for r in items:
                L.append(f"**#{r['rank']} — {md_escape(r['produto'])}** ({r['pagina_anunciante']}, page_id {r['page_id']})")
                L.append('')
                L.append(f"- Evidência COD: {r['evidencia_cod']}")
                L.append(f"- Justificativa: {r['justificativa']}")
                if r['alertas']:
                    L.append(f"- Alertas: {r['alertas']}")
                L.append(f"- Anúncio mais antigo: {r['link_anuncio_mais_antigo']}")
                L.append(f"- Verificado: Biblioteca {r['verificacao_biblioteca']}, site {r['verificacao_site']}")
                L.append('')
        if tier == TIERS[3]:
            L.append('Motivos: ' + '; '.join(sorted({f"#{r['rank']} {r['motivo_inelegibilidade']}" for r in items})[:40]))
            L.append('')
    if inelig:
        L.append(f'## Páginas auditadas sem destino em site ({len(inelig)})')
        L.append('')
        L.append('Anúncios observados levam apenas a WhatsApp/Messenger/perfis sociais — fora do ranking COD por regra do briefing. Lista completa em `output/paginas_sem_destino_site.csv`.')
        L.append('')
    with open(os.path.join(C.OUTPUT, 'relatorio_cod_colombia.md'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')


if __name__ == '__main__':
    main()
