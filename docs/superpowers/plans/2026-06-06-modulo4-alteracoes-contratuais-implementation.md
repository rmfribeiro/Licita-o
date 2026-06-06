# Módulo 4 — Analisador de Alterações Contratuais Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Tab 6 to IA-Licita that lets a public manager upload documents and get an AI-generated legal opinion on whether a contract alteration request (reajuste, repactuação, or reequilíbrio) should be deferred, deferred with caveats, or denied.

**Architecture:** Three new files (`ia_contratos.py`, `relatorio_contratos.py`, and their test counterparts) plus a Tab 6 block appended to `app.py`. `ia_contratos.py` holds constants + `analisar()` which calls Claude via `urllib`; `relatorio_contratos.py` generates a PDF with ReportLab. The pattern mirrors Módulo 3 (`ia_pi_empresas.py` / `relatorio_pi_empresas.py`) exactly. No CNPJ lookup — this is a 2-step flow: fill form → view result.

**Tech Stack:** Python 3.9, Streamlit, ReportLab, pytest + unittest.mock, `urllib` (no SDK), Claude Haiku (`claude-haiku-4-5-20251001`).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `ia_contratos.py` | Create | Constants, `_chamar_anthropic()`, `analisar()` |
| `relatorio_contratos.py` | Create | `gerar_pdf()` — PDF with badge + checklist |
| `tests/test_ia_contratos.py` | Create | 17 unit tests (constants + analisar) |
| `tests/test_relatorio_contratos.py` | Create | 4 smoke tests |
| `app.py` | Modify | Add `import ia_contratos`, `import relatorio_contratos`, 6th tab |

---

## Context for Every Task

### Codebase conventions (read before implementing)
- All public constant dicts → `types.MappingProxyType` (see `ia_pi_empresas.py` lines 12–73)
- API calls → `urllib.request.urlopen`, never the Anthropic SDK
- JSON extraction → `from ia_utils import extrair_json as _extrair_json`
- Error handling: `HTTPError` → `RuntimeError("Falha na API Anthropic: HTTP {code} ...")`, `URLError`/`OSError` → `RuntimeError("Falha na API Anthropic: ...")`, non-dict response → `RuntimeError("Resposta inesperada da API: objeto JSON esperado, recebeu ...")`
- Local values MUST override AI values: `return {**qualitativo, "tipo_alteracao": tipo, "dados_contrato": dados_contrato}` (local keys at the end — see `ia_pi_empresas.py` line 244–248)
- Style names must be module-prefixed to avoid ReportLab singleton conflicts: use `"cont_titulo"`, `"cont_h1"` etc. (see `relatorio_pi_empresas.py` lines 18–23 for `"pi_*"` prefix)
- PDF magic bytes check: `assert pdf[:4] == b"%PDF"` in the smoke test

### Existing passing tests baseline
Run `python3 -m pytest tests/ -q --tb=no` — must show 115 passed before starting.

---

## Task 1: `ia_contratos.py` — Core Logic

**Files:**
- Create: `ia_contratos.py`
- Create: `tests/test_ia_contratos.py`

- [ ] **Step 1: Write `tests/test_ia_contratos.py`**

