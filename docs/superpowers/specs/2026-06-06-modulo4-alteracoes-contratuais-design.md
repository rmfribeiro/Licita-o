# Módulo 4 — Analisador de Alterações Contratuais

**Base legal:** Art. 124 II "d"; Art. 25 §8º; Art. 137 §2º; Art. 92 §3º — Lei 14.133/2021 · Art. 37 XXI CF/88
**Produto:** IA-Licita — RM Vértice Digital
**Data:** 2026-06-06

---

## Visão Geral

O Módulo 4 permite que gestores públicos analisem pedidos de alteração contratual apresentados pela contratada — **reajuste**, **repactuação** e **reequilíbrio econômico-financeiro** —, verificando se o pedido possui fundamento legal adequado, documentação suficiente e metodologia de cálculo correta, à luz da Lei 14.133/2021.

O resultado é um parecer jurídico-técnico gerado por IA (deferível / deferível com ressalvas / indeferível), com os fundamentos legais aplicáveis e as lacunas documentais identificadas, exportável como PDF para instrução do processo administrativo.

---

## Usuário e Caso de Uso

**Usuário:** gestor público, fiscal de contrato, assessor jurídico.

**Situação de uso:** A contratada protocola um pedido de reajuste, repactuação ou reequilíbrio. O gestor precisa: (1) identificar qual tipo de alteração está sendo solicitada; (2) verificar se o pedido atende aos requisitos legais; (3) identificar documentos faltantes; (4) emitir um parecer fundamentado para o processo administrativo.

---

## Os Três Tipos de Alteração

### Reajuste (Art. 25 §8º)
Atualização monetária automática prevista em cláusula contratual, com índice e periodicidade definidos no contrato. Requisitos: (a) cláusula expressa no contrato com índice e data-base; (b) intervalo mínimo de 12 meses contado da data-base; (c) cálculo conforme índice previsto (IPCA, INPC, IGP-M etc.).

### Repactuação (Art. 25 §8º + IN SEGES 5/2017)
Aplicável exclusivamente a contratos de serviços com dedicação exclusiva de mão de obra. Requisitos: (a) variação nos custos trabalhistas demonstrada por Convenção Coletiva de Trabalho (CCT) ou ACT; (b) Planilha de Custos e Formação de Preços atualizada; (c) intervalo mínimo de 12 meses da data-base (data da proposta ou da última repactuação); (d) solicitação dentro do prazo de preclusão (até o encerramento do contrato ou prazo menor definido em edital).

### Reequilíbrio Econômico-Financeiro (Art. 124 II "d" + Art. 37 XXI CF/88)
Restabelecimento da equação econômica-financeira rompida por áleas extraordinárias ou extracontratuais imprevisíveis. Requisitos: (a) evento imprevisível e extraordinário (não álea ordinária); (b) nexo causal entre o evento e o desequilíbrio; (c) comprovação documental do impacto financeiro; (d) memória de cálculo fundamentada; (e) não há prazo mínimo — pode ser solicitado a qualquer tempo durante a vigência.

---

## Fluxo (2 Etapas — sem consulta CNPJ)

### Etapa 1 — Identificação e Documentos
1. Gestor seleciona o tipo de alteração (reajuste / repactuação / reequilíbrio).
2. Informa dados básicos: número do contrato, objeto resumido, data de assinatura, valor atual.
3. Faz upload dos documentos do pedido (PDF/DOCX): requerimento, memória de cálculo, CCT, notas fiscais, planilhas etc.
4. Clica em "Analisar Pedido" → sistema extrai texto via `etp_extrator.extrair_texto()` e chama a IA.

### Etapa 2 — Resultado
1. **Parecer** (DEFERÍVEL / DEFERÍVEL COM RESSALVAS / INDEFERÍVEL) com badge colorido.
2. **Fundamentos legais** aplicados à situação concreta.
3. **Requisitos verificados** — checklist com status (atendido / parcialmente atendido / ausente).
4. **Lacunas documentais** — lista do que falta para instruir o processo.
5. **Recomendações ao gestor** — próximos passos (notificar contratada, solicitar documentos, deferir etc.).
6. **Botão de download do PDF** para anexar ao processo administrativo.

---

## Divisão de Responsabilidades: Local vs. IA

**Validado localmente (sem IA):**
- Tipo de alteração selecionado pelo gestor
- Dados básicos do contrato (número, objeto, data, valor)
- Extração de texto dos documentos

**Retornado pela IA (análise qualitativa):**
- Verificação dos requisitos legais por tipo de alteração
- Identificação de lacunas documentais
- Parecer conclusivo (DEFERÍVEL / DEFERÍVEL COM RESSALVAS / INDEFERÍVEL)
- Fundamentos legais aplicáveis
- Recomendações ao gestor

