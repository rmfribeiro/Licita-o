# Módulo 5 — Dosimetria de Sanções Administrativas e Crimes em Licitações

**Data:** 2026-06-07
**Status:** Aprovado
**Base legal:** Arts. 156-159 e 178, Lei 14.133/2021

---

## Contexto

O Módulo 5 auxilia o **gestor do órgão público** a aplicar sanções administrativas a fornecedores infratores, fundamentando juridicamente a dosimetria e gerando a minuta do ato administrativo. Inclui alerta quando a conduta também configura crime (Art. 178), com orientação para representação ao Ministério Público.

---

## Arquitetura

Segue o padrão dos demais módulos do projeto:

| Arquivo | Responsabilidade |
|---|---|
| `ia_sancoes.py` | Lógica de IA: duas chamadas sequenciais (dosimetria + minuta) |
| `relatorio_sancoes.py` | Geração de PDF com duas seções (parecer + minuta) |
| `app.py` | Nova aba 8 — "⚖️ Dosimetria de Sanções" |

Reutiliza `etp_extrator.extrair_texto()` para extração de PDF/DOCX e `ia_utils.chamar_anthropic()` / `ia_utils.extrair_json()` para chamadas à API.

**Fluxo:**
```
Upload PDF/DOCX
  → etp_extrator.extrair_texto()
  → ia_sancoes.analisar_dosimetria()   ← 1ª chamada IA (parecer estruturado)
  → ia_sancoes.gerar_minuta(parecer)   ← 2ª chamada IA (texto do ato)
  → relatorio_sancoes.gerar_pdf()
  → Download PDF
```

---

## Entradas do Formulário

| Campo | Tipo | Obrigatório | Uso |
|---|---|---|---|
| Documento (relatório / termo de ocorrência) | Upload PDF ou DOCX | Sim | Fonte dos fatos para a IA |
| CNPJ do fornecedor | Texto (14 dígitos) | Sim | Preenche a minuta |
| Número do contrato | Texto | Sim | Preenche a minuta |
| Valor do contrato (R$) | Numérico | Sim | Base de cálculo da multa (Arts. 158) |
| Reincidência do fornecedor? | Sim / Não / Não verificado | Sim | Agravante (Art. 157, III) |
| Autoridade competente | Texto (ex: "Secretário Municipal de Obras") | Sim | Assina a minuta |
| Órgão/Entidade | Texto (ex: "Prefeitura de São Paulo") | Sim | Cabeçalho da minuta |

A reincidência é informada pelo gestor (não há API pública de histórico de sanções) e passada como contexto explícito ao prompt.

---

## 1ª Chamada de IA — Parecer de Dosimetria

**Sistema:** especialista em direito administrativo sancionador, Lei 14.133/2021, Arts. 156-159 e 178. Com sufixo de segurança padrão do projeto.

**Prompt:** inclui texto do documento extraído (até 30.000 chars), dados do contrato, CNPJ, valor e reincidência.

**Estrutura JSON retornada:**

```json
{
  "fatos_apurados": "resumo objetivo dos fatos extraídos do documento",
  "condutas_identificadas": ["inexecução parcial do contrato", "atraso injustificado"],
  "enquadramento": {
    "tipo_sancao": "advertencia | multa | impedimento | inidoneidade",
    "artigo": "Art. 156, II, Lei 14.133/2021",
    "justificativa": "fundamentação da escolha da sanção"
  },
  "dosimetria": {
    "percentual_multa": 10.0,
    "valor_multa_estimado": 15000.00,
    "prazo_sancao": null,
    "nivel_gravidade": "LEVE | MÉDIO | GRAVE",
    "agravantes": ["reincidência", "dano ao erário"],
    "atenuantes": ["colaboração com a apuração"]
  },
  "alerta_criminal": {
    "configura_crime": false,
    "artigo_178": null,
    "descricao_conduta": null,
    "recomendacao": null
  },
  "base_legal": [
    "Art. 156, II, Lei 14.133/2021",
    "Art. 157, Lei 14.133/2021",
    "Art. 158, §1º, Lei 14.133/2021"
  ]
}
```

