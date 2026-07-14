# ia_integridade.py — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar o módulo `ia_integridade.py` que diagnostica o Programa de Integridade Pública (PIP) de prefeituras via questionário + documentos, gera parecer com nível de maturidade (INEXISTENTE → INICIAL → EM DESENVOLVIMENTO → CONSOLIDADO), e expõe o resultado numa Tab 4 do app Streamlit com download em PDF.

**Architecture:** Três arquivos novos (`ia_integridade.py`, `relatorio_integridade.py`, `tests/test_ia_integridade.py`, `tests/test_relatorio_integridade.py`) mais modificação do `app.py`. O módulo `ia_integridade.py` segue o mesmo padrão de `ia_ddi.py` e `ia_etp.py`: `_SISTEMA` + `_ESTRUTURA_PARECER` + `_chamar_anthropic()` via `urllib` + função pública `diagnosticar()`. A lógica de piso de maturidade é separada em `_aplicar_piso()` para ser testável isoladamente.

**Tech Stack:** Python 3.11+, urllib (stdlib), reportlab (já instalado), streamlit, pytest + unittest.mock.

---

## Mapa de arquivos

| Ação | Arquivo | Responsabilidade |
|---|---|---|
| Criar | `ia_integridade.py` | Lógica de IA: prompt, chamada Anthropic, piso de maturidade |
| Criar | `relatorio_integridade.py` | Geração do PDF com reportlab |
| Criar | `tests/test_ia_integridade.py` | Testes de `_aplicar_piso` e `diagnosticar` |
| Criar | `tests/test_relatorio_integridade.py` | Testes de `gerar_pdf` |
| Modificar | `app.py` | Imports + Tab 4 (destructuring obrigatório: 3→4 tabs) |

---

## Task 1: ia_integridade.py — piso de maturidade (TDD)

**Files:**
- Create: `tests/test_ia_integridade.py`
- Create: `ia_integridade.py`

- [ ] **Step 1: Escrever os testes de `_aplicar_piso` (ainda vai falhar)**

Criar `tests/test_ia_integridade.py` com o conteúdo abaixo. Neste ponto `ia_integridade` não existe, então os testes vão falhar com `ModuleNotFoundError`.

```python
from __future__ import annotations
import pytest
import ia_integridade


def _nao() -> dict:
    return {k: "Não" for k in ia_integridade._CHAVES_QUESTIONARIO}


def _sim() -> dict:
    return {k: "Sim" for k in ia_integridade._CHAVES_QUESTIONARIO}


class TestAplicarPiso:
    def test_all_nao_retorna_inexistente(self):
        assert ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO") == "INEXISTENTE"

    def test_regra1_tem_precedencia_sobre_regra2(self):
        # All-Não deve produzir INEXISTENTE, não INICIAL
        assert ia_integridade._aplicar_piso(_nao(), "CONSOLIDADO") == "INEXISTENTE"

    def test_ato_formal_nao_responsavel_nao_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_parcialmente_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Parcialmente"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_ato_formal_nao_responsavel_parcialmente_cap_inicial(self):
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Parcialmente"
        assert ia_integridade._aplicar_piso(r, "CONSOLIDADO") == "INICIAL"

    def test_tudo_sim_aceita_resposta_ia(self):
        assert ia_integridade._aplicar_piso(_sim(), "CONSOLIDADO") == "CONSOLIDADO"

    def test_cap_nao_eleva_maturidade(self):
        # Piso nunca eleva — se IA já retornou INICIAL, fica INICIAL
        r = _sim()
        r["q_ato_formal"] = "Não"
        r["q_responsavel_designado"] = "Não"
        assert ia_integridade._aplicar_piso(r, "INICIAL") == "INICIAL"
```

- [ ] **Step 2: Confirmar que os testes falham por ausência do módulo**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_ia_integridade.py -v 2>&1 | head -20
```

Esperado: `ModuleNotFoundError: No module named 'ia_integridade'`

- [ ] **Step 3: Criar `ia_integridade.py` com as constantes e `_aplicar_piso`**

Criar `~/Documents/Daysival/ia_integridade.py`:

```python
from __future__ import annotations
import json
import os
import urllib.request
import urllib.error
try:
    import streamlit as st
    _HAS_ST = True
