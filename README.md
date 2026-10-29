# Descoberta avançada — Meta Ads Colômbia (COD)

Pipeline para descobrir anunciantes e ofertas de e-commerce com sinais de escala na
Colômbia usando a Biblioteca de Anúncios da Meta, com verificação de pagamento
contraentrega (COD) no destino real dos anúncios.

Entregáveis em `output/`:

| Arquivo | Conteúdo |
|---|---|
| `ranking_cod_colombia.csv` | Todas as ofertas avaliadas, ordenadas por prioridade |
| `relatorio_cod_colombia.md` | Relatório com cobertura, limitações, critérios e ranking |
| `paginas_sem_destino_site.csv` | Páginas auditadas cujos anúncios levam só a WhatsApp/Messenger/perfis |

## Como funciona

1. **Descoberta por palavra-chave** (`src/discover.js`) — cada termo de
   `keywords_colombia.json` é pesquisado como frase exata em
   `country=CO`, `ad_type=all`, `active_status=active`, `media_type=all`, ordenado por
   impressões. Para os termos de nicho usa-se o recorte "iniciados há 30+ dias"
   (`start_date[max]`), que já privilegia anúncios longevos. O log de cada consulta
   fica em `data/search_log.jsonl` (status `ok`, `zero` ou `failed`).
2. **Seleção de páginas** (`src/select_pages.py`) — ranqueia as páginas descobertas
   por sinais (COD no texto, nº de consultas em que aparecem, destino em site,
   longevidade, colação) e grava `data/audit_queue.json`.
3. **Auditoria de página** (`src/audit_pages.js`) — abre a URL da página na
   Biblioteca no formato do briefing (`search_type=page&view_all_page_id=…`, ordenado
   por impressões) em até 3 recortes: todos os ativos, iniciados há 30+ dias,
   iniciados há 90+ dias.
4. **Ofertas** (`src/offers.py`) — agrupa os anúncios de cada página por destino de
   produto (URL normalizada), calcula anúncios relacionados, criativos distintos
   (ID do vídeo/imagem), longevidade, continuidade e exclui anúncios com destino em
   WhatsApp/Messenger/Direct (pelo tipo de CTA e pelo domínio do link).
5. **Verificação do destino** (`src/build_site_queue.py`, `src/check_sites.js`) —
   abre a landing page renderizada e registra texto visível, apps de formulário COD
   (Releasit, EasySell…), moeda/preço (JSON-LD, og:price, texto) e links de
   WhatsApp. Nenhum formulário é enviado.
6. **Pontuação e relatório** (`src/analyze.py`).
7. **Expansão de palavras-chave** (`src/expand_keywords.py`) — extrai frases de
   produto recorrentes, pares marca+modelo e domínios de lojas dos anúncios reais e
   adiciona à categoria `expansao`, com a origem de cada termo.

```bash
NODE_PATH=$(npm root -g) node src/discover.js --variants 30d
python3 src/select_pages.py
NODE_PATH=$(npm root -g) node src/audit_pages.js --limit 100
python3 src/build_site_queue.py
NODE_PATH=$(npm root -g) node src/check_sites.js
python3 src/analyze.py
python3 src/expand_keywords.py && NODE_PATH=$(npm root -g) node src/discover.js --cats expansao --variants 30d
```

## Limitações de acesso

- A coleta é feita **sem login**. Nessa condição a Biblioteca entrega só a primeira
  página de resultados (até 30 grupos de anúncios) de cada URL; a paginação responde
  "Rate limit exceeded". Contagens por oferta são, portanto, **mínimos observados**.
- A Biblioteca aplica um limite de frequência: às vezes devolve zero resultados para
  uma consulta válida. Os scripts espaçam as requisições (10–16 s), esperam 60–90 s
  e tentam de novo uma vez; persistindo, registram `zero` para nova checagem
  (`--recheck-zero 1`). Não há rotação de sessão/IP nem tentativa de contornar o
  limite. Isso define o volume máximo de páginas auditadas por execução.
- Para anúncios comerciais fora da UE a Biblioteca não mostra impressões, gasto nem
  vendas. Os sinais usados são longevidade, volume criativo e continuidade; nenhuma
  oferta é declarada lucrativa.
- Alegações de saúde/cosméticas e uso de marcas de terceiros são registrados como
  alegações do anunciante, sem verificação de veracidade ou autenticidade.
