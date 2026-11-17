# Histórico: o que já foi decidido em conversas anteriores

Resumo das sessões anteriores com o Claude sobre o modelo de agência. Aqui ficam só as decisões
de negócio.

## Set/2026: modelo de agência (sessão "Pesquisa de mercado e modelo de agência 2026")

- **Tese:** agência de implementação de IA (voz e texto) para negócios locais. A porta de entrada
  é **ligação e mensagem perdida, principalmente fora do horário comercial**.
- **Regras que saíram da pesquisa:**
  1. Um nicho por vez. "IA para qualquer empresa" está saturado e morre no preço. Quem se
     especializa por vertical tem agenda cheia.
  2. Vender o número perdido, não a tecnologia. Exemplo: "você perdeu US$ X em ligação não
     atendida este mês", calculado com o dono na primeira conversa.
  3. O atendimento fora do horário é a porta de entrada. Depois vem qualificação, agendamento
     e dashboard.
- **Jornada do cliente:** Diagnóstico grátis (isca) → Setup (pagamento único) → Retenção (mensal).
  Funil: prospecção → diagnóstico em 3 dias → proposta em 48h → fechamento com 50% de entrada →
  onboarding.
- **Primeiros 10 clientes sem anúncio:** case piloto com desconto em troca de depoimento →
  outreach direto (30 por semana, meta de 3 reuniões) → conteúdo de nicho → parcerias com
  comissão de 10–15% → grupos do setor.
- Blueprint publicado (versão clínicas no Brasil, em reais):
  [Blueprint Fluxo](https://claude.ai/code/artifact/0d546585-bce5-4ccc-a2dc-6e39f5acc225)

## Out/2026: agência em dólar para brasileiros nos EUA (sessão "Estratégia de caixa e negócio")

- **Ideia do Nathan:** captar donos brasileiros com TikTok Ads, porque o CPL seria mais barato
  que no Meta.
- **Análise:**
  - O mercado está certo. O brasileiro dono de negócio nos EUA talvez seja o melhor ICP já
    levantado: ticket em dólar, sem barreira de idioma, e agência americana não alcança esse
    público por barreira cultural. A maioria vive de boca a boca, com site ruim e zero tráfego pago.
  - **TikTok Ads tem piso de US$ 50/dia por campanha e US$ 20/dia por conjunto.** Um teste de
    R$ 100 não roda nem um dia. Uma leitura mínima custa US$ 20–50/dia por 7 dias.
  - **A métrica é CAC (custo por cliente fechado), não CPL.** Lead barato que não fecha sai mais caro.
  - **O prospect é encontrável de graça:** grupos de Facebook ("Brasileiros em Boston/Orlando/
    Newark"), Instagram e Google Maps em Framingham, Pompano Beach, Marietta, Danbury...
  - **A arbitragem que importa é de mão de obra.** Agência americana cobra US$ 2.000–5.000/mês.
    Cobrar **US$ 600–800/mês** é barato para o cliente e vale R$ 3.500–4.500 para a gente.
    **Dois clientes já mudam o ano.**
- **Plano de validação a custo zero:**
  1. Escolher UM vertical de ticket alto. As sugestões foram remodeling/construção ou limpeza
     comercial.
  2. Escolher 2 praças: Boston/Framingham e Orlando/Pompano.
  3. Montar uma lista de 40 nomes na mão (grupos, Instagram, Maps em português).
  4. Mandar 30 DMs locais e específicos, citando a cidade, o serviço e um número.
  5. Meta: 3 calls. Só depois que fechar alguém o tráfego pago vira decisão de escala.
- **Detalhes:** o leste dos EUA fica 1–2h atrás de Brasília, então call às 19h–20h daqui pega o
  fim do expediente de lá. Receber em dólar via Wise ou Payoneer na PJ (exportação de serviço)
  tem vantagem fiscal, mas precisa validar com o contador antes de emitir nota.

## Ferramentas que já existem

- **LeadLens** (ago/2026, no computador do Nathan, fora deste repositório): pipeline de
  prospecção. Coleta do Google Maps via Apify → checa o site → nota do site → nota do Google
  Business Profile → Lead Score → gera "motivo da ligação" e abertura → dashboard em Streamlit
  com status de CRM e export CSV. **Dá para reaproveitar e prospectar negócios brasileiros nos EUA.**
- **Pipeline da Biblioteca de Anúncios da Meta** (este repositório, `src/discover.js`): hoje roda
  para a Colômbia. Dá para adaptar para país = EUA com termos em português e achar brasileiros
  que já pagam anúncio.

## Como isso conversa com a pesquisa de 17/11

- A porta de entrada de setembro (ligação perdida, IA fora do horário) é o **mesmo produto** do
  snapshot GoHighLevel (missed call text-back + Conversation/Voice AI). Agora ganha um motivo a
  mais: a IA responde o americano em inglês e o dono lê em português.
- O preço de outubro (US$ 600–800) é o **preço de entrada para os primeiros clientes e cases**.
  A escada de `01-pesquisa-de-mercado.md` (US$ 297 a US$ 3.500) vem depois que existir prova.
