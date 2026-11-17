# Mapa: onde estão os brasileiros nos EUA

Os números vêm de duas fontes que medem coisas diferentes:

- **Itamaraty (MRE), ano-base 2023:** estimativa dos consulados. Inclui indocumentados. Dá
  **2.085.000 no total** e serve para dimensionar o mercado. [Relatório MRE][mre]
- **Census/ACS por cidade (via ZipAtlas):** pessoas que se declaram de origem brasileira.
  Fica muito abaixo do real (~509 mil no total), mas mostra **quais cidades concentram mais**.
  [ZipAtlas][za]

Regra prática: o número real de uma cidade costuma ser **2 a 4 vezes** o número do Census.

## Por região consular (Itamaraty, 2023)

| Consulado | Brasileiros estimados |
|---|---|
| Nova York | 500.000 |
| Boston (Nova Inglaterra) | 420.000 |
| Miami | 400.000 |
| Orlando | 190.000 |
| Atlanta | 120.000 |
| Los Angeles | 120.000 |
| Houston | 110.000 |
| Hartford | 70.000 |
| São Francisco | 65.000 |
| Chicago | 45.000 |
| Washington | 45.000 |
| **Total EUA** | **2.085.000** |

Só Massachusetts: 139.587 pelo ACS 2022, ou ~348 mil aplicando a proporção do estado à
estimativa do Itamaraty. [Boston Foundation][tbf]

## Cidades por estado (Census; o real é maior)

### Massachusetts: o polo mais denso
- **MetroWest:** Framingham 8.429, Marlborough 4.466, Milford 3.991
- **Grande Boston:** Everett 4.560, Boston 3.552, Malden 2.641, Revere 2.099, Somerville 1.930,
  Lynn 1.385, Medford 1.359, Norwood 1.152
- **Outras:** Worcester 3.491, Lowell 2.931, Barnstable/Cape Cod 3.170, Fall River 2.192,
  Martha's Vineyard (2,1% dos brasileiros do estado)

### Flórida: o maior estado em número
- **Sul (Broward/Palm Beach):** Deerfield Beach 7.675, Pompano Beach 4.178, Coconut Creek 3.221,
  Coral Springs 1.446, Fort Lauderdale 1.194, Boca Raton 1.103
- **Miami:** 3.473
- **Centro:** Orlando 6.487, Horizon West 4.012
- **Outras:** Jacksonville 3.810, Port St. Lucie 1.890, Fort Myers 1.445

### Nova Jersey
- Newark 14.736 (a maior cidade em número, bairro Ironbound), Elizabeth 2.949, Long Branch 2.861,
  Kearny 1.847

### Connecticut
- Bridgeport 5.340, Danbury 4.858, Waterbury 1.323, Bethel 1.133

### Nova York e Pensilvânia
- Nova York (cidade) 12.869, Filadélfia 5.360

### Outros polos
- **Califórnia:** Los Angeles 5.906, San Diego 3.888, San Francisco 2.205, Richmond 1.684,
  San Jose 1.343
- **Texas:** Houston 2.264, Austin 1.248, Dallas 1.196
- **Geórgia:** região de Atlanta (120 mil pelo Itamaraty; Marietta é polo conhecido)
- Charlotte (NC) 1.353, Phoenix (AZ) 1.580, Aspen Hill (MD) 1.631, Chicago 3.206

## Onde estão os EMPREENDEDORES (o público-alvo)

### Dados oficiais (ACS 2022, por estado; não existe dado por cidade)

Donos de negócio brasileiros: **Flórida 30.985 (24,7%)**, **Massachusetts 24.488 (19,5%)**,
Califórnia 10,4%, Nova Jersey 8,2%, Connecticut 4,9%, Texas 4,2%, Nova York 4,1%,
Pensilvânia 3,2%, Geórgia 2,9%, Maryland 2,0%. [Boston Foundation][tbf]
A taxa de autônomos entre imigrantes brasileiros é de ~24% nos EUA e 27,6% em MA, quase 3 vezes
a de outros imigrantes. Ou seja, **cerca de 1 em cada 4 brasileiros tem negócio próprio**.

Sinais por cidade: no centro de Framingham, ~85% dos negócios são de imigrantes e existe uma
associação comercial majoritariamente brasileira. Pompano Beach é descrita em estudo como
"enclave típico" de empreendedores brasileiros.

### Medição na prática: quem anuncia em português nos EUA (17/11/2026)

Script `src/us_brazil_scan.js`: 28 buscas em português na Biblioteca de Anúncios (país = EUA,
anúncios ativos). Resultado: **303 anunciantes únicos**. Contagem por cidade citada no anúncio
ou no nome da página (`src/us_brazil_report.py` → `data/eua/cidades_anunciantes.csv`):

| Cidade | Anunciantes | Observação |
|---|---|---|
| **Orlando** | **29** | ~20 negócios locais (concreto, mudança, wallpaper, insulfilm, limpeza, estofados, dentista, buffet, filtro de água). O resto é turismo (aluguel de carro, estacionamento no aeroporto) ou falso positivo |
| Miami | 7 | Aluguel de carro, autoescola, empreiteira |
| Boston | 3 | Limpeza e advogados |
| Framingham, Marlborough | 2 cada | Carros, advogado, moda |
| Tampa, Houston, Nova York, Las Vegas, Windermere | 2 cada | |
| Newark, Danbury, Marietta, Milford, Hudson, Boca Raton, Jacksonville | 1 cada | |

Por estado citado: **FL 46, MA 25**, CA 8, TX 3, CT 3, PA 3.

Limites: só lê os ~30 primeiros anúncios de cada busca. "Pintura" e "reforma" também pegam
anúncio em espanhol. E muito negócio brasileiro de home service anuncia em inglês, para o
americano, então não aparece nessa busca.

**Leitura:** Orlando é onde mais empreendedor brasileiro **já paga anúncio em português**, o
que prova disposição de pagar marketing. Massachusetts tem quase tantos donos de negócio, mas
anuncia menos em português (vive de indicação ou anuncia em inglês). Isso é menos concorrência
para a agência, mas exige achar os clientes pelo Google Maps e pelos grupos, não pela
Biblioteca de Anúncios. Os 303 anunciantes em `data/eua/scan_ads.jsonl` já são uma lista de
leads quentes.

## Leitura: onde atacar com home services

1. **Massachusetts, MetroWest e Grande Boston** (Framingham, Marlborough, Milford, Everett,
   Malden). A maior densidade, muito brasileiro em construção e pintura, e casas antigas que
   precisam de roofing, siding e pintura.
2. **Sul da Flórida, Broward** (Deerfield, Pompano, Coconut Creek, Boca). Muitos negócios
   brasileiros, roofing forte por causa de furacão e muita limpeza.
3. **Orlando/Horizon West.** Comunidade crescendo rápido, com bairros novos e casas de
   aluguel de temporada (limpeza, pressure washing, pool).
4. **Danbury/Bridgeport (CT) e Newark/Long Branch (NJ)**, para a segunda onda.

Isso bate com as 2 praças definidas em outubro: Boston/Framingham e Orlando/Pompano.

[mre]: https://www.conjur.com.br/wp-content/uploads/2025/02/BrasileirosnoExterior2023.pdf
[za]: https://zipatlas.com/us/city-comparison/largest-brazilian-community.htm
[tbf]: https://tbf.org/-/media/tbf/reports-and-covers/2024/brasileiros-na-regiao-da-grande-boston-portugues.pdf
