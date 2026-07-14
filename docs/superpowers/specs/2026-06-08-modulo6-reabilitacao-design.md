# Módulo 6 — Reabilitação de Fornecedor: Design Spec

**Data:** 2026-06-08
**Status:** Aprovado

---

## Objetivo

Ferramenta de análise de elegibilidade e geração de documentos para reabilitação de fornecedor sancionado, fundamentada no Art. 163, Parágrafo Único, Lei 14.133/2021. Suporta as duas modalidades de sanção (Art. 156, III — impedimento de licitar; Art. 156, IV — declaração de inidoneidade) com fluxo de 3 etapas em aba única.

---

## Approach A — Fluxo 3 etapas em aba única

Único fluxo linear: identificação + dados → análise de elegibilidade → resultado + PDFs. Aprovado como abordagem de implementação.

---

## Arquitetura

### Novos arquivos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `ia_reabilitacao.py` | Constantes legais, cálculo de prazo mínimo, análise de elegibilidade via IA |
| `relatorio_reabilitacao.py` | Dois geradores de PDF: relatório técnico + minuta do requerimento |
| `tests/test_ia_reabilitacao.py` | Testes unitários do módulo de análise |
| `tests/test_relatorio_reabilitacao.py` | Testes dos geradores de PDF |

### Arquivo modificado

| Arquivo | Mudança |
|---------|---------|
| `app.py` | Nova aba9 "🔄 Reabilitação de Fornecedor" |

### Reuso sem modificação

| Arquivo | Como reutilizado |
|---------|-----------------|
| `ddi_consultas.py` | `consultar_ceis()` e `consultar_cnep()` — lookup automático por CNPJ, filtrado para Art. 156 III e IV |
| `etp_extrator.py` | Upload e extração de texto de documentos comprobatórios (PDF/DOCX) |

### Fluxo de dados

```
CNPJ → ddi_consultas (CEIS/CNEP automático)
     + campos manuais (tipo sanção, data, órgão, multa, condições do ato)
     + respostas do questionário de condições
     + documentos comprobatórios (opcional)
         → ia_reabilitacao.analisar()
             → parecer {ELEGÍVEL | ELEGÍVEL COM RESSALVAS | INELEGÍVEL}
                 → relatorio_reabilitacao.gerar_relatorio_tecnico()
                 → relatorio_reabilitacao.gerar_minuta_requerimento()
```

---

## Base Legal

**Art. 163, Parágrafo Único, Lei 14.133/2021** — 5 condições cumulativas para reabilitação:

| # | Condição | Como verificar |
|---|----------|----------------|
| I | Reparação integral do dano à Administração | Campo manual: Sim / Parcial / Não / N.A. + descrição livre |
| II | Pagamento de multa eventualmente aplicada | Campos: multa aplicada? (Sim/Não); se Sim → multa quitada? (Sim/Não) |
| III | Transcurso do prazo mínimo | **Calculado automaticamente**: 1 ano (Art. 156, III) ou 3 anos (Art. 156, IV) a partir da data de aplicação da sanção |
| IV | Cumprimento das condições do ato punitivo | Textarea para descrever condições + radio Cumpridas? (Sim / Parcial / Não / N.A.) |
| V | Análise jurídica prévia com posicionamento conclusivo | Radio: Realizada / Em andamento / Não realizada — IA inclui ressalva automática se não concluída |

**Prazos mínimos (Condição III):**
- Art. 156, III (impedimento de licitar): 1 ano contado da data de aplicação
- Art. 156, IV (declaração de inidoneidade): 3 anos contados da data de aplicação
- Prazo não decorrido → parecer `INELEGÍVEL` imediato, sem chamar a IA

---

## UI — Etapas da Aba

### Etapa 1 — Identificação e Dados da Sanção

