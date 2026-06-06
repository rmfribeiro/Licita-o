# Módulo 3 — Avaliação do Programa de Integridade (PI) de Empresas

**Base legal:** Decreto 12.304/2024, Art. 1º, I-III, Parágrafo Único
**Produto:** IA-Licita — RM Vértice Digital
**Data:** 2026-06-05

---

## Visão Geral

O Módulo 3 permite que gestores públicos avaliem o Programa de Integridade (PI) de
empresas licitantes ou contratadas, à luz do Decreto 12.304/2024. O módulo cobre as
três hipóteses legais de exigência/avaliação do PI: contratações de grande vulto,
desempate entre licitantes, e reabilitação de fornecedor.

O resultado é um parecer qualitativo gerado por IA, um score de aderência por
parâmetro (0–100) e um relatório PDF para fins de arquivo e decisão administrativa.

**Coexistência:** o `ia_integridade.py` existente (Tab 4) continua operando para
diagnóstico do Programa de Integridade Pública municipal (Decreto 11.129/2022).
O Módulo 3 é uma nova aba (Tab 5) com escopo distinto: PI de empresas privadas,
OSCs e administração pública sob o Decreto 12.304/2024.

---

## Usuário e Caso de Uso

**Usuário:** gestor público (servidor, pregoeiro, controlador interno).

**Situação de uso:** O gestor precisa registrar/documentar que avaliou o PI de uma
empresa antes de contratar (grande vulto), para desempate de propostas, ou para
deliberar sobre reabilitação de fornecedor punido.

---

## Fluxo de 3 Etapas

### Etapa 1 — Identificação

1. Gestor informa CNPJ da empresa e seleciona a hipótese legal.
2. Sistema consulta Receita Federal via `ddi_consultas.consultar_empresa(cnpj)`.
3. Exibe: Razão Social, Porte, Situação Cadastral, CNAE Principal, Data de Abertura.
4. Se hipótese = Grande Vulto e porte ≠ Grande Empresa: exibe aviso sobre o
   enquadramento obrigatório (> R$ 239M).
5. Gestor confirma e avança.

### Etapa 2 — Questionário

1. Apresenta os 17 parâmetros agrupados em 5 dimensões (expanders no Streamlit).
2. Cada parâmetro: radio com 3 opções → Não existe (0) | Parcialmente (50) | Implementado (100).
3. Upload opcional de documentos (PDF/DOCX): regulamento interno, código de ética,
   relatório do PI, etc.
4. Ao submeter, chama `ia_pi_empresas.avaliar()` com respostas + hipótese + texto extraído.

### Etapa 3 — Resultado

1. Score geral (0–100) + nível de maturidade com badge colorido.
2. Tabela de score por dimensão com barra de progresso.
3. Conclusão específica para a hipótese (texto gerado pela IA).
4. Pontos críticos (lista).
5. Análise por dimensão com achados e recomendações (expanders).
6. Botão de download do PDF.

---

## Os 17 Parâmetros (Decreto 12.304/2024)

### Dimensão 1 — Comprometimento da Alta Direção
- P1: Política formal de integridade aprovada e publicada pela alta direção
- P2: Responsável formalmente designado com autonomia e recursos adequados
- P3: Programa incluído no planejamento estratégico e orçamento da empresa

### Dimensão 2 — Análise de Riscos
- P4: Mapeamento e análise periódica de riscos de integridade
- P5: Procedimentos internos adaptados ao perfil de risco da empresa

### Dimensão 3 — Estrutura de Controles
- P6: Código de ética ou conduta formal
- P7: Canal de denúncias ativo, acessível, com garantia de anonimato
- P8: Política de conflito de interesses
- P9: Treinamentos periódicos de integridade para colaboradores
- P10: Due diligence de terceiros (fornecedores, parceiros, agentes)
- P11: Controles sobre doações, patrocínios, brindes e hospitalidade
- P12: Procedimentos de integridade em interações com o setor público

### Dimensão 4 — Monitoramento e Melhoria Contínua
- P13: Auditorias internas ou externas periódicas do programa
- P14: Indicadores (KPIs) de efetividade do programa
- P15: Investigações internas e ações corretivas aplicadas

### Dimensão 5 — Transparência e Comunicação
- P16: Registros contábeis e financeiros íntegros e auditáveis
- P17: Relatório periódico do programa publicado ou disponível para consulta

---

## Scoring e Maturidade

### Cálculo do score

| Resposta | Valor |
|----------|-------|
| Não existe | 0 |
| Parcialmente implementado | 50 |
| Implementado | 100 |

- **Score por dimensão:** média simples dos parâmetros da dimensão.
- **Score geral:** média ponderada das dimensões. Pesos padrão (iguais por dimensão):
  Comprometimento 20% · Riscos 15% · Controles 35% · Monitoramento 20% · Transparência 10%.
  Pesos podem ser ajustados por hipótese no futuro sem quebrar a interface.

### Nível de maturidade

| Score | Nível |
|-------|-------|
| 0–24 | INEXISTENTE |
| 25–49 | INICIAL |
| 50–74 | EM DESENVOLVIMENTO |
| 75–100 | CONSOLIDADO |

Reutiliza `COR_MATURIDADE_HEX` de `ia_integridade.py` para consistência visual.

### Regras de piso por hipótese

| Hipótese | Regra |
|----------|-------|
| `grande_vulto` | PI obrigatório (Decreto 12.304/2024, Art. 4º). Score < 50 → conclusão indica **impedimento à contratação**. |
| `desempate` | PI usado como critério de mérito (Lei 14.133/2021, Art. 60, IV). Sem impedimento — maior score vence o desempate. |
| `reabilitacao` | Avalia trajetória de melhoria (Lei 14.133/2021, Art. 163, Par. Único). Foco em tendência e comprometimento, não em patamar absoluto. |