except ImportError:
    _HAS_ST = False
from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_MATURIDADE_ORDEM = ["INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"]

_CHAVES_QUESTIONARIO = [
    "q_ato_formal", "q_responsavel_designado",
    "q_diretrizes_publicadas", "q_diretrizes_divulgadas",
    "q_base_legal_conhecida",
    "q_mecanismos_responsabilizacao", "q_precedentes_punicao",
    "q_plano_gestao", "q_indicadores",
    "q_primeira_linha", "q_segunda_linha", "q_terceira_linha",
]

_SISTEMA = (
    "Você é um consultor sênior especialista em Programas de Integridade Pública (PIP) "
    "para a Administração Pública municipal brasileira. "
    "Avalie o estágio de maturidade do Programa de Integridade da prefeitura com base nas "
    "respostas do questionário e nos documentos fornecidos, à luz do Decreto 11.129/2022, "
    "da IN CGU 21/2021, da Lei 12.846/2013 (art. 7º, III) e do Decreto 8.420/2015. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "maturidade_geral": "INEXISTENTE|INICIAL|EM DESENVOLVIMENTO|CONSOLIDADO",
  "dimensoes": {
    "compromisso_alta_gestao": {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "diretrizes_integridade":  {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "base_legal_normativa":    {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "responsabilizacao":       {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "metodologia_gestao":      {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]},
    "tres_linhas_defesa":      {"nivel": "...", "achados": ["..."], "recomendacoes": ["..."]}
  },
  "prioridades": ["ação imediata 1", "ação imediata 2", "ação imediata 3"],
  "resumo_executivo": "parágrafo para apresentar ao prefeito",
  "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021", "Lei 12.846/2013, art. 7 III", "Decreto 8.420/2015"]
}"""

_ROTULOS_QUESTIONARIO = {
    "q_ato_formal":                  "Existe ato formal do prefeito instituindo o PIP?",
    "q_responsavel_designado":       "Há responsável formalmente designado pelo PIP?",
    "q_diretrizes_publicadas":       "As diretrizes de integridade foram publicadas?",
    "q_diretrizes_divulgadas":       "As diretrizes foram divulgadas a todos os servidores?",
    "q_base_legal_conhecida":        "A autoridade superior conhece o marco legal do PIP (Decreto 11.129/2022, IN CGU 21/2021)?",
    "q_mecanismos_responsabilizacao":"Existem mecanismos formais de responsabilização de servidores?",
    "q_precedentes_punicao":         "Já houve apuração e punição por irregularidades nesta prefeitura?",
    "q_plano_gestao":                "Existe plano formal de gestão e acompanhamento do PIP?",
    "q_indicadores":                 "Existem indicadores definidos para monitorar o PIP?",
    "q_primeira_linha":              "Gestores de linha conhecem e exercem seus controles de conformidade?",
    "q_segunda_linha":               "Controle interno está estruturado e ativo?",
    "q_terceira_linha":              "Auditoria interna existe e funciona de forma independente?",
}


def _aplicar_piso(respostas: dict, maturidade_ia: str) -> str:
    valores = [str(respostas.get(k) or "Não").strip() for k in _CHAVES_QUESTIONARIO]

    # Regra 1 (mais restritiva) — todos Não → INEXISTENTE
    if all(v == "Não" for v in valores):
        return "INEXISTENTE"

    # Regra 2 — campos críticos ausentes/parciais → cap INICIAL
    ato = str(respostas.get("q_ato_formal") or "Não").strip()
    resp = str(respostas.get("q_responsavel_designado") or "Não").strip()
    if ato in {"Não", "Parcialmente"} and resp in {"Não", "Parcialmente"}:
        idx_ia = _MATURIDADE_ORDEM.index(maturidade_ia) if maturidade_ia in _MATURIDADE_ORDEM else 3
        if idx_ia > _MATURIDADE_ORDEM.index("INICIAL"):
            return "INICIAL"

    return maturidade_ia
```

- [ ] **Step 4: Rodar só os testes de `_aplicar_piso` e confirmar que passam**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_ia_integridade.py::TestAplicarPiso -v
```

Esperado: 7 testes PASS.

---

## Task 2: ia_integridade.py — `diagnosticar` (TDD)

**Files:**
- Modify: `tests/test_ia_integridade.py` (adiciona `TestDiagnosticar`)
- Modify: `ia_integridade.py` (adiciona `_chamar_anthropic` e `diagnosticar`)

- [ ] **Step 1: Adicionar `TestDiagnosticar` ao arquivo de testes**

Adicionar ao final de `tests/test_ia_integridade.py`:

```python
import json
from unittest.mock import patch, MagicMock


def _parecer_mock(maturidade: str = "EM DESENVOLVIMENTO") -> dict:
    return {
        "maturidade_geral": maturidade,
        "dimensoes": {
            "compromisso_alta_gestao": {"nivel": maturidade, "achados": ["a"], "recomendacoes": ["r"]},
            "diretrizes_integridade":  {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "base_legal_normativa":    {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "responsabilizacao":       {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "metodologia_gestao":      {"nivel": maturidade, "achados": [], "recomendacoes": []},
            "tres_linhas_defesa":      {"nivel": maturidade, "achados": [], "recomendacoes": []},
        },
        "prioridades": ["Ação 1", "Ação 2", "Ação 3"],
        "resumo_executivo": "Resumo para o prefeito.",
        "base_legal": ["Decreto 11.129/2022"],
    }


def _mock_urlopen(parecer: dict):
    payload = json.dumps({"content": [{"text": json.dumps(parecer)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(
        return_value=MagicMock(read=MagicMock(return_value=payload))
    )
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestDiagnosticar:
    @patch("ia_integridade.urllib.request.urlopen")
    def test_retorna_estrutura_correta(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for campo in ("maturidade_geral", "dimensoes", "prioridades", "resumo_executivo", "base_legal"):
            assert campo in resultado, f"Campo ausente: {campo}"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_6_dimensoes_presentes(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        for dim in (
            "compromisso_alta_gestao", "diretrizes_integridade", "base_legal_normativa",
            "responsabilizacao", "metodologia_gestao", "tres_linhas_defesa",
        ):
            assert dim in resultado["dimensoes"], f"Dimensão ausente: {dim}"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_maturidade_valida(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] in (
            "INEXISTENTE", "INICIAL", "EM DESENVOLVIMENTO", "CONSOLIDADO"
        )

    @patch("ia_integridade.urllib.request.urlopen")
    def test_piso_aplicado_all_nao(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock("CONSOLIDADO"))
        resultado = ia_integridade.diagnosticar(_nao(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"

    @patch("ia_integridade.urllib.request.urlopen")
    def test_texto_docs_incluido_no_prompt(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        ia_integridade.diagnosticar(_sim(), "DOCUMENTO_MARCADOR_XYZ", "sk-test")
        corpo = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert "DOCUMENTO_MARCADOR_XYZ" in corpo["messages"][0]["content"]

    @patch("ia_integridade.urllib.request.urlopen")
    def test_ddi_context_incluido_se_fornecido(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        parecer_ddi = {
            "dimensoes": {
                "programa_integridade": {
                    "status": "critico",
                    "descricao": "Sem programa formal",
                    "obrigatorio": True,
                    "pro_etica": False,
                }
            }
        }
        ia_integridade.diagnosticar(_sim(), None, "sk-test", parecer_ddi=parecer_ddi)
        corpo = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        prompt = corpo["messages"][0]["content"]
        assert "critico" in prompt

    @patch("ia_integridade.urllib.request.urlopen")
    def test_ddi_none_nao_quebra(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_mock())
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test", parecer_ddi=None)
        assert "maturidade_geral" in resultado

    @patch("ia_integridade.urllib.request.urlopen")
    def test_maturidade_invalida_da_ia_normalizada_para_inexistente(self, mock_urlopen):
        parecer_ruim = _parecer_mock()
        parecer_ruim["maturidade_geral"] = "DESCONHECIDO"
        mock_urlopen.return_value = _mock_urlopen(parecer_ruim)
        resultado = ia_integridade.diagnosticar(_sim(), None, "sk-test")
        assert resultado["maturidade_geral"] == "INEXISTENTE"
```

- [ ] **Step 2: Rodar os novos testes para confirmar que falham**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_ia_integridade.py::TestDiagnosticar -v 2>&1 | head -20
```

Esperado: `AttributeError` ou `ImportError` — `diagnosticar` não existe ainda.

- [ ] **Step 3: Adicionar `_chamar_anthropic` e `diagnosticar` ao `ia_integridade.py`**

Adicionar ao final de `ia_integridade.py` (após `_aplicar_piso`):

```python
def _chamar_anthropic(prompt: str, api_key: str, modelo: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 3000,
        "system": _SISTEMA,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=corpo,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        dados = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in dados.get("content", []))


def diagnosticar(
    respostas: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
    parecer_ddi: dict | None = None,
) -> dict:
    partes = ["Questionário sobre o Programa de Integridade Pública da prefeitura:\n"]
    for chave, pergunta in _ROTULOS_QUESTIONARIO.items():
        partes.append(f"- {pergunta} Resposta: {respostas.get(chave, 'Não informado')}")

    if texto_docs:
        partes.append(f"\nDocumentos da prefeitura fornecidos:\n{texto_docs[:30000]}")

    if parecer_ddi:
        pi = parecer_ddi.get("dimensoes", {}).get("programa_integridade", {})
        if pi:
            partes.append(
                f"\nContexto DDI (Due Diligence de fornecedor relacionado):\n"
                f"- Status do programa de integridade: {pi.get('status', '-')}\n"
                f"- Descrição: {pi.get('descricao', '-')}\n"
                f"- Programa obrigatório: {pi.get('obrigatorio', '-')}\n"
                f"- Empresa Pró-Ética: {pi.get('pro_etica', '-')}"
            )

    partes.append(f"\nRetorne o diagnóstico no formato:\n{_ESTRUTURA_PARECER}")

    try:
        bruto = _chamar_anthropic("\n".join(partes), api_key, modelo)
        parecer = _extrair_json(bruto)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc
    except (ValueError, Exception) as exc:
        raise RuntimeError(f"Resposta inesperada da API: {exc}") from exc

    if not isinstance(parecer, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(parecer).__name__}"
        )

    _mat = str(parecer.get("maturidade_geral") or "INEXISTENTE").strip().upper()
    if _mat not in _MATURIDADE_ORDEM:
        _mat = "INEXISTENTE"
    parecer["maturidade_geral"] = _aplicar_piso(respostas, _mat)

    return parecer
```

- [ ] **Step 4: Rodar todos os testes do módulo**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_ia_integridade.py -v
```

Esperado: 15 testes PASS.

- [ ] **Step 5: Verificar sintaxe e rodar suite completa**

```bash
cd ~/Documents/Daysival && python -m py_compile ia_integridade.py && python -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: todos os testes existentes continuam passando + 15 novos.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Daysival && git add ia_integridade.py tests/test_ia_integridade.py && git commit -m "$(cat <<'EOF'
feat: ia_integridade.py — diagnóstico PIP com piso de maturidade e integração DDI

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: relatorio_integridade.py (TDD)

**Files:**
- Create: `tests/test_relatorio_integridade.py`
- Create: `relatorio_integridade.py`

> **Nota:** A assinatura do spec original inclui `respostas: dict`, mas a estrutura do documento (§6 do spec) não exibe o questionário — esse parâmetro não tem uso. O plano implementa `gerar_pdf(municipio, parecer)` sem `respostas`, consistente com o padrão de `relatorio_etp.gerar_pdf`.

- [ ] **Step 1: Escrever os testes**

Criar `tests/test_relatorio_integridade.py`:

```python
from __future__ import annotations
import pytest
import relatorio_integridade


def _parecer() -> dict:
    return {
        "maturidade_geral": "INICIAL",
        "dimensoes": {
            "compromisso_alta_gestao": {
                "nivel": "INEXISTENTE",
                "achados": ["Nenhum ato formal publicado."],
                "recomendacoes": ["Publicar decreto de instituição do PIP."],
            },
            "diretrizes_integridade":  {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
            "base_legal_normativa":    {"nivel": "INICIAL",     "achados": [], "recomendacoes": []},
            "responsabilizacao":       {"nivel": "INICIAL",     "achados": [], "recomendacoes": []},
            "metodologia_gestao":      {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
            "tres_linhas_defesa":      {"nivel": "INEXISTENTE", "achados": [], "recomendacoes": []},
        },
        "prioridades": ["Publicar decreto.", "Designar responsável.", "Criar código de ética."],
        "resumo_executivo": "O programa está em estágio inicial e requer ação imediata.",
        "base_legal": ["Decreto 11.129/2022", "IN CGU 21/2021"],
    }


class TestGerarPdf:
    def test_retorna_bytes(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", _parecer())
        assert isinstance(resultado, bytes)
        assert len(resultado) > 1000

    def test_pdf_comeca_com_magic_bytes(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", _parecer())
        assert resultado[:4] == b"%PDF"

    def test_municipio_vazio_nao_quebra(self):
        resultado = relatorio_integridade.gerar_pdf("", _parecer())
        assert isinstance(resultado, bytes)

    def test_parecer_vazio_nao_quebra(self):
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", {})
        assert isinstance(resultado, bytes)

    def test_dimensoes_vazias_nao_quebra(self):
        p = _parecer()
        p["dimensoes"] = {}
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", p)
        assert isinstance(resultado, bytes)

    def test_prioridades_vazias_nao_quebra(self):
        p = _parecer()
        p["prioridades"] = []
        resultado = relatorio_integridade.gerar_pdf("Ilha Solteira/SP", p)
        assert isinstance(resultado, bytes)
```

- [ ] **Step 2: Confirmar que os testes falham**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_relatorio_integridade.py -v 2>&1 | head -10
```

Esperado: `ModuleNotFoundError: No module named 'relatorio_integridade'`

- [ ] **Step 3: Criar `relatorio_integridade.py`**

Criar `~/Documents/Daysival/relatorio_integridade.py`:

```python
from __future__ import annotations
import html
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_COR_MATURIDADE = {
    "CONSOLIDADO":       colors.HexColor("#27AE60"),
    "EM DESENVOLVIMENTO": colors.HexColor("#2980B9"),
    "INICIAL":           colors.HexColor("#F39C12"),
    "INEXISTENTE":       colors.HexColor("#C0392B"),
}
_COR_NIVEL_HEX = {
    "CONSOLIDADO":       "#27AE60",
    "EM DESENVOLVIMENTO": "#2980B9",
    "INICIAL":           "#F39C12",
    "INEXISTENTE":       "#C0392B",
}
_LABEL_DIMENSAO = {
    "compromisso_alta_gestao": "Compromisso da Alta Gestão",
    "diretrizes_integridade":  "Diretrizes de Integridade",
    "base_legal_normativa":    "Base Legal e Normativa",
    "responsabilizacao":       "Responsabilização",
    "metodologia_gestao":      "Metodologia de Gestão",
    "tres_linhas_defesa":      "Três Linhas de Defesa",
}


def gerar_pdf(municipio: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    estilos = getSampleStyleSheet()
    titulo   = ParagraphStyle("titulo", parent=estilos["Title"],    fontSize=16, spaceAfter=4)
    h2       = ParagraphStyle("h2",    parent=estilos["Heading2"],  fontSize=12, spaceAfter=3)
    corpo    = ParagraphStyle("corpo", parent=estilos["Normal"],    fontSize=10, spaceAfter=3)
    pequeno  = ParagraphStyle("peq",   parent=estilos["Normal"],    fontSize=8,
                              textColor=colors.grey)

    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", titulo))
    story.append(Paragraph("Diagnóstico do Programa de Integridade Pública", estilos["Heading1"]))
    story.append(Paragraph(
        "Decreto 11.129/2022 · IN CGU 21/2021 · Lei 12.846/2013, art. 7º, III · Decreto 8.420/2015",
        pequeno,
    ))
    story.append(Paragraph(f"Município: {html.escape(str(municipio or ''))}", pequeno))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", pequeno))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Nível de maturidade geral
    maturidade = str(parecer.get("maturidade_geral") or "INEXISTENTE").strip().upper()
    cor = _COR_MATURIDADE.get(maturidade, colors.grey)
    story.append(Paragraph("Nível de Maturidade Geral", h2))
    t_mat = Table(
        [[Paragraph(
            f"<b>{html.escape(maturidade)}</b>",
            ParagraphStyle("m", fontSize=14, textColor=colors.white, alignment=1),
        )]],
        colWidths=[17*cm],
    )
    t_mat.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_mat)
    story.append(Spacer(1, 0.4*cm))

    # Resumo executivo
    resumo = str(parecer.get("resumo_executivo") or "")
    if resumo:
        story.append(Paragraph("Resumo Executivo", h2))
        story.append(Paragraph(html.escape(resumo), corpo))
        story.append(Spacer(1, 0.3*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", h2))
    dims = parecer.get("dimensoes") or {}
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave) or {}
        nivel = str(dim.get("nivel") or "INEXISTENTE").strip().upper()
        cor_n = _COR_NIVEL_HEX.get(nivel, "#000000")
        story.append(Paragraph(
            f"<b>{html.escape(label)}</b> — "
            f"<font color='{cor_n}'><b>{html.escape(nivel)}</b></font>",
            corpo,
        ))
        for achado in (dim.get("achados") or []):
            if achado:
                story.append(Paragraph(f"  • {html.escape(str(achado))}", corpo))
        for rec in (dim.get("recomendacoes") or []):
            if rec:
                story.append(Paragraph(f"  → {html.escape(str(rec))}", corpo))
        story.append(Spacer(1, 0.2*cm))

    # Prioridades imediatas
    prioridades = parecer.get("prioridades") or []
    if prioridades:
        story.append(Paragraph("Prioridades Imediatas", h2))
        for i, p in enumerate(prioridades, 1):
            if p:
                story.append(Paragraph(f"{i}. {html.escape(str(p))}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    story.append(Paragraph("Base Legal", h2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", corpo))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        pequeno,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Rodar os testes**

```bash
cd ~/Documents/Daysival && python -m pytest tests/test_relatorio_integridade.py -v
```

Esperado: 6 testes PASS.

- [ ] **Step 5: Rodar suite completa**

```bash
cd ~/Documents/Daysival && python -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: todos os testes passando (sem regressões).

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Daysival && git add relatorio_integridade.py tests/test_relatorio_integridade.py && git commit -m "$(cat <<'EOF'
feat: relatorio_integridade.py — PDF de diagnóstico PIP com badge de maturidade

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: app.py — Tab 4 (Diagnóstico de Integridade)

**Files:**
- Modify: `app.py`

> **Atenção crítica:** Há dois lugares para atualizar: (1) a lista de `st.tabs` e (2) o destructuring. Atualizar só um levanta `ValueError` na inicialização.

- [ ] **Step 1: Adicionar imports no topo de `app.py`**

Localizar o bloco de imports existente (linhas 13–20) e adicionar as duas novas linhas:

```python
import ia_integridade
import relatorio_integridade
```

O bloco de imports deve ficar:

```python
import analisador as A
import branding
import ddi_consultas
import ia_ddi
import relatorio_ddi
import etp_extrator
import ia_etp
import relatorio_etp
import ia_integridade
import relatorio_integridade
```

- [ ] **Step 2: Atualizar `st.tabs()` — lista + destructuring juntos**

Localizar a linha 67:
```python
aba1, aba2, aba3 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
])
```

Substituir por:
```python
aba1, aba2, aba3, aba4 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
])
```

- [ ] **Step 3: Adicionar o bloco `with aba4:` ao final de `app.py`**

Adicionar após o bloco `with aba3:` existente (após a linha 404):

```python
with aba4:
    st.subheader("Diagnóstico do Programa de Integridade Pública")
    st.caption(
        "Decreto 11.129/2022 · IN CGU 21/2021 · Lei 12.846/2013, art. 7º, III · Decreto 8.420/2015"
    )

    _api_key_pip = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_pip:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_pip = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
    _modelo_pip = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _municipio_pip = st.text_input("Nome do município", key="pip_municipio")

    st.markdown("**Questionário — 12 perguntas sobre o PIP**")
    _PERGUNTAS_PIP = [
        ("q_ato_formal",                  "1. Existe ato formal do prefeito instituindo o PIP?"),
        ("q_responsavel_designado",        "2. Há responsável formalmente designado pelo PIP?"),
        ("q_diretrizes_publicadas",        "3. As diretrizes de integridade foram publicadas?"),
        ("q_diretrizes_divulgadas",        "4. As diretrizes foram divulgadas a todos os servidores?"),
        ("q_base_legal_conhecida",         "5. A autoridade superior conhece o marco legal do PIP (Decreto 11.129/2022)?"),
        ("q_mecanismos_responsabilizacao", "6. Existem mecanismos formais de responsabilização de servidores?"),
        ("q_precedentes_punicao",          "7. Já houve apuração e punição por irregularidades nesta prefeitura?"),
        ("q_plano_gestao",                 "8. Existe plano formal de gestão e acompanhamento do PIP?"),
        ("q_indicadores",                  "9. Existem indicadores definidos para monitorar o PIP?"),
        ("q_primeira_linha",               "10. Gestores de linha conhecem e exercem seus controles de conformidade?"),
        ("q_segunda_linha",                "11. Controle interno está estruturado e ativo?"),
        ("q_terceira_linha",               "12. Auditoria interna existe e funciona de forma independente?"),
    ]
    _respostas_pip = {}
    for _chave_pip, _pergunta_pip in _PERGUNTAS_PIP:
        _respostas_pip[_chave_pip] = st.selectbox(
            _pergunta_pip,
            ["Sim", "Não", "Parcialmente"],
            key=f"pip_{_chave_pip}",
        )

    _arqs_pip = st.file_uploader(
        "Documentos da prefeitura (opcional — PDF ou Word)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="pip_arquivos",
    )

    if st.button("Gerar Diagnóstico", type="primary", key="btn_pip", disabled=not _municipio_pip):
        if not _api_key_pip:
            st.error("ANTHROPIC_API_KEY não configurada — configure via variável de ambiente ou secrets.toml.")
        else:
            try:
                with st.spinner("Analisando programa de integridade com IA (pode levar 1-2 minutos)..."):
                    _texto_pip, _avisos_pip = (
                        etp_extrator.extrair_texto(_arqs_pip) if _arqs_pip else (None, [])
                    )
                    _parecer_pip = ia_integridade.diagnosticar(
                        _respostas_pip,
                        _texto_pip,
                        _api_key_pip,
                        _modelo_pip,
                        st.session_state.get("ddi_parecer"),
                    )
                st.session_state["pip_parecer"] = _parecer_pip
                st.session_state["pip_municipio"] = _municipio_pip
                st.session_state["pip_avisos"] = _avisos_pip
            except (ValueError, RuntimeError) as _e:
                st.error(str(_e))

    if "pip_parecer" in st.session_state:
        _pr_pip = st.session_state["pip_parecer"]
        _mun_pip = st.session_state.get("pip_municipio", "")
        _av_pip  = st.session_state.get("pip_avisos", [])

        for _aviso in _av_pip:
            st.warning(_aviso)

        st.divider()
        _mat_pip = str(_pr_pip.get("maturidade_geral") or "INEXISTENTE").strip().upper()
        _icone_mat = {
            "CONSOLIDADO": "🟢", "EM DESENVOLVIMENTO": "🔵",
            "INICIAL": "🟡",    "INEXISTENTE": "🔴",
        }
        st.subheader(f"{_icone_mat.get(_mat_pip, '⚪')} Maturidade Geral: {_mat_pip}")

        _resumo_pip = str(_pr_pip.get("resumo_executivo") or "")
        if _resumo_pip:
            st.info(_resumo_pip)

        _LABEL_DIM_PIP = {
            "compromisso_alta_gestao": "Compromisso da Alta Gestão",
            "diretrizes_integridade":  "Diretrizes de Integridade",
            "base_legal_normativa":    "Base Legal e Normativa",
            "responsabilizacao":       "Responsabilização",
            "metodologia_gestao":      "Metodologia de Gestão",
            "tres_linhas_defesa":      "Três Linhas de Defesa",
        }
        _icone_nivel = {
            "CONSOLIDADO": "🟢", "EM DESENVOLVIMENTO": "🔵",
            "INICIAL": "🟡",    "INEXISTENTE": "🔴",
        }
        _dims_pip = _pr_pip.get("dimensoes") or {}
        for _ch, _lb in _LABEL_DIM_PIP.items():
            _d   = _dims_pip.get(_ch) or {}
            _niv = str(_d.get("nivel") or "INEXISTENTE").strip().upper()
            _ic  = _icone_nivel.get(_niv, "⚪")
            with st.expander(f"{_ic} {_lb} — {_niv}"):
                for _ach in (_d.get("achados") or []):
                    if _ach:
                        st.warning(_ach)
                for _rec in (_d.get("recomendacoes") or []):
                    if _rec:
                        st.info(_rec)

        _prio_pip = _pr_pip.get("prioridades") or []
        if _prio_pip:
            st.subheader("Prioridades Imediatas")
            for _i, _p in enumerate(_prio_pip, 1):
                if _p:
                    st.error(f"{_i}. {_p}")

        with st.expander("Base Legal"):
            for _bl in (_pr_pip.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_bl}")

        try:
            _pdf_pip = relatorio_integridade.gerar_pdf(_mun_pip, _pr_pip)
            _nome_pdf = f"PIP_{_mun_pip.replace('/', '-').replace(' ', '_')}.pdf"
            st.download_button(
                label="Baixar Relatório PDF",
                data=_pdf_pip,
                file_name=_nome_pdf,
                mime="application/pdf",
            )
        except Exception as _e:
            st.error(f"Erro ao gerar PDF: {_e}")
```

- [ ] **Step 4: Verificar sintaxe**

```bash
cd ~/Documents/Daysival && python -m py_compile app.py && echo "Sintaxe OK"
```

Esperado: `Sintaxe OK`

- [ ] **Step 5: Rodar suite completa de testes**

```bash
cd ~/Documents/Daysival && python -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: todos os testes passando.

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Daysival && git add app.py && git commit -m "$(cat <<'EOF'
feat: Tab 4 — Diagnóstico de Integridade Pública no app Streamlit

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

### Cobertura do spec

| Seção do spec | Coberta? | Onde |
|---|---|---|
| §5 Função pública `diagnosticar` | ✅ | Task 2, Step 3 |
| §5 Questionário 12 perguntas | ✅ | `_ROTULOS_QUESTIONARIO` + Task 4 |
| §5 Estrutura JSON do parecer | ✅ | `_ESTRUTURA_PARECER` |
| §5 Lógica de piso (Regra 1 antes Regra 2) | ✅ | Task 1 — `_aplicar_piso` |
| §5 Integração DDI — caminho exato `dimensoes.programa_integridade` | ✅ | Task 2, Step 3 |
| §5 Todos os 4 campos DDI incluídos no prompt | ✅ | Task 2, Step 3 |
| §6 `gerar_pdf(municipio, parecer)` | ✅ | Task 3 |
| §6 Badge colorido por nível | ✅ | `_COR_MATURIDADE` |
| §6 Resumo executivo, dimensões, prioridades, base legal, rodapé | ✅ | Task 3, Step 3 |
| §7 api_key resolvida em Tab 4 | ✅ | Task 4, Step 3 |
| §7 st.tabs destructuring 3→4 | ✅ | Task 4, Step 2 — nota explícita |
| §7 extrair_texto só chamado se arquivos presentes | ✅ | Task 4, Step 3 |
| §7 DDI de sessão aproveitado | ✅ | `st.session_state.get("ddi_parecer")` |
