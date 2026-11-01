"""Classifica as cidades colombianas em camadas para testes de contraentrega.

Entrada:
  data/dane_pop2026_municipios.csv  projeção DANE 2026 por município (urbana e total),
                                    extraída de PPED-AreaMun-2018-2042_VP.xlsx (atualizado jul/2025)
  data/swayp_cobertura.json         localidades atendidas pela Swayp (código do site swayp.co, nov/2026)

Saída:
  output/cidades_teste_colombia.csv

Critério das camadas (supõe fornecedor despachando de Bogotá, Medellín ou Cali):
  1 Núcleo        os três hubs logísticos e suas regiões metropolitanas: entrega local D+1
                  ou D+2 entre hubs, todas as transportadoras com operação forte.
  2 Eixo andino   cidades grandes ligadas por estrada curta aos hubs (Eje Cafetero,
                  Bucaramanga, Ibagué, Villavicencio, Tunja, Neiva, Oriente antioqueño,
                  centro do Valle).
  3 Distantes     cidades grandes longe dos hubs (Costa Caribe, Cúcuta, sul, Llanos):
                  mais dias em trânsito, testar em conjunto separado.
  Fora            todo o resto (cidades pequenas e zona rural) fica fora do teste inicial.
"""
import csv
import json
import os

from common import DATA, OUTPUT, fold

# (camada, grupo, códigos DANE dos municípios)
TIERS = [
    (1, 'Bogotá e Sabana', ['11001', '25754', '25473', '25286', '25430', '25269', '25175', '25126',
                            '25899', '25214', '25740', '25817', '25758', '25377', '25799', '25785']),
    (1, 'Medellín e Valle de Aburrá', ['05001', '05088', '05360', '05266', '05631', '05380', '05129',
                                       '05212', '05308', '05079']),
    (1, 'Cali e região', ['76001', '76364', '76520', '76892', '76130']),
    (2, 'Oriente antioqueño', ['05615', '05440', '05376', '05318', '05148']),
    (2, 'Eje Cafetero', ['66001', '66170', '66682', '17001', '17873', '63001', '63130']),
    (2, 'Bucaramanga e região', ['68001', '68276', '68307', '68547']),
    (2, 'Ibagué', ['73001']),
    (2, 'Villavicencio', ['50001']),
    (2, 'Tunja', ['15001']),
    (2, 'Neiva', ['41001']),
    (2, 'Fusagasugá e Girardot', ['25290', '25307']),
    (2, 'Centro-norte do Valle', ['76834', '76111', '76147']),
    (2, 'Barrancabermeja', ['68081']),
    (3, 'Barranquilla e região', ['08001', '08758', '08433', '08573', '08296']),
    (3, 'Cartagena e região', ['13001', '13836', '13052']),
    (3, 'Santa Marta e Ciénaga', ['47001', '47189']),
    (3, 'Montería', ['23001']),
    (3, 'Sincelejo', ['70001']),
    (3, 'Valledupar', ['20001']),
    (3, 'Riohacha', ['44001']),
    (3, 'Cúcuta e região', ['54001', '54874', '54405']),
    (3, 'Pasto', ['52001']),
    (3, 'Popayán', ['19001']),
    (3, 'Buenaventura', ['76109']),
    (3, 'Yopal', ['85001']),
    (3, 'Florencia', ['18001']),
]

TIER_NAMES = {1: 'Núcleo', 2: 'Eixo andino', 3: 'Distantes'}


def load_population():
    with open(os.path.join(DATA, 'dane_pop2026_municipios.csv'), encoding='utf-8') as f:
        return {r['mpio']: r for r in csv.DictReader(f)}


def load_swayp():
    """Conjunto de (departamento, município) atendidos pela Swayp, nomes normalizados."""
    with open(os.path.join(DATA, 'swayp_cobertura.json'), encoding='utf-8') as f:
        cov = json.load(f)
    return {(fold(dep), fold(m)) for dep, areas in cov['departamentos'].items() for m in areas}


def main():
    pop = load_population()
    swayp = load_swayp()
    national_total = sum(int(r['total']) for r in pop.values())
    national_urban = sum(int(r['urbana']) for r in pop.values())

    rows = []
    for tier, group, codes in TIERS:
        for code in codes:
            r = pop[code]
            name = r['municipio'].replace(', D.C.', '')
            dep = r['depto'].replace(', D.C.', '')
            # Bogotá aparece como departamento "Cundinamarca" na lista da Swayp.
            dep_key = 'cundinamarca' if code == '11001' else fold(dep)
            name_key = fold(name)
            aliases = {'cartagena de indias': 'cartagena', 'san jose de cucuta': 'cucuta',
                       'guadalajara de buga': 'buga'}
            name_key = aliases.get(name_key, name_key)
            rows.append({
                'camada': tier,
                'camada_nome': TIER_NAMES[tier],
                'grupo': group,
                'departamento': dep,
                'municipio': name,
                'codigo_dane': code,
                'pop_urbana_2026': int(r['urbana']),
                'pop_total_2026': int(r['total']),
                'swayp': 'sim' if (dep_key, name_key) in swayp else 'não',
            })

    out = os.path.join(OUTPUT, 'cidades_teste_colombia.csv')
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f'População Colômbia 2026: {national_total:,} (urbana {national_urban:,})')
    cum = 0
    for tier in (1, 2, 3):
        t = [r for r in rows if r['camada'] == tier]
        tot = sum(r['pop_total_2026'] for r in t)
        urb = sum(r['pop_urbana_2026'] for r in t)
        sw = sum(r['pop_urbana_2026'] for r in t if r['swayp'] == 'sim')
        cum += tot
        print(f'Camada {tier} {TIER_NAMES[tier]:12s} municípios={len(t):3d} total={tot:>11,} '
              f'({tot / national_total:5.1%})  urbana={urb:>11,}  acumulado={cum / national_total:5.1%}  '
              f'urbana c/ Swayp={sw / urb:5.1%}')
        for group in dict.fromkeys(r['grupo'] for r in t):
            g = [r for r in t if r['grupo'] == group]
            print(f'    {group:28s} {sum(r["pop_total_2026"] for r in g):>10,}')
    print('Gravado em', out)


if __name__ == '__main__':
    main()