---

## Arquitetura de Arquivos

### Novos arquivos

**`ia_pi_empresas.py`**
- Constantes: `DIMENSOES_PI`, `QUESTOES_PI`, `HIPOTESES`, `PESOS_DIMENSAO`
- `_SISTEMA` — system prompt para o modelo Claude
- `_ESTRUTURA_PARECER` — template JSON esperado da IA
- `calcular_scores(respostas) -> dict` — calcula score por parâmetro, por dimensão e geral
- `nivel_maturidade(score: float) -> str` — converte score em nível
- `avaliar(respostas, hipotese, texto_docs, api_key, modelo) -> dict` — chama a IA e retorna parecer completo com scores

**`relatorio_pi_empresas.py`**
- `gerar_pdf(cnpj, razao_social, hipotese, parecer) -> bytes`
- Seções: cabeçalho · identificação · score geral + maturidade · tabela de scores por dimensão · conclusão da hipótese · pontos críticos · análise por dimensão · recomendações · rodapé

### Arquivos modificados

**`app.py`**
- Adiciona Tab 5: `🏢 Avaliação de PI`
- Importa `ia_pi_empresas`, `relatorio_pi_empresas`
- Reutiliza `ddi_consultas.consultar_empresa()` (sem alterar `ddi_consultas.py`)
- State keys: `pi_etapa`, `pi_dados_empresa`, `pi_hipotese`, `pi_respostas`, `pi_parecer`

### Arquivos de teste

**`tests/test_ia_pi_empresas.py`**
- `calcular_scores`: todos implementados → 100, todos não existem → 0, misto
- `nivel_maturidade`: limites de faixa (0, 24, 25, 49, 50, 74, 75, 100)
- `avaliar`: mock da API → JSON válido → dict estruturado
- Regras de piso: grande_vulto score < 50 → texto de impedimento presente

**`tests/test_relatorio_pi_empresas.py`**
- `gerar_pdf` com parecer mínimo → retorna `bytes` não vazios

---

## Divisão de responsabilidades: local vs. IA

**Calculado localmente** (determinístico, não depende da IA):
- Score por parâmetro (0 / 50 / 100 das respostas do questionário)
- Score por dimensão (média simples dos parâmetros)
- Score geral (média ponderada das dimensões)
- Nível de maturidade geral (derivado do score via `nivel_maturidade()`)

**Retornado pela IA** (análise qualitativa):
- Achados e recomendações por parâmetro
- Síntese qualitativa por dimensão
- Pontos críticos
- Conclusão específica para a hipótese
- Recomendações gerais
- Base legal aplicável

Essa separação garante scores determinísticos e auditáveis, enquanto a IA
foca no que faz melhor: análise qualitativa e linguagem jurídica contextualizada.

## Estrutura JSON retornada pela IA

```json
{
  "dimensoes": {
    "comprometimento_alta_direcao": {
      "sintese": "Alta direção demonstra comprometimento formal, mas falta orçamento próprio.",
      "parametros": {
        "p1": {"achados": ["Política publicada no site institucional"], "recomendacoes": []},
        "p2": {"achados": ["CCO designado por portaria interna"], "recomendacoes": []},
        "p3": {"achados": ["PI mencionado no planejamento, sem orçamento próprio"], "recomendacoes": ["Alocar linha orçamentária exclusiva para o PI"]}
      }
    },
    "analise_riscos": {
      "sintese": "...",
      "parametros": { "p4": {"achados": [], "recomendacoes": []}, "p5": {"achados": [], "recomendacoes": []} }
    },
    "estrutura_controles": { "sintese": "...", "parametros": { "p6": {}, "p7": {}, "p8": {}, "p9": {}, "p10": {}, "p11": {}, "p12": {} } },
    "monitoramento_melhoria": { "sintese": "...", "parametros": { "p13": {}, "p14": {}, "p15": {} } },
    "transparencia": { "sintese": "...", "parametros": { "p16": {}, "p17": {} } }
  },
  "pontos_criticos": ["Canal de denúncias sem garantia de anonimato documentada"],
  "conclusao_hipotese": "Texto específico para a hipótese selecionada (grande_vulto | desempate | reabilitacao).",
  "recomendacoes": ["Formalizar orçamento do PI", "Documentar protocolo de anonimato do canal"],
  "base_legal": ["Decreto 12.304/2024, Art. 4º", "Lei 14.133/2021, Art. 60, IV"]
}
```

---

## Tratamento de Erros

- CNPJ inválido ou não encontrado na Receita: mensagem de erro na Etapa 1, sem avançar.
- Falha na API Anthropic: `RuntimeError` com mensagem descritiva (padrão dos outros módulos).
- JSON malformado da IA: `_extrair_json` de `ia_utils.py` com repair robusto (padrão existente).
- Scores calculados localmente antes de chamar a IA — a IA não retorna scores, apenas análise
  qualitativa. Isso garante determinismo e auditabilidade dos resultados numéricos.

---

## Fora de Escopo

- Avaliação de PI para administração pública e OSCs (Art. 1º, II e III do Decreto 12.304/2024)
  — escopo futuro, mesma arquitetura, sistema prompt diferente.
- Módulo 7 (Desempate por PI) e Módulo 6 (Reabilitação) como abas separadas — por ora
  são hipóteses dentro do Módulo 3.
- Consulta automática a bases externas do PI (ex: Empresa Pró-Ética) além da já existente
  em `ddi_consultas.py`.
