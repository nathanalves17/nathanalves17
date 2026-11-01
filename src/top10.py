"""Top 10 de produtos para o próximo teste COD: cruza a validação da Biblioteca com o filtro de produto.

Entrada: output/ranking_cod_colombia.csv (pontuação de validação do pipeline: tempo no ar,
duplicações, criativos, continuidade, escala da página, COD no site).

Por cima da pontuação aplica:
  + experiência de campo (produtos que o usuário e conhecidos viram escalar na Colômbia)
  + temporada (presente de Natal/prima, pólvora, volta às aulas)
  - tamanho (calçado/roupa: risco extra de recusa)
  - marca de terceiros (risco de denúncia e reprovação do anúncio)
  - alegação de saúde (restrição de anúncio no TikTok/Meta)
  - ticket baixo sem kit (não cobre frete + devolução)
e calcula o custo máximo de fornecedor que fecha a conta:
  preço - frete 30k - ((lucro 10k + CPA 15k)/0,8 + 0,3 × devolução 30k)/0,7  ≈ preço - 87,5k

usage: python3 src/top10.py  ->  output/top10_produtos_nov2026.md
"""
import csv
import os
import re

from common import OUTPUT, fold

FIELD = ['picador', 'cortador', 'rallador', 'especier', 'especias', 'robot', 'aspiradora', 'trapeador', 'mopa',
         'taladro', 'masajeador', 'tenis', 'zapatilla', 'chaqueta', 'freidora', 'cafetera', 'olla']
SEASON = ['olla', 'freidora', 'picador', 'licuadora', 'taladro', 'masajeador', 'aspiradora', 'robot', 'iniciador',
          'bateria', 'perro', 'gato', 'escolar', 'regalo', 'combo', 'kit', 'maleta']
SIZE = ['talla', 'tenis', 'zapat', 'chaqueta', 'pantal', 'jean', 'vestido', 'brasier', 'leggin', 'camis', 'jump']
BRANDS = ['nike', 'adidas', 'on cloud', 'cloudtilt', 'apple', 'airpods', 'samsung', 'dewalt', 'stanley', 'xiaomi',
          'shark', 'dyson', 'alexa', 'amazon', 'black+decker', 'black & decker']
BUNDLE = re.compile(r'2\s?x\s?1|x\s?[23]\b|3\s?x\s?2|combo|kit|paquete|juego')
FREIGHT, RETURN, CPA, PROFIT, CONF, DELIV = 30000, 30000, 15000, 10000, 0.8, 0.7
OVERHEAD = FREIGHT + ((PROFIT + CPA) / CONF + (1 - DELIV) * RETURN) / DELIV


def price_of(s):
    m = re.search(r'(\d{1,3}(?:[.,]\d{3})+)', s or '')
    return int(re.sub(r'[.,]', '', m.group(1))) if m else None


def main():
    rows = list(csv.DictReader(open(os.path.join(OUTPUT, 'ranking_cod_colombia.csv'), encoding='utf-8')))
    out = []
    for r in rows:
        if r['classificacao'] not in ('Forte candidata a escala', 'Candidata promissora', 'Necessita de verificação'):
            continue
        name = fold(r['produto'])
        score = float(r['pontuacao'] or 0)
        price = price_of(r['preco_cop'])
        flags, plus = [], []
        if any(k in name for k in FIELD):
            score += 10; plus.append('campo')
        if any(k in name for k in SEASON):
            score += 5; plus.append('temporada')
        if r['nicho'] in ('Calçado', 'Moda/Vestuário') or any(k in name for k in SIZE):
            score -= 15; flags.append('tamanho')
        if any(b in name for b in BRANDS):
            score -= 25; flags.append('marca de terceiros')
        if 'alega' in (r['alertas'] or ''):
            score -= 10; flags.append('alegação de saúde')
        bundle = bool(BUNDLE.search(name))
        if price and price < 100000 and not bundle:
            score -= 10; flags.append('ticket baixo')
        if not price:
            flags.append('sem preço')
        max_cost = price - OVERHEAD if price else None
        out.append({**r, 'score_final': round(score, 1), 'flags': flags, 'plus': plus, 'price': price,
                    'max_cost': max_cost, 'bundle': bundle})
    out.sort(key=lambda r: -r['score_final'])
    top = out[:10]

    L = ['# Top 10 produtos para o próximo teste COD (Colômbia, nov/2026)', '',
         'Validação: pontuação do pipeline (Biblioteca de Anúncios da Meta, CO). Ajustes: +10 experiência de campo, '
         '+5 temporada, −15 tamanho, −25 marca de terceiros, −10 alegação de saúde, −10 ticket < 100 mil sem kit.',
         f'Custo máximo no fornecedor = preço − {OVERHEAD:,.0f} (frete 30k, devolução 30k, CPA 15k, 80% confirmação, '
         '70% entrega, lucro 10k por pedido).', '']
    for i, r in enumerate(top, 1):
        mc = f"até ${r['max_cost']:,.0f}".replace(',', '.') if r['max_cost'] and r['max_cost'] > 0 else 'não fecha sozinho (precisa kit)'
        L += [f"## {i}. {r['produto']} · {r['pagina_anunciante']} · {r['preco_cop'] or 'preço não lido'}",
              f"- Nota final {r['score_final']} (validação {r['pontuacao']}) · nicho {r['nicho']} · no ar há {r['dias_veiculacao']} dias · "
              f"{r['anuncios_oferta_com_duplicatas']} anúncios · maior duplicação {r['maior_grupo_duplicado']}x · {r['criativos_distintos']} criativos",
              f"- A favor: {', '.join(r['plus']) or '—'} · Atenção: {', '.join(r['flags']) or '—'}",
              f"- Custo máximo no fornecedor: {mc}",
              f"- Melhor criativo: {r['link_anuncio_principal']}",
              f"- Biblioteca da loja: {r['link_biblioteca_pagina']}",
              f"- Loja: {r['link_site']}", '']
    path = os.path.join(OUTPUT, 'top10_produtos_nov2026.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(L))
    for i, r in enumerate(top, 1):
        print(f"{i:2d}. {r['score_final']:5.1f} ({r['pontuacao']}) {r['produto'][:38]:38s} {r['pagina_anunciante'][:18]:18s} "
              f"{(r['preco_cop'] or '-')[:12]:12s} {r['dias_veiculacao']:>4s}d  +{','.join(r['plus'])} -{','.join(r['flags'])}")
    print('->', path)


if __name__ == '__main__':
    main()