A IA **não** faz cálculos financeiros (reajuste = novo valor etc.) — apenas analisa se a metodologia apresentada é juridicamente adequada.

---

## Estrutura JSON retornada pela IA

```json
{
  "parecer": "DEFERÍVEL|DEFERÍVEL COM RESSALVAS|INDEFERÍVEL",
  "tipo_alteracao": "reajuste|repactuacao|reequilibrio",
  "requisitos": [
    {
      "descricao": "Cláusula de reajuste expressa no contrato com índice e data-base",
      "status": "ATENDIDO|PARCIAL|AUSENTE",
      "observacao": "Texto explicativo opcional"
    }
  ],
  "lacunas_documentais": ["Documento X não localizado", "..."],
  "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021", "..."],
  "recomendacoes": ["Solicitar à contratada a CCT vigente", "..."],
  "sintese": "Parágrafo explicando o parecer e os principais fundamentos"
}
```

---

## Arquitetura de Arquivos

### Novos arquivos

**`ia_contratos.py`**
- `TIPOS_ALTERACAO: MappingProxyType[str, str]` — rótulos dos 3 tipos
- `REQUISITOS_POR_TIPO: MappingProxyType[str, tuple[str, ...]]` — lista de requisitos por tipo
- `STATUS_REQUISITO: MappingProxyType[str, str]` — ATENDIDO / PARCIAL / AUSENTE
- `PARECER_OPTIONS: MappingProxyType[str, str]` — DEFERÍVEL / DEFERÍVEL COM RESSALVAS / INDEFERÍVEL
- `_SISTEMA_POR_TIPO: dict[str, str]` — system prompt específico por tipo de alteração
- `_chamar_anthropic(prompt, api_key, modelo) -> str`
- `analisar(tipo, dados_contrato, texto_docs, api_key, modelo) -> dict`

**`relatorio_contratos.py`**
- `gerar_pdf(dados_contrato, tipo, parecer) -> bytes`
- Seções: cabeçalho · identificação do contrato · badge do parecer · requisitos (checklist) · lacunas documentais · fundamentos legais · recomendações · rodapé

### Arquivos modificados

**`app.py`**
- Adiciona Tab 6: `⚖️ Alterações Contratuais`
- Importa `ia_contratos`, `relatorio_contratos`
- Reutiliza `etp_extrator.extrair_texto()` para upload de documentos
- State keys: `cont_etapa`, `cont_tipo`, `cont_dados`, `cont_parecer`, `cont_pdf`

### Arquivos de teste

**`tests/test_ia_contratos.py`**
- Testa `TIPOS_ALTERACAO`, `REQUISITOS_POR_TIPO`, `STATUS_REQUISITO`
- Testa `analisar()` com mock da API (3 tipos × cenários básicos)
- Testa erro HTTP e resposta não-dict

**`tests/test_relatorio_contratos.py`**
- Smoke test: `gerar_pdf()` retorna bytes não vazios com magic bytes `%PDF`
- Testa os 3 tipos de parecer sem crash
- Testa lista de requisitos vazia sem crash

---

## Cores e Status

| Parecer | Cor |
|---------|-----|
| DEFERÍVEL | `#27AE60` (verde — COR_STATUS["ok"]) |
| DEFERÍVEL COM RESSALVAS | `#F39C12` (laranja — alerta) |
| INDEFERÍVEL | `#C0392B` (vermelho — COR_STATUS["critico"]) |

| Requisito | Cor |
|-----------|-----|
| ATENDIDO | verde |
| PARCIAL | laranja |
| AUSENTE | vermelho |

Reutiliza `COR_STATUS_HEX` de `ia_utils.py`.

---

## Tratamento de Erros

- Nenhum documento enviado: IA analisa apenas os dados informados e sinaliza que a análise é limitada (sem erro — comportamento esperado para triagem rápida).
- Falha na API Anthropic: `RuntimeError` com mensagem descritiva (padrão dos outros módulos).
- JSON malformado: `_extrair_json` de `ia_utils.py` com repair robusto (padrão existente).
- Tipo de alteração inválido: validação local antes de chamar a IA.

---

## Fora de Escopo

- Cálculo automático do valor do reajuste/repactuação (requer índices em tempo real).
- Consulta automática a CNIS, RAIS ou sistemas de convenções coletivas.
- Módulo 4-A (Cumprimento de Obrigações): recebimentos provisório/definitivo — futuro.
- Geração automática de ofício à contratada (futuro).