```python
from __future__ import annotations
import json
import types
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_contratos


class TestConstantes:
    def test_tipos_alteracao_tem_3_tipos(self):
        assert len(ia_contratos.TIPOS_ALTERACAO) == 3

    def test_chaves_tipos_sao_corretas(self):
        assert set(ia_contratos.TIPOS_ALTERACAO.keys()) == {
            "reajuste", "repactuacao", "reequilibrio"
        }

    def test_requisitos_cobre_todos_tipos(self):
        for tipo in ia_contratos.TIPOS_ALTERACAO:
            assert tipo in ia_contratos.REQUISITOS_POR_TIPO

    def test_reajuste_tem_ao_menos_3_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["reajuste"]) >= 3

    def test_repactuacao_tem_ao_menos_4_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["repactuacao"]) >= 4

    def test_reequilibrio_tem_ao_menos_4_requisitos(self):
        assert len(ia_contratos.REQUISITOS_POR_TIPO["reequilibrio"]) >= 4

    def test_status_requisito_contem_atendido_parcial_ausente(self):
        assert set(ia_contratos.STATUS_REQUISITO.keys()) == {
            "ATENDIDO", "PARCIAL", "AUSENTE"
        }

    def test_parecer_options_tem_3_opcoes(self):
        assert len(ia_contratos.PARECER_OPTIONS) == 3

    def test_constantes_sao_mapping_proxy(self):
        assert isinstance(ia_contratos.TIPOS_ALTERACAO, types.MappingProxyType)
        assert isinstance(ia_contratos.REQUISITOS_POR_TIPO, types.MappingProxyType)
        assert isinstance(ia_contratos.STATUS_REQUISITO, types.MappingProxyType)
        assert isinstance(ia_contratos.PARECER_OPTIONS, types.MappingProxyType)


def _dados_contrato_mock() -> dict:
    return {
        "numero_contrato": "001/2024",
        "objeto": "Prestação de serviços de limpeza",
        "data_assinatura": "15/01/2024",
        "valor_atual": 500000.0,
    }


def _parecer_api_mock() -> dict:
    return {
        "parecer": "DEFERÍVEL COM RESSALVAS",
        "tipo_alteracao": "reajuste",
        "requisitos": [
            {
                "descricao": "Cláusula de reajuste expressa",
                "status": "ATENDIDO",
                "observacao": "",
            },
            {
                "descricao": "Intervalo mínimo 12 meses",
                "status": "PARCIAL",
                "observacao": "Apenas 11 meses decorridos",
            },
        ],
        "lacunas_documentais": ["Planilha IPCA não anexada"],
        "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
        "recomendacoes": ["Aguardar completar 12 meses da data-base"],
        "sintese": "Pedido atende parcialmente os requisitos legais.",
    }


def _mock_urlopen(qualitativo: dict):
    payload = json.dumps(
        {"content": [{"text": json.dumps(qualitativo)}]}
    ).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(
        return_value=MagicMock(read=MagicMock(return_value=payload))
    )
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAnalisar:
    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Tipo de alteração inválido"):
            ia_contratos.analisar("inexistente", {}, None, "key")

    def test_retorna_dict_com_parecer_e_requisitos(self):
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert "parecer" in r
        assert "requisitos" in r
        assert "sintese" in r

    def test_tipo_alteracao_sempre_local(self):
        api_result = {**_parecer_api_mock(), "tipo_alteracao": "repactuacao"}
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_urlopen(api_result),
        ):
            r = ia_contratos.analisar(
                "reajuste", _dados_contrato_mock(), None, "key_teste"
            )
        assert r["tipo_alteracao"] == "reajuste"

    def test_dados_contrato_preservados_localmente(self):
        dados = _dados_contrato_mock()
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar("reajuste", dados, None, "key_teste")
        assert r["dados_contrato"] == dados

    def test_sem_documentos_nao_levanta_erro(self):
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_urlopen(_parecer_api_mock()),
        ):
            r = ia_contratos.analisar(
                "reequilibrio", _dados_contrato_mock(), None, "key_teste"
            )
        assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=MagicMock(
                read=MagicMock(return_value=b'{"error":"invalid key"}')
            ),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_invalida"
                )

    def test_url_error_levanta_runtime_error(self):
        url_err = urllib.error.URLError(reason="Connection refused")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(RuntimeError):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        payload = json.dumps(
            {"content": [{"text": "[1, 2, 3]"}]}
        ).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_contratos.analisar(
                    "reajuste", _dados_contrato_mock(), None, "key_teste"
                )
```

- [ ] **Step 2: Run tests to verify they fail (module not found)**

```bash
python3 -m pytest tests/test_ia_contratos.py -v --tb=short 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'ia_contratos'`

- [ ] **Step 3: Write `ia_contratos.py`**

