"""Gera uma palavra-chave de busca (em espanhol, como os anunciantes escrevem) para cada
produto de um catálogo de fornecedor e registra as palavras únicas numa categoria do
keywords_colombia.json, para o src/discover.js buscar na Biblioteca.

Regras: corta no primeiro separador (" - ", "+", ",", "(", "|"), remove códigos de modelo
(tokens com dígitos), marcas e palavras de quantidade, fica com até 2 palavras de conteúdo
(preposições entre elas são mantidas) e tira preposição solta no fim.
Ajustes manuais ficam em OVERRIDES (nome do produto em minúsculas -> palavra-chave).

usage: python3 src/catalog_keywords.py data/catalogos/nicol_rodriguez.csv L_catalogo_nicol
  -> data/catalogos/<nome>_keywords.csv  e  categoria nova no keywords_colombia.json
"""
import csv
import json
import os
import re
import sys
import unicodedata

from common import DATA, ROOT

STOP_TAIL = {'de', 'para', 'con', 'y', 'en', 'e', 'a', 'el', 'la', 'los', 'las', 'por', 'sin', 'tipo', 'del', 'al', 'x'}
PREP = {'de', 'para', 'con', 'y', 'en', 'del', 'al', 'sin', 'e'}
DROP = {'combo', 'kit', 'set', 'nuevo', 'nueva', 'pro', 'professional', 'profesional', 'mini', 'super', 'x1', 'x2', 'x3',
        'remington', 'remlngton', 'babyliss', 'baby', 'liss', 'wahl', 'sokany', 'xiaomi', 'redmi', 'apple', 'sony', 'aiwa',
        'baofeng', 'nintendo', 'kotion', 'buda', 'onn', 'nova', 'chefmaster', 'maclehose', 'sethruki', 'ambie', 'unispeak',
        'inteliget', 'inteligente', 'portatil', 'portátil', 'recargable', 'eléctrico', 'electrico', 'eléctrica', 'electrica'}