```
CNPJ: [____________] [Consultar CEIS/CNEP]

Tipo de Sanção:
  ◉ Impedimento de Licitar e Contratar (Art. 156, III)  — prazo mínimo: 1 ano
  ○ Declaração de Inidoneidade (Art. 156, IV)           — prazo mínimo: 3 anos

Data de aplicação da sanção: [DD/MM/AAAA]
Órgão/Entidade sancionadora: [_____________]

--- Resultado automático CEIS/CNEP ---
(tabela com registros encontrados, ou aviso se ausente)

Multa foi aplicada?   ○ Sim  ○ Não
  [se Sim] Valor: R$ [_____]   Quitada? ○ Sim  ○ Não

Condições definidas no ato punitivo:
[textarea]

[Verificar Elegibilidade →]
```

### Etapa 2 — Questionário das Condições

```
Condição I — Reparação integral do dano:
  ○ Sim (integral)  ○ Parcial  ○ Não  ○ N.A.
  Descrição/comprovação: [_________]

Condição III — Prazo mínimo:
  ✅ Decorrido (X anos, Y meses desde DD/MM/AAAA)
  ❌ Não decorrido — faltam Z meses (reabilitação ainda não possível)

Condição IV — Condições do ato punitivo cumpridas:
  ○ Sim  ○ Parcial  ○ Não  ○ N.A.

Condição V — Análise jurídica prévia:
  ○ Realizada  ○ Em andamento  ○ Não realizada

Documentos comprobatórios (opcional):
[upload múltiplos arquivos PDF/DOCX]

[Analisar Elegibilidade →]
```

### Etapa 3 — Resultado

```
┌────────────────────────────────────────┐
│  ELEGÍVEL COM RESSALVAS                │  (badge colorido)
└────────────────────────────────────────┘

Condição I  (Reparação):             ✅ Atendida
Condição II (Multa):                 ✅ Atendida
Condição III (Prazo mínimo):         ✅ Decorrido (2a 3m)
Condição IV (Ato punitivo):          ⚠️ Parcialmente atendida
Condição V  (Análise jurídica):      ⚠️ Em andamento

Síntese: [texto gerado pela IA — fundamentado no Art. 163 Par. Único]

[⬇ Relatório Técnico (PDF)]    [⬇ Minuta do Requerimento (PDF)]
```

---

## `ia_reabilitacao.py`

### Constantes

```python
TIPOS_SANCAO: MappingProxyType[str, str]
# {"impedimento": "Impedimento de Licitar e Contratar (Art. 156, III)",
#  "inidoneidade": "Declaração de Inidoneidade (Art. 156, IV)"}

PRAZOS_MINIMOS_ANOS: MappingProxyType[str, int]
# {"impedimento": 1, "inidoneidade": 3}

PARECER_OPTIONS: MappingProxyType[str, str]
# {"ELEGÍVEL": "ELEGÍVEL", "ELEGÍVEL COM RESSALVAS": "ELEGÍVEL COM RESSALVAS",
#  "INELEGÍVEL": "INELEGÍVEL"}

NORM_PARECER_REAB: MappingProxyType[str, str]
# aliases sem acento → forma canônica com acento
```

### Funções

```python
def calcular_prazo(tipo_sancao: str, data_aplicacao: date) -> dict:
    """Retorna {atendido: bool, anos_decorridos: int, meses_decorridos: int,
               prazo_minimo_anos: int}"""

def analisar(
    tipo_sancao: str,
    dados_empresa: dict,       # razao_social, cnpj, ceis, cnep
    dados_sancao: dict,        # data_aplicacao, orgao, multa_aplicada,
                               # multa_quitada, condicoes_ato_punitivo
    respostas_condicoes: dict, # reparacao, cond_ato_cumpridas, analise_juridica
                               # (condição II derivada de dados_sancao.multa_*)
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    """
    Guarda de prazo: se prazo não decorrido → retorna INELEGÍVEL sem
    chamar a IA (economiza token).
    Retorna: {parecer, condicoes_avaliadas: [...], sintese, base_legal,
              dados_empresa, dados_sancao}
    """
```

**Estrutura JSON esperada da IA:**