```python
from __future__ import annotations
import json
import logging
import types
import urllib.error
import urllib.request

from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_ALTERACAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "reajuste":    "Reajuste (Art. 25 §8º, Lei 14.133/2021)",
    "repactuacao": "Repactuação (Art. 25 §8º + IN SEGES 5/2017)",
    "reequilibrio": "Reequilíbrio Econômico-Financeiro (Art. 124 II 'd' + Art. 37 XXI CF/88)",
})

REQUISITOS_POR_TIPO: types.MappingProxyType[str, tuple[str, ...]] = types.MappingProxyType({
    "reajuste": (
        "Cláusula expressa no contrato com índice de reajuste e data-base definidos",
        "Intervalo mínimo de 12 meses contado da data-base contratual",
        "Cálculo elaborado conforme índice previsto (IPCA, INPC, IGP-M etc.)",
        "Memória de cálculo detalhada apresentada pela contratada",
    ),
    "repactuacao": (
        "Contrato é de serviços com dedicação exclusiva de mão de obra",
        "Convenção Coletiva de Trabalho (CCT) ou ACT vigente apresentada",
        "Planilha de Custos e Formação de Preços atualizada com nova CCT",
        "Intervalo mínimo de 12 meses da data-base (data da proposta ou última repactuação)",
        "Solicitação dentro do prazo de preclusão contratual",
        "Comprovação objetiva da variação nos custos trabalhistas",
    ),
    "reequilibrio": (
        "Evento identificado é imprevisível e extraordinário (não álea ordinária de mercado)",
        "Nexo causal entre o evento e o desequilíbrio econômico-financeiro demonstrado",
        "Comprovação documental do impacto financeiro (notas, cotações, laudos)",
        "Memória de cálculo fundamentada com valores precisos antes e após o evento",
        "Equação econômico-financeira original identificada no contrato ou proposta",
    ),
})

STATUS_REQUISITO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDO": "ATENDIDO",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "DEFERÍVEL":                "DEFERÍVEL",
    "DEFERÍVEL COM RESSALVAS":  "DEFERÍVEL COM RESSALVAS",
    "INDEFERÍVEL":              "INDEFERÍVEL",
})

_SISTEMA_POR_TIPO: dict[str, str] = {
    "reajuste": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REAJUSTE contratual à luz do Art. 25 §8º da Lei 14.133/2021. "
        "Verifique se há cláusula expressa de reajuste com índice e data-base, se o intervalo "
        "mínimo de 12 meses foi respeitado e se a memória de cálculo está correta. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "repactuacao": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REPACTUAÇÃO contratual à luz do Art. 25 §8º da Lei 14.133/2021 e "
        "IN SEGES 5/2017. Verifique se o contrato é de serviços com mão de obra dedicada, se há "
        "CCT ou ACT, planilha de custos atualizada, prazo de preclusão e comprovação dos novos custos. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "reequilibrio": (
        "Você é um consultor jurídico especialista em contratos administrativos brasileiros. "
        "Analise pedidos de REEQUILÍBRIO ECONÔMICO-FINANCEIRO à luz do Art. 124 II 'd' da "
        "Lei 14.133/2021 e Art. 37 XXI da CF/88. Verifique se o evento é imprevisível e "
        "extraordinário, se há nexo causal comprovado e documentação suficiente do impacto. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
}

_ESTRUTURA_PARECER = """{
  "parecer": "DEFERÍVEL|DEFERÍVEL COM RESSALVAS|INDEFERÍVEL",
  "tipo_alteracao": "reajuste|repactuacao|reequilibrio",
  "requisitos": [
    {
      "descricao": "Descrição do requisito verificado",
      "status": "ATENDIDO|PARCIAL|AUSENTE",
      "observacao": "Observação explicativa (pode ser vazio)"
    }
  ],
  "lacunas_documentais": ["Documento X não localizado ou insuficiente"],
  "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
  "recomendacoes": ["Próxima ação recomendada ao gestor público"],
  "sintese": "Parágrafo explicando o parecer conclusivo e seus principais fundamentos."
}"""


def _chamar_anthropic(prompt: str, api_key: str, modelo: str, sistema: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 4000,
        "system": sistema,
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


def analisar(
    tipo: str,
    dados_contrato: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if tipo not in TIPOS_ALTERACAO:
        raise ValueError(
            f"Tipo de alteração inválido: '{tipo}'. Esperado: {list(TIPOS_ALTERACAO)}"
        )

    partes = [
        f"Análise de Pedido de Alteração Contratual — {TIPOS_ALTERACAO[tipo]}\n",
        f"Número do Contrato: {dados_contrato.get('numero_contrato') or 'não informado'}",
        f"Objeto: {dados_contrato.get('objeto') or 'não informado'}",
        f"Data de Assinatura: {dados_contrato.get('data_assinatura') or 'não informada'}",
        f"Valor Atual: R$ {float(dados_contrato.get('valor_atual') or 0):.2f}",
        f"\nRequisitos legais a verificar para {TIPOS_ALTERACAO[tipo]}:",
    ]
    for i, req in enumerate(REQUISITOS_POR_TIPO[tipo], 1):
        partes.append(f"{i}. {req}")

    if texto_docs:
        partes.append(
            f"\nDocumentos fornecidos pelo gestor:\n{texto_docs[:30000]}"
        )
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize as lacunas documentais que impedem a análise completa."
        )

    partes.append(
        f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}"
    )

    try:
        bruto = _chamar_anthropic(
            "\n".join(partes), api_key, modelo, _SISTEMA_POR_TIPO[tipo]
        )
        qualitativo = _extrair_json(bruto)
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(
            f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}"
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Resposta inesperada da API: {exc}") from exc

    if not isinstance(qualitativo, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(qualitativo).__name__}"
        )

    return {**qualitativo, "tipo_alteracao": tipo, "dados_contrato": dados_contrato}
```