# Nomes que a regra resolveria mal.
OVERRIDES = {
    'bandas de ejercicio sf 608': 'bandas de ejercicio',
    'combo 3 en1 aguacatе': None,
    'combo pla +sec ceramico babyliss': 'plancha y secador',
    'combo pl aguacate, rizadora, secadornova': 'plancha y secador',
    'raqueta lampara maтa mosquitos': 'raqueta mata mosquitos',
    'base ay41 cargador inalámbrico 4 en1': 'cargador inalámbrico',
    'cepillo 5 in 1 con maleta cp-c06': 'cepillo 5 en 1',
    'mini camara': 'mini cámara',
    'cepillo x3': None,
    'crispetera maquina para hacer palomitas': 'crispetera',
    'combo wahl professional clip - buda': None,
    'máquina wahl super combo magic clip + de': None,
    'wahl professional clip mágico inalámbric': None,
    'maquina peluquera wahl magic clip 5 star': None,
    'super combo buda y mini buda': None,
    'combo peluq professional y patill buda': 'máquina peluquera',
    'shaver series 2000': 'afeitadora eléctrica',
    'set de cubierto 24p base piña': 'set de cubiertos',
    'set de cubiertos 24p base huevo': 'set de cubiertos',
    'set de cubierto 24p base huevo corona': 'set de cubiertos',
    'reloj inteligente w26 pro': 'reloj inteligente',
    'smartwatch fd68 pro reloj inteligente de': 'reloj inteligente',
    'reloj inteligente moderno deportivo colo': 'reloj inteligente',
    'reloj inteligente smart watch t500': 'reloj inteligente',
    'reloj smart watch t500 contesta llamadas': 'reloj inteligente',
    'combo t500 y audifonos i12': 'reloj inteligente',
    'kit de manicure kit-m016 120 x caja': 'kit de manicure',
    'kit de supervivencia': 'kit de supervivencia',
    'combo set arte 145 pzs y rollo dibujo': 'set de arte',
    'set arte caja lujo aluminio 145 pzs': 'set de arte',
    'set kit arte niños 208 piezas': 'set de arte',
    'set de arte para niños 208 piezas portát': 'set de arte',
    'sarten mini 3 compartimientos divisiones': 'sartén 3 divisiones',
    'combo proyector hy300 +parlante ducha': 'proyector hy300',
    'proyector smart hy300': 'proyector hy300',
    'combo camara 3 antenas y micro sd 32': 'cámara 3 antenas',
    'camara 4k deportiva wifi con control': 'cámara deportiva',
    'combo cepillo 9 en 1 -filtro p 3 en 1': 'cepillo 9 en 1',
    'cepillo de limpieza giratorio 9 en 1': 'cepillo 9 en 1',
    'combo cepillo 2 en 1 y cepillo one strep': 'cepillo one step',
    'combo cep one step-mini plancha-espatula': 'cepillo one step',
    'sec nova, plancha,rizador,peine,one step': 'cepillo one step',
    'kit completo de brochas & limpieza+regal': 'kit de brochas',
    'bandeja p/cubos hielo': 'bandeja para hielo',
    '(2x1) depiladora electrica sensa yes': 'depiladora eléctrica',
    'ab tomic para para abdominales profesion': 'ab tomic',
    'combtapete pies, parchepierna, mini parc': 'tapete masajeador',
    'combo mini parche masajeador-tapete pies': 'tapete masajeador',
    'combo x2 tapete masajeador electroestimu': 'tapete masajeador',
    'tapete masajeador electroestimulador': 'tapete masajeador',
    'mini parche masajeador electrico corpora': 'parche masajeador',
    'peine eléctrico mata las pulgas': 'peine mata pulgas',
    'combo secador 2003 y combo titanio': 'secador de cabello',
    'ventilador eléctrico x3 interior auto us': 'ventilador para carro',
    'ventilador portátil': 'ventilador portátil',
    'candado 6 dígitos seguridad impermeable': 'candado de seguridad',
    'audifonos xg88pro': 'audífonos',
    'audífonos f9-5 unispeak': 'audífonos f9',
    'audífonos in-ear inalámbricos f9-5 negro': 'audífonos f9',
    'combo candado y audifonos f9': None,
    'maleta coo': None,
    'caja fuerte grande': 'caja fuerte',
    'estufa eléctrica 2 puestos hot plate': 'estufa eléctrica',
    'parrilla eléctrica portátil': 'parrilla eléctrica',
    'lavadora portátil maclehose': 'lavadora portátil',
    'set de ollas 13pcs eco': 'set de ollas',
    'linterna + encendedor': 'linterna encendedor',
    'kit limpieza bebe': 'kit de aseo para bebé',
    'kit de aseo personal para bebe': 'kit de aseo para bebé',
    'destornillador electrico': 'destornillador eléctrico',
    'sacacorchos eléctrico para vino': 'sacacorchos eléctrico',
    'masajeador eléctrico': 'masajeador eléctrico',
    'camara videocámara': 'videocámara',
    'cámara digital niños a color fotos y vid': 'cámara para niños',
    'cámara digital fotográfica niños': 'cámara para niños',
    'mini consola portatil retro family game': 'consola retro',
    'consola nintendo super mini sfc 620 jueg': 'consola retro',
    'audifonos diadema mario bros bluetooth m': 'audífonos mario bros',
    'organizadores de nevera almacenamient x7': 'organizadores de nevera',
    'carpa de fotografía con caja de luz para foto': 'caja de luz para fotografía',
    'pluma laser terapia de luz para eliminar': 'pluma láser',
    'letrero led ojos led para vehiculo': 'ojos led para carro',
    'letrero led ojos led para camión': 'ojos led para carro',
    'aspiradora compacta': 'aspiradora compacta',
    'potente aspirador portátil': 'aspiradora portátil',
    'intercomunicador m8 x2': 'intercomunicador m8',
    'intercomunicador m8': 'intercomunicador m8',
    'intercomunicador q58 max x2': 'intercomunicador para moto',
    'licuadora portátil usb-c': 'licuadora portátil',
    'tapete agua peq': 'tapete de agua',
    'tapete agua gr': 'tapete de agua',
    'cinta adhesiva flex tape': 'flex tape',
    'kit pastelería decoración tortas': 'kit de pastelería',
    'kit bandas elásticas x4': 'bandas elásticas',
    'kit limpiador de zapatos': 'limpiador de zapatos',
    'kit pulidor de uñas recargable drill ina': 'pulidor de uñas',
    'kit x3 cuchillos tabla picar pedestal': 'set de cuchillos',
    'juego set de cuchillos 13 piezas en acer': 'set de cuchillos',
    'set de cuchillos pela papas tijeras jueg': 'set de cuchillos',
    'set utensilios cocina madera silicona': 'utensilios de cocina',
    'set tijeras para mascotas ch01': 'tijeras para mascotas',
    'set cepillo para cabello pro5+1': 'cepillo para cabello',
    'set cepillo para cabello pro5+1k': 'cepillo para cabello',
    'set cepillo y plancha pro-2521': 'cepillo y plancha',
    'pestañas kit': 'kit de pestañas',
    'combo 3 en1 keratina': None,
    'mini canchas de fútbol x2': 'cancha de fútbol',
    'cancha de futbol y básquet': 'cancha de fútbol',
    'dermaroller x6': 'dermaroller',
    'estuche bluetooth parlante para ducha': 'parlante para ducha',
    'producto secreto': None,
    'caja cliente ganador': None,
    '120 coмbо': None, 'kr-918': None, 'mvp-100': None, 'lg 60 ultra': None, 'combo zt-40': None, 'combo p9 ultra': None,
    's1 cicla luz': 'luz para bicicleta',
    'watch onn hd': 'tv box', 'watch onn 4k': 'tv box', 'tv box mundialista': 'tv box',
    'watch 4 pro': 'reloj inteligente', 'combo reloj watch x8 ultra': 'reloj inteligente',
    'apple watch series 9': 'reloj inteligente',
    'iniciador de batería carro portatil': 'iniciador de batería',
    'combo x 2 aspiradora robótico inteliget': 'aspiradora robot',
    'robot aspirador robótico inteligente': 'aspiradora robot',
    'luz proyectora universo usb': 'proyector de galaxia',
    'astronauta proyector de luces galaxia': 'proyector astronauta',
    'fascial gun': 'pistola de masajes',
    'mini masajeador martillo pistola fascial': 'pistola de masajes',
    'paint zoom naranja': 'pistola para pintar',
    'water zoom limpieza alta presion agua': 'hidrolavadora',
    'lavadora a presión automotriz portátil': 'hidrolavadora portátil',
    'trapero': 'trapero', 'creatina': 'creatina',
    'cami hot shaper camisa térmica': 'camisa térmica',
    'hada voladora': 'hada voladora',
    'cactus bailarín repetidor': 'cactus bailarín',
    'esferas del dragón caja de 7': 'esferas del dragón',
    'nitric oxide booster ap snap supplements': None,
    'dron e88 pro': 'dron',
    'tábano taser paralizador defensa persona': 'paralizador',
    'xiaomi redmi airdots manos libres blueto': 'audífonos inalámbricos',
    'air pods serie 3': 'audífonos inalámbricos', 'airpods pro 2 con anc': 'audífonos inalámbricos',
    'audífonos airpods pro 2 con pantalla': 'audífonos con pantalla',
    'secador remlngton': 'secador de cabello', 'secador mini remlgton': 'secador de cabello',
    'secador cabello remlngton 2003': 'secador de cabello', 'secador nova': 'secador de cabello',
    'secador porcelana y ceramica baby liss': 'secador de cabello',
    'secador ropa': 'secadora de ropa',
    'mopa giratoria 8988': 'mopa giratoria',
    'trapero giratorio autoescurrido': 'trapero giratorio',
    'trapero giratorio 360° trapeador valde': 'trapero giratorio',
    'trapero escurridor rotación 90°': 'trapero escurridor',
    'molino de carne': 'molino de carne',
    'compresor de aire carro inflador llantas': 'compresor de aire para carro',
    'mini compresor aire 12v': 'compresor de aire para carro',
    'licuadora portátil usb-c': 'licuadora portátil',
    'licuadora portátil jugo fresco mini licu': 'licuadora portátil',
    'mini licuadora shake and take batidos ju': 'licuadora portátil',
    'mini batidora usb portátil de 6 cuchilla': 'licuadora portátil',
}


