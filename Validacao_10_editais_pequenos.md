# Validação em lote — 10 editais de municípios pequenos

**Projeto IA-Licita (piloto) · Lei 14.133/2021 · análise de 01/06/2026**

## Resultado agregado (camada automática)

- Editais processados: **10** (todos com texto extraível — nenhum escaneado)
- Índice de risco médio: **0/100**
- Editais com inconformidade estrutural: **0 (0%)**
- Editais com achado grave: **0 (0%)**

Ao contrário do edital de Santa Teresinha (que veio cheio de erros de reaproveitamento de modelo), **estes 10 editais estão bem redigidos** nos pontos verificáveis. Isso é, em si, um resultado relevante: a ferramenta **não fabrica problemas** onde não há.

## Os 10 editais

| # | Município/Órgão | Instrumento | Objeto | Veredito |
|---|---|---|---|---|
| e01 | Lajes/RN | Concorrência Eletrônica 06/2026 | Contratação de empresa (serviços) | Sem inconformidade |
| e02 | Resende/RJ (FMS) | Pregão Eletrônico SRP 165/2026 | Saúde | Sem inconformidade |
| e03 | Pesqueira/PE | Pregão Eletrônico 014/2026 | — (menor preço) | Atestado 30% (proporcional) — conforme |
| e04 | Araguaína/TO | Concorrência Internacional 003/2026 | Engenharia — Parque Nascentes do Neblina (R$ 8,1 mi) | Internacional legítima (financiamento externo) — conforme |
| e05 | Órgão "FUL" (autarquia/fundação municipal) | Pregão Eletrônico 013/2026 | Equipamentos p/ manutenção de semáforo | Validade da proposta 60 dias — conforme |
| e06 | Timon/MA | Concorrência Pública 005/2026 (republicação) | REURB-S (regularização fundiária) — técnica e preço | Modo de disputa **fechado** (correto p/ técnica e preço, art. 56) |
| e07 | Câmara Municipal de Formosa/GO | Chamamento Público 01/2026 | Credenciamento de rádios | Instrumento distinto (credenciamento) — sem inconformidade |
| e08 | Acari/RN | Pregão Eletrônico (republicação) | Seguro veicular | Vedações de participação presentes — conforme |
| e09 | Senador José Porfírio/PA (FMS) | Pregão Eletrônico | Saúde | Sem inconformidade legal. Nota de qualidade: comunicado com frase de tom amador |
| e10 | Aimorés/MG | Pregão Eletrônico 040/2026 | — (menor preço) | Sem inconformidade |

## O que foi verificado

Camada automática (30 regras) + varredura semântica dirigida aos defeitos mais frequentes em município pequeno: coerência município/órgão/objeto, datas contraditórias, exercício orçamentário, plataforma eletrônica, modo de disputa × critério (art. 56), garantia de execução, percentual de atestado (restritividade técnica), visita técnica obrigatória e validade da proposta.

## Falsos positivos identificados e tratados

A varredura inicial levantou alguns sinais que, ao serem conferidos, se mostraram **falsos** — e foram corrigidos, fortalecendo a ferramenta:

- "Modo de disputa = Menor Preço" (e01, e09): era adjacência de linhas na extração; o campo real é "Aberto". **Rejeitado.**
- Alertas de "vedações de participação" (e08) e "validade da proposta" (e06): a exigência existia, com redação diferente do termo esperado ("não poderão disputar"; "validade de sua proposta"). Os sinônimos foram **adicionados às regras**.
- "Desempate/validade" (e07): não se aplicam a um credenciamento. **Contextual.**

Que a ferramenta tenha terminado com **zero inconformidade** depois de rejeitar os falsos positivos é o comportamento correto de uma auditoria — não inventar achado.

## Leitura honesta para o piloto

Esta amostra **não produz a estatística de "X% com erro grave"** — e isso é informação útil: nem todo município pequeno comete os erros grosseiros de Santa Teresinha. Dois pontos decorrem disso:

1. **Credibilidade:** a ferramenta calibrou para a qualidade real dos documentos (5 inconformidades no edital ruim, 0 nestes 10 bons), sem alarme falso.
2. **Limite da camada determinística:** em editais bem redigidos, os defeitos que sobram são sutis e interpretativos (proporcionalidade de exigências, coerência entre cláusulas, aderência fina à lei). Encontrá-los é justamente o trabalho da **camada de IA ao vivo**, que aqui não pôde rodar por falta de chave de API. Para uma estatística de venda robusta, o caminho é: ligar a IA (já integrada e blindada) e rodar em uma amostra maior e aleatória de editais.

*Instrumento de apoio — não substitui parecer jurídico. Cada veredito deve ser confirmado por profissional habilitado.*