**Semântica dos campos de dosimetria por tipo de sanção:**
- `advertencia` → `percentual_multa` e `valor_multa_estimado` ignorados; `prazo_sancao` nulo
- `multa` → `percentual_multa` entre 0.5 e 30% (Art. 158); `prazo_sancao` nulo
- `impedimento` → `percentual_multa` ignorado; `prazo_sancao` em anos (até 3 anos, Art. 156, III)
- `inidoneidade` → `percentual_multa` ignorado; `prazo_sancao` em anos (3 a 6 anos, Art. 156, IV)

**Normalização pós-parse:**
- `tipo_sancao` validado contra frozenset de valores válidos; fallback: `"multa"`
- `nivel_gravidade` normalizado para maiúsculas; fallback: `"MÉDIO"`
- `percentual_multa` clampado entre 0.5 e 30.0 somente quando `tipo_sancao == "multa"`
- `configura_crime` garantido como bool

---

## 2ª Chamada de IA — Minuta do Ato Administrativo

**Entrada:** parecer da 1ª chamada + dados do formulário (CNPJ, contrato, valor, autoridade, órgão).

**Sistema:** especialista em redação de atos administrativos, portarias e decisões de processos administrativos sancionadores.

**Saída:** string com o texto completo da portaria/decisão, incluindo:
- Cabeçalho (órgão, número do ato, data)
- Considerandos (fatos apurados, enquadramento legal)
- Dispositivo (sanção aplicada, percentual/valor da multa quando aplicável, prazo de recurso de 15 dias úteis conforme Art. 157, §4º)
- Local para assinatura da autoridade competente

A minuta é retornada como campo `"minuta"` (string) dentro de um JSON simples: `{"minuta": "..."}`.

---

## Interface — Aba 8

**Label:** `"⚖️ Dosimetria de Sanções"`

**Fluxo linear (sem etapas separadas):**

1. Formulário com todos os campos e upload
2. Botão "Analisar Infração" (desabilitado sem arquivo)
3. Spinner: "Analisando infração e gerando dosimetria (pode levar 2-3 minutos)..."
4. Resultado:
   - Badge colorido com sanção sugerida:
     - 🟡 Advertência
     - 🟠 Multa
     - 🔴 Impedimento de licitar e contratar
     - ⛔ Declaração de inidoneidade
   - Fatos apurados (caixa informativa)
   - Tabela: gravidade / agravantes / atenuantes / % multa / valor estimado
   - Alerta vermelho (st.error) se `configura_crime == true`, com artigo e recomendação ao MP
   - Expander "Base Legal"
   - Expander "Minuta do Ato Administrativo" (texto completo para revisão)
5. Botão "⬇️ Baixar Relatório PDF"

---

## PDF — Duas Seções

**Seção 1: Parecer de Dosimetria**
- Cabeçalho IA-Licita / RM Vértice Digital
- Identificação (CNPJ formatado, contrato, órgão, autoridade, data)
- Fatos apurados
- Enquadramento legal e sanção sugerida (badge colorido)
- Tabela de dosimetria (gravidade, agravantes, atenuantes, % e valor da multa)
- Alerta criminal (caixa destacada em vermelho, se aplicável)
- Base legal

**Seção 2: Minuta do Ato Administrativo**
- Separador visual (linha + título "MINUTA — Para revisão e assinatura")
- Texto da minuta em fonte monoespaçada ou com fundo cinza claro para distinguir do parecer
- Nota de rodapé: "Sujeito a revisão jurídica antes da assinatura"

---

## Tratamento de Erros

- Arquivo sem texto extraível (OCR) → `st.warning` + interrompe
- API Anthropic indisponível → `RuntimeError` capturado → `st.error`
- JSON inválido na 1ª chamada → `RuntimeError` → `st.error`
- Falha na 2ª chamada (minuta) → exibe parecer normalmente + aviso de que a minuta não pôde ser gerada (não bloqueia o PDF parcial)
- PDF falhou → aviso persistente (padrão estabelecido no code review)

---

## Testes

- `tests/test_ia_sancoes.py`:
  - `analisar_dosimetria` retorna dict com todas as chaves obrigatórias
  - `tipo_sancao` normalizado corretamente para valores inválidos
  - `percentual_multa` clampado entre 0.5 e 30.0
  - `configura_crime` é sempre bool
  - Falha de API levanta `RuntimeError`
- `tests/test_relatorio_sancoes.py`:
  - `gerar_pdf` retorna bytes com conteúdo (len > 0)
  - Sem erro quando `alerta_criminal.configura_crime == false`
  - Sem erro quando minuta está vazia (2ª chamada falhou)