def fold(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


def keyword(name):
    key = name.strip().lower()
    if key in OVERRIDES:
        return OVERRIDES[key]
    s = re.split(r'\s-\s|\+|,|\(|\||/', name)[0].lower()
    s = re.sub(r'[•°"“”]', ' ', s)
    out, content = [], 0
    for tok in s.split():
        t = tok.strip('.:;!¡¿?')
        if not t or any(ch.isdigit() for ch in t) or fold(t) in {fold(d) for d in DROP}:
            if out and t and any(ch.isdigit() for ch in t):
                break  # código de modelo: o resto costuma ser descrição cortada
            continue
        if t in PREP:
            if out:
                out.append(t)
            continue
        out.append(t)
        content += 1
        if content == 2:
            break
    while out and out[-1] in STOP_TAIL:
        out.pop()
    return ' '.join(out) or None


def add_category(cat, terms):
    path = os.path.join(ROOT, 'keywords_colombia.json')
    txt = open(path, encoding='utf-8').read()
    data = json.loads(txt)
    if cat in data['categories']:
        data['categories'][cat] = terms
        json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        return
    lines = []
    for i in range(0, len(terms), 6):
        lines.append('      ' + ', '.join(json.dumps(t, ensure_ascii=False) for t in terms[i:i + 6]))
    block = f',\n    "{cat}": [\n' + ',\n'.join(lines) + '\n    ]\n  }\n}'
    end = txt.rstrip()
    assert end.endswith('}\n}') or end.endswith('}\r\n}') or re.search(r'\]\s*\}\s*\}$', end)
    new = re.sub(r'\n\s*\}\s*\}\s*$', '', end) + block + '\n'
    json.loads(new)
    open(path, 'w', encoding='utf-8').write(new)


def main():
    src, cat = sys.argv[1], sys.argv[2]
    rows = list(csv.DictReader(open(src, encoding='utf-8-sig'), delimiter=';'))
    for r in rows:
        r['keyword'] = keyword(r['nome']) or ''
    out = os.path.splitext(src)[0] + '_keywords.csv'
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['id', 'nome', 'custo', 'estoque', 'keyword'], delimiter=';')
        w.writeheader()
        w.writerows(rows)
    terms = sorted({r['keyword'] for r in rows if r['keyword']})
    add_category(cat, terms)
    print(f'{len(rows)} produtos, {len(terms)} palavras-chave únicas, {sum(1 for r in rows if not r["keyword"])} sem palavra-chave')
    print('->', out)


if __name__ == '__main__':
    main()