```json
{
  "parecer": "ELEGÍVEL|ELEGÍVEL COM RESSALVAS|INELEGÍVEL",
  "condicoes_avaliadas": [
    {
      "numero": "I",
      "descricao": "Reparação integral do dano",
      "status": "ATENDIDA|PARCIAL|AUSENTE|N.A.",
      "observacao": "..."
    }
  ],
  "sintese": "Parágrafo conclusivo fundamentado no Art. 163 Par. Único",
  "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"]
}
```

**Normalização pós-IA:** aliases sem acento mapeados para canônicos (`ELEGIVEL` → `ELEGÍVEL`, `INELEGIVEL` → `INELEGÍVEL`), mesma estratégia de `NORM_PARECER_CONT` em `ia_contratos.py`.

---

## `relatorio_reabilitacao.py`

```python
def gerar_relatorio_tecnico(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,
) -> bytes:
    """
    PDF interno para arquivo do órgão. Seções:
    1. Cabeçalho IA-Licita + data geração
    2. Identificação da empresa (razão social, CNPJ, porte, sanção)
    3. Badge de elegibilidade (verde/amarelo/vermelho)
    4. Tabela das 5 condições com status (✅/⚠️/❌)
    5. Síntese gerada pela IA
    6. Base legal (Art. 163, Par. Único, Lei 14.133/2021)
    7. Rodapé: "sujeito a verificação humana"
    """

def gerar_minuta_requerimento(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,
) -> bytes:
    """
    PDF formal para protocolo junto ao órgão sancionador. Seções:
    1. Título: "REQUERIMENTO DE REABILITAÇÃO"
    2. Qualificação do requerente (razão social, CNPJ)
    3. Dos fatos: sanção aplicada, data, órgão, tipo (Art. 156, III ou IV)
    4. Do direito: Art. 163, Par. Único — 5 condições cumpridas por extenso
    5. Do pedido: reabilitação nos termos do Art. 163
    6. Local, data e linha de assinatura
    7. Rodapé: "Minuta gerada por IA-Licita — revisar antes de protocolar"
    """
```

**Segurança de strings:** todos os campos dinâmicos passam por `html.escape()` antes de entrar em `Paragraph()` ou células de tabela — mesma disciplina de `relatorio_ddi.py`.

---

## Testes

### `tests/test_ia_reabilitacao.py`

**`calcular_prazo`:**
- Prazo atendido: impedimento, data há 2 anos → `{atendido: True}`
- Prazo não atendido: inidoneidade, data há 1 ano → `{atendido: False}`
- Exatamente no limite: data há exatamente 1 ano → `{atendido: True}` (condição é `>=` prazo mínimo)
- `tipo_sancao` inválido → `ValueError`

**`analisar`:**
- Prazo não decorrido → retorna `INELEGÍVEL` sem chamar API (mock verifica 0 chamadas à API)
- Todas condições OK → API mockada retorna `ELEGÍVEL` → normalizado corretamente
- Alias sem acento `"ELEGIVEL"` → normalizado para `"ELEGÍVEL"`
- `tipo_sancao` inválido → `ValueError` antes de chamar API
- API retorna JSON malformado → `RuntimeError`
- API retorna não-dict → `RuntimeError`
- `HTTPError` da API → `RuntimeError` com mensagem HTTP

### `tests/test_relatorio_reabilitacao.py`

**`gerar_relatorio_tecnico`:**
- Retorna bytes não-vazio com parecer `ELEGÍVEL`
- Caracteres especiais em `razao_social` não quebram PDF (html.escape)

**`gerar_minuta_requerimento`:**
- Retorna bytes não-vazio
- Tipo `impedimento` → "Art. 156, III" no conteúdo
- Tipo `inidoneidade` → "Art. 156, IV" no conteúdo

**Total estimado:** ~15 testes novos, estrutura `unittest.TestCase` + `pytest`.

---

## Restrições

- `ANTHROPIC_API_KEY` nunca exposta em chat — somente via variável de ambiente
- `CGU_API_KEY` idem
- Tokens GitHub (`ghp_*`) idem