- [ ] **Step 4: Run tests — expect 17 passed**

```bash
python3 -m pytest tests/test_ia_contratos.py -v --tb=short 2>&1 | tail -25
```

Expected: `17 passed`

- [ ] **Step 5: Run full suite — expect 132 passed**

```bash
python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: `132 passed, 1 warning`

- [ ] **Step 6: Commit**

```bash
git add ia_contratos.py tests/test_ia_contratos.py
git commit -m "feat: Módulo 4 — ia_contratos.py + 17 testes"
```

---

## Task 2: `relatorio_contratos.py` — PDF Generator

**Files:**
- Create: `relatorio_contratos.py`
- Create: `tests/test_relatorio_contratos.py`

- [ ] **Step 1: Write `tests/test_relatorio_contratos.py`**

```python
from __future__ import annotations
import relatorio_contratos


def _dados_contrato_mock() -> dict:
    return {
        "numero_contrato": "001/2024",
        "objeto": "Prestação de serviços de limpeza predial",
        "data_assinatura": "15/01/2024",
        "valor_atual": 500000.0,
    }


def _parecer_completo_mock() -> dict:
    return {
        "parecer": "DEFERÍVEL COM RESSALVAS",
        "tipo_alteracao": "reajuste",
        "dados_contrato": _dados_contrato_mock(),
        "requisitos": [
            {
                "descricao": "Cláusula de reajuste expressa no contrato",
                "status": "ATENDIDO",
                "observacao": "Cláusula 12ª prevê IPCA anual",
            },
            {
                "descricao": "Intervalo mínimo de 12 meses",
                "status": "PARCIAL",
                "observacao": "Apenas 11 meses decorridos",
            },
            {
                "descricao": "Memória de cálculo apresentada",
                "status": "AUSENTE",
                "observacao": "",
            },
        ],
        "lacunas_documentais": ["Planilha de cálculo IPCA não anexada"],
        "fundamentos_legais": ["Art. 25 §8º, Lei 14.133/2021"],
        "recomendacoes": ["Aguardar 1 mês para completar a data-base"],
        "sintese": "O pedido atende parcialmente os requisitos legais.",
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reajuste",
            parecer=_parecer_completo_mock(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_todos_os_tipos_de_parecer_nao_quebram(self):
        for tipo_parecer in [
            "DEFERÍVEL",
            "DEFERÍVEL COM RESSALVAS",
            "INDEFERÍVEL",
        ]:
            parecer = _parecer_completo_mock()
            parecer["parecer"] = tipo_parecer
            pdf = relatorio_contratos.gerar_pdf(
                dados_contrato=_dados_contrato_mock(),
                tipo="repactuacao",
                parecer=parecer,
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_requisitos_vazios_nao_quebra(self):
        parecer = _parecer_completo_mock()
        parecer["requisitos"] = []
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reequilibrio",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_listas_nulas_nao_quebram(self):
        parecer = _parecer_completo_mock()
        parecer["lacunas_documentais"] = None
        parecer["recomendacoes"] = None
        parecer["fundamentos_legais"] = None
        pdf = relatorio_contratos.gerar_pdf(
            dados_contrato=_dados_contrato_mock(),
            tipo="reajuste",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
```

- [ ] **Step 2: Run tests — expect failure**

```bash
python3 -m pytest tests/test_relatorio_contratos.py -v --tb=short 2>&1 | head -15
```

Expected: `ModuleNotFoundError: No module named 'relatorio_contratos'`

- [ ] **Step 3: Write `relatorio_contratos.py`**

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
from ia_utils import COR_STATUS_HEX as _COR_STATUS
from ia_contratos import TIPOS_ALTERACAO

_COR_PARECER = {
    "DEFERÍVEL":               colors.HexColor(_COR_STATUS["ok"]),
    "DEFERÍVEL COM RESSALVAS": colors.HexColor("#F39C12"),
    "INDEFERÍVEL":             colors.HexColor(_COR_STATUS["critico"]),
}

_COR_REQUISITO = {
    "ATENDIDO": colors.HexColor(_COR_STATUS["ok"]),
    "PARCIAL":  colors.HexColor("#F39C12"),
    "AUSENTE":  colors.HexColor(_COR_STATUS["critico"]),
}

_estilos_base    = getSampleStyleSheet()
_ESTILO_TITULO   = ParagraphStyle("cont_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1       = ParagraphStyle("cont_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2       = ParagraphStyle("cont_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO    = ParagraphStyle("cont_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO  = ParagraphStyle("cont_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE    = ParagraphStyle("cont_badge",   parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_REQ_OK   = ParagraphStyle("cont_req_ok",  parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["ok"]))
_ESTILO_REQ_PAR  = ParagraphStyle("cont_req_par", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor("#F39C12"))
_ESTILO_REQ_AUS  = ParagraphStyle("cont_req_aus", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["critico"]))

_ICONE_REQ = {"ATENDIDO": "✓ ATENDIDO", "PARCIAL": "⚠ PARCIAL", "AUSENTE": "✗ AUSENTE"}
_ESTILO_REQ_MAP = {
    "ATENDIDO": _ESTILO_REQ_OK,
    "PARCIAL":  _ESTILO_REQ_PAR,
    "AUSENTE":  _ESTILO_REQ_AUS,
}


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(dados_contrato: dict, tipo: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Analisador de Alterações Contratuais", _ESTILO_H1))
    story.append(Paragraph(
        "Art. 124 II 'd' · Art. 25 §8º · Art. 137 §2º — Lei 14.133/2021 · Art. 37 XXI CF/88",
        _ESTILO_PEQUENO,
    ))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}",
        _ESTILO_PEQUENO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação do Contrato
    story.append(Paragraph("Identificação do Contrato", _ESTILO_H2))
    tipo_label = TIPOS_ALTERACAO.get(tipo, tipo)
    linhas_id = [
        ["Número do Contrato", html.escape(str(dados_contrato.get("numero_contrato") or "-"))],
        ["Objeto", html.escape(str(dados_contrato.get("objeto") or "-"))],
        ["Data de Assinatura", html.escape(str(dados_contrato.get("data_assinatura") or "-"))],
        ["Valor Atual", _fmt_brl(float(dados_contrato.get("valor_atual") or 0))],
        ["Tipo de Alteração", html.escape(tipo_label)],
    ]
    t_id = Table(linhas_id, colWidths=[5*cm, 12*cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4*cm))

    # Badge do parecer
    parecer_val = str(parecer.get("parecer") or "INDEFERÍVEL").strip().upper()
    cor_badge = _COR_PARECER.get(parecer_val, colors.grey)
    story.append(Paragraph("Parecer Conclusivo", _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(parecer_val)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_badge),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    # Síntese
    sintese = str(parecer.get("sintese") or "-")
    story.append(Paragraph("Síntese", _ESTILO_H2))
    story.append(Paragraph(html.escape(sintese), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Checklist de requisitos
    requisitos = parecer.get("requisitos") or []
    if requisitos:
        story.append(Paragraph("Verificação de Requisitos", _ESTILO_H2))
        for req in requisitos:
            if not req:
                continue
            status = str(req.get("status") or "AUSENTE").strip().upper()
            icone = _ICONE_REQ.get(status, status)
            estilo = _ESTILO_REQ_MAP.get(status, _ESTILO_CORPO)
            descricao = html.escape(str(req.get("descricao") or ""))
            obs = html.escape(str(req.get("observacao") or ""))
            linha = f"<b>[{icone}]</b> {descricao}"
            if obs:
                linha += f" — {obs}"
            story.append(Paragraph(linha, estilo))
        story.append(Spacer(1, 0.3*cm))

    # Lacunas documentais
    lacunas = parecer.get("lacunas_documentais") or []
    if lacunas:
        story.append(Paragraph("Lacunas Documentais", _ESTILO_H2))
        for i, lac in enumerate(lacunas, 1):
            if lac:
                story.append(Paragraph(f"{i}. {html.escape(str(lac))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Fundamentos legais
    story.append(Paragraph("Fundamentos Legais", _ESTILO_H2))
    for fl in (parecer.get("fundamentos_legais") or []):
        if fl:
            story.append(Paragraph(f"- {html.escape(str(fl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes") or []
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if rec:
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Run tests — expect 4 passed**

```bash
python3 -m pytest tests/test_relatorio_contratos.py -v --tb=short 2>&1 | tail -15
```

Expected: `4 passed`

- [ ] **Step 5: Run full suite — expect 136 passed**

```bash
python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: `136 passed, 1 warning`

- [ ] **Step 6: Commit**

```bash
git add relatorio_contratos.py tests/test_relatorio_contratos.py
git commit -m "feat: Módulo 4 — relatorio_contratos.py + 4 smoke tests"
```

---

## Task 3: `app.py` — Tab 6

**Files:**
- Modify: `app.py`

No automated tests for UI code. Verify manually by running Streamlit locally (if possible) or inspecting that the imports resolve and the Python syntax is valid.

- [ ] **Step 1: Add imports at line 24 of `app.py`**

Find the block (current lines 23-24):
```python
import ia_pi_empresas
import relatorio_pi_empresas
```

Replace with:
```python
import ia_pi_empresas
import relatorio_pi_empresas
import ia_contratos
import relatorio_contratos
```

- [ ] **Step 2: Change the tab declaration (current lines 71-77)**

Find:
```python
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
])
```

Replace with:
```python
aba1, aba2, aba3, aba4, aba5, aba6 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
])
```

- [ ] **Step 3: Append `with aba6:` block at the end of `app.py`**

Append this entire block after the final line of `app.py` (currently line 744 `            )`):

```python

with aba6:
    st.subheader("Analisador de Alterações Contratuais")
    st.caption(
        "Art. 124 II 'd' · Art. 25 §8º · Art. 137 §2º — Lei 14.133/2021 · Art. 37 XXI CF/88"
    )

    _api_key_cont = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_cont:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_cont = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
    _modelo_cont = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _tipos_cont_chaves = list(ia_contratos.TIPOS_ALTERACAO.keys())
    _tipos_cont_labels = list(ia_contratos.TIPOS_ALTERACAO.values())
    _tipo_cont_idx = st.selectbox(
        "Tipo de alteração contratual",
        options=range(len(_tipos_cont_chaves)),
        format_func=lambda i: _tipos_cont_labels[i],
        key="cont_tipo_select",
    )
    _tipo_cont = _tipos_cont_chaves[_tipo_cont_idx]

    _col_num_cont, _col_data_cont = st.columns(2)
    _num_cont = _col_num_cont.text_input(
        "Número do contrato", key="cont_numero", placeholder="001/2024"
    )
    _data_cont = _col_data_cont.text_input(
        "Data de assinatura", key="cont_data", placeholder="DD/MM/AAAA"
    )
    _objeto_cont = st.text_input(
        "Objeto do contrato (resumido)", key="cont_objeto"
    )
    _valor_cont = st.number_input(
        "Valor atual do contrato (R$)",
        min_value=0.0, format="%.2f", step=10_000.0, key="cont_valor",
    )

    _arqs_cont = st.file_uploader(
        "Documentos do pedido (opcional — PDF ou Word): requerimento, memória de cálculo, CCT, planilhas etc.",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="cont_docs",
    )

    if st.button("Analisar Pedido", type="primary", key="btn_cont"):
        if not _api_key_cont:
            st.error(
                "ANTHROPIC_API_KEY não configurada — "
                "configure via variável de ambiente ou secrets.toml."
            )
        else:
            for _k in ("cont_parecer", "cont_pdf", "cont_dados"):
                st.session_state.pop(_k, None)
            _dados_cont = {
                "numero_contrato": _num_cont or "não informado",
                "objeto": _objeto_cont or "não informado",
                "data_assinatura": _data_cont or "não informada",
                "valor_atual": _valor_cont,
            }
            try:
                with st.spinner(
                    "Analisando pedido de alteração contratual com IA (pode levar 1-2 minutos)..."
                ):
                    _texto_cont, _ = (
                        etp_extrator.extrair_texto(_arqs_cont)
                        if _arqs_cont
                        else (None, [])
                    )
                    _parecer_cont = ia_contratos.analisar(
                        _tipo_cont,
                        _dados_cont,
                        _texto_cont,
                        _api_key_cont,
                        _modelo_cont,
                    )
                st.session_state["cont_parecer"] = _parecer_cont
                st.session_state["cont_dados"] = _dados_cont
                try:
                    st.session_state["cont_pdf"] = relatorio_contratos.gerar_pdf(
                        dados_contrato=_dados_cont,
                        tipo=_tipo_cont,
                        parecer=_parecer_cont,
                    )
                except Exception as _pdf_e:
                    st.session_state.pop("cont_pdf", None)
                    st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
            except (ValueError, RuntimeError) as _e:
                st.error(str(_e))

    if "cont_parecer" in st.session_state:
        _pr_cont = st.session_state["cont_parecer"]

        st.divider()
        _parecer_val_cont = str(_pr_cont.get("parecer") or "INDEFERÍVEL").strip().upper()
        _icone_parecer_cont = {
            "DEFERÍVEL":               "🟢",
            "DEFERÍVEL COM RESSALVAS": "🟡",
            "INDEFERÍVEL":             "🔴",
        }
        _cor_parecer_cont = {
            "DEFERÍVEL":               "#27AE60",
            "DEFERÍVEL COM RESSALVAS": "#F39C12",
            "INDEFERÍVEL":             "#C0392B",
        }
        st.markdown(
            f"<div style='background:{_cor_parecer_cont.get(_parecer_val_cont, '#888888')};"
            f"padding:16px;border-radius:8px;color:white;font-size:20px;"
            f"font-weight:bold;text-align:center'>"
            f"{_icone_parecer_cont.get(_parecer_val_cont, '⚪')} {_parecer_val_cont}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        _sintese_cont = str(_pr_cont.get("sintese") or "")
        if _sintese_cont:
            st.info(_sintese_cont)

        _requisitos_cont = _pr_cont.get("requisitos") or []
        if _requisitos_cont:
            st.markdown("**Verificação de Requisitos:**")
            _icone_req_cont = {"ATENDIDO": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌"}
            for _req_cont in _requisitos_cont:
                if not _req_cont:
                    continue
                _status_req = str(_req_cont.get("status") or "AUSENTE").strip().upper()
                _ic_req = _icone_req_cont.get(_status_req, "ℹ️")
                _obs_req = str(_req_cont.get("observacao") or "")
                _desc_req = str(_req_cont.get("descricao") or "")
                _linha_req = f"{_ic_req} **{_desc_req}**"
                if _obs_req:
                    _linha_req += f" — {_obs_req}"
                st.write(_linha_req)

        _lacunas_cont = _pr_cont.get("lacunas_documentais") or []
        if _lacunas_cont:
            with st.expander("📋 Lacunas Documentais"):
                for _lac in _lacunas_cont:
                    if _lac:
                        st.warning(_lac)

        _recs_cont = _pr_cont.get("recomendacoes") or []
        if _recs_cont:
            with st.expander("💡 Recomendações ao Gestor"):
                for _i_cont, _r_cont in enumerate(_recs_cont, 1):
                    if _r_cont:
                        st.info(f"{_i_cont}. {_r_cont}")

        with st.expander("⚖️ Fundamentos Legais"):
            for _fl_cont in (_pr_cont.get("fundamentos_legais") or []):
                if _fl_cont:
                    st.write(f"• {_fl_cont}")

        if "cont_pdf" in st.session_state:
            _num_pdf_cont = (
                (st.session_state.get("cont_dados") or {}).get("numero_contrato")
                or "contrato"
            )
            _nome_pdf_cont = f"Alteracao_{_num_pdf_cont.replace('/', '-')}.pdf"
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=st.session_state["cont_pdf"],
                file_name=_nome_pdf_cont,
                mime="application/pdf",
            )
```

- [ ] **Step 4: Verify Python syntax is valid**

```bash
python3 -c "import ast; ast.parse(open('app.py').read()); print('OK — syntax valid')"
```

Expected: `OK — syntax valid`

- [ ] **Step 5: Verify full test suite still passes**

```bash
python3 -m pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: `136 passed, 1 warning`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: Módulo 4 — Tab 6 Alterações Contratuais no app.py"
```

---

## Self-Review Checklist

Spec coverage verified:
- ✅ 3 alteration types (reajuste, repactuação, reequilíbrio) — `TIPOS_ALTERACAO`
- ✅ Requirements per type — `REQUISITOS_POR_TIPO`
- ✅ 2-step flow (no CNPJ lookup) — Tab 6 design
- ✅ IA JSON shape: `{parecer, tipo_alteracao, requisitos[{descricao,status,observacao}], lacunas_documentais, fundamentos_legais, recomendacoes, sintese}`
- ✅ Local values override AI: `{**qualitativo, "tipo_alteracao": tipo, "dados_contrato": dados_contrato}`
- ✅ Parecer colors: DEFERÍVEL=#27AE60, COM RESSALVAS=#F39C12, INDEFERÍVEL=#C0392B
- ✅ Requisito colors: ATENDIDO=verde, PARCIAL=laranja, AUSENTE=vermelho
- ✅ Error handling: HTTPError/URLError/non-dict all raise `RuntimeError`
- ✅ State keys: `cont_parecer`, `cont_dados`, `cont_pdf`
- ✅ PDF sections: header · contrato ID · badge · síntese · checklist · lacunas · fundamentos · recomendações · rodapé
- ✅ Style names prefixed `cont_*` to avoid ReportLab conflicts
- ✅ PDF magic bytes `%PDF` tested
- ✅ Type validation: invalid type raises `ValueError` before API call
