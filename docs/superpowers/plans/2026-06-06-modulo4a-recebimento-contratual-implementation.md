# M4a — Monitor de Recebimento Contratual — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar a sub-aba "📦 Recebimento Contratual" ao Monitor de Contratos (aba6) emitindo pareceres de recebimento provisório e definitivo, com checklist de condições e PDF, nos termos do Art. 140 da Lei 14.133/2021.

**Architecture:** Seguindo o padrão M4b (`ia_contratos.py` / `relatorio_contratos.py`): `ia_recebimento.py` expõe constantes + `analisar()` (uma chamada à API retorna dois blocos — provisório e definitivo); `relatorio_recebimento.py` gera o PDF com dois badges via ReportLab; `app.py` reorganiza o `with aba6:` com `st.tabs()` internos. Nenhum arquivo existente é deletado.

**Tech Stack:** Python 3.9, Streamlit, urllib (sem SDK), ReportLab, pytest + unittest.mock.

---

## Estrutura de Arquivos

| Ação | Arquivo | Responsabilidade |
|------|---------|-----------------|
| Criar | `ia_recebimento.py` | Constantes, `_chamar_anthropic()`, `analisar()` |
| Criar | `relatorio_recebimento.py` | `gerar_pdf()` com dois badges ReportLab |
| Criar | `tests/test_ia_recebimento.py` | ~15 testes unitários (constantes + `analisar()`) |
| Criar | `tests/test_relatorio_recebimento.py` | ~5 smoke tests do PDF |
| Modificar | `app.py` (linha 26 + linhas 760-949) | Importar novos módulos + reorganizar aba6 |

---

## Task 1: ia_recebimento.py — Constantes

**Files:**
- Create: `ia_recebimento.py`
- Create: `tests/test_ia_recebimento.py`

- [ ] **Step 1: Escrever testes das constantes (falharão)**

```python
# tests/test_ia_recebimento.py
from __future__ import annotations
import json
import types
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import ia_recebimento


class TestConstantes:
    def test_tipos_objeto_tem_3_entradas(self):
        assert len(ia_recebimento.TIPOS_OBJETO) == 3

    def test_tipos_objeto_chaves(self):
        assert set(ia_recebimento.TIPOS_OBJETO.keys()) == {"servico", "bem", "obra"}

    def test_parecer_options_tem_3_entradas(self):
        assert len(ia_recebimento.PARECER_OPTIONS) == 3

    def test_parecer_options_chaves(self):
        assert set(ia_recebimento.PARECER_OPTIONS.keys()) == {
            "APTO", "APTO COM RESSALVAS", "INAPTO"
        }

    def test_status_condicao_tem_3_entradas(self):
        assert len(ia_recebimento.STATUS_CONDICAO) == 3

    def test_status_condicao_chaves(self):
        assert set(ia_recebimento.STATUS_CONDICAO.keys()) == {
            "ATENDIDA", "PARCIAL", "AUSENTE"
        }

    def test_constantes_sao_mapping_proxy(self):
        assert isinstance(ia_recebimento.TIPOS_OBJETO, types.MappingProxyType)
        assert isinstance(ia_recebimento.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_recebimento.STATUS_CONDICAO, types.MappingProxyType)
```

- [ ] **Step 2: Verificar que os testes falham**

```
python3 -m pytest tests/test_ia_recebimento.py::TestConstantes -v
```

Esperado: `ModuleNotFoundError: No module named 'ia_recebimento'`

- [ ] **Step 3: Criar ia_recebimento.py com as constantes**

```python
# ia_recebimento.py
from __future__ import annotations
import json
import types
import urllib.error
import urllib.request

from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_OBJETO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": "Serviço",
    "bem":     "Fornecimento de Bem",
    "obra":    "Obra",
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "APTO":               "APTO",
    "APTO COM RESSALVAS": "APTO COM RESSALVAS",
    "INAPTO":             "INAPTO",
})

STATUS_CONDICAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
})
```

- [ ] **Step 4: Verificar que os testes passam**

```
python3 -m pytest tests/test_ia_recebimento.py::TestConstantes -v
```

Esperado: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add ia_recebimento.py tests/test_ia_recebimento.py
git commit -m "feat(m4a): ia_recebimento constantes (TIPOS_OBJETO, PARECER_OPTIONS, STATUS_CONDICAO)"
```

---

## Task 2: ia_recebimento.py — `_chamar_anthropic()` + `analisar()`

**Files:**
- Modify: `ia_recebimento.py` (adicionar _SISTEMA, _CONDICOES_POR_TIPO, _ESTRUTURA_PARECER, _chamar_anthropic, analisar)
- Modify: `tests/test_ia_recebimento.py` (adicionar helpers + TestAnalisar)

- [ ] **Step 1: Adicionar helpers de teste e TestAnalisar ao arquivo de teste**

Adicionar ao final de `tests/test_ia_recebimento.py` (após `TestConstantes`):

```python
def _dados_entrega_mock() -> dict:
    return {
        "numero_contrato": "010/2024",
        "objeto": "Serviços de manutenção predial",
        "data_entrega": "30/05/2025",
        "descricao_entrega": "Manutenção preventiva realizada em todos os andares",
        "nao_conformidades": "",
        "valor_contrato": 120000.0,
    }


def _parecer_api_mock() -> dict:
    return {
        "tipo_objeto": "servico",
        "recebimento_provisorio": {
            "parecer": "APTO",
            "condicoes": [
                {
                    "descricao": "Serviço prestado conforme TR",
                    "status": "ATENDIDA",
                    "observacao": "",
                }
            ],
            "pendencias": [],
            "sintese": "Condições de recebimento provisório atendidas.",
        },
        "recebimento_definitivo": {
            "parecer": "APTO COM RESSALVAS",
            "condicoes": [
                {
                    "descricao": "Qualidade confirmada após verificação",
                    "status": "PARCIAL",
                    "observacao": "Revisão técnica pendente",
                }
            ],
            "pendencias": ["Revisão técnica agendada para 30 dias"],
            "sintese": "Recebimento definitivo condicionado à revisão técnica.",
        },
        "recomendacoes_gerais": ["Agendar revisão técnica em 30 dias"],
        "base_legal": ["Art. 140, I, Lei 14.133/2021", "Art. 140, II, Lei 14.133/2021"],
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
        with pytest.raises(ValueError, match="Tipo de objeto inválido"):
            ia_recebimento.analisar("inexistente", {}, None, "key")

    def test_retorno_tem_recebimento_provisorio_e_definitivo(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert "recebimento_provisorio" in r
        assert "recebimento_definitivo" in r

    def test_cada_bloco_tem_campos_obrigatorios(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        for bloco_key in ("recebimento_provisorio", "recebimento_definitivo"):
            bloco = r[bloco_key]
            assert "parecer" in bloco
            assert "condicoes" in bloco
            assert "pendencias" in bloco
            assert "sintese" in bloco

    def test_tipo_objeto_local_prevalece(self):
        api_result = {**_parecer_api_mock(), "tipo_objeto": "bem"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(api_result)):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert r["tipo_objeto"] == "servico"

    def test_dados_entrega_preservados(self):
        dados = _dados_entrega_mock()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("servico", dados, None, "key")
        assert r["dados_entrega"] == dados

    def test_tipo_bem_funciona(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("bem", _dados_entrega_mock(), None, "key")
        assert isinstance(r, dict)

    def test_tipo_obra_funciona(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar("obra", _dados_entrega_mock(), None, "key")
        assert isinstance(r, dict)

    def test_com_texto_docs_nao_levanta(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_recebimento.analisar(
                "servico", _dados_entrega_mock(), "Texto do relatório fiscal", "key"
            )
        assert isinstance(r, dict)

    def test_http_error_levanta_runtime_error(self):
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key_invalida")

    def test_url_error_levanta_runtime_error(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
            with pytest.raises(RuntimeError):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_envelope_nao_json_levanta_runtime_error(self):
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=b"<html>Bad Gateway</html>"))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="não é JSON válido"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_resposta_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_content_null_nao_levanta(self):
        payload = json.dumps({"content": None}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError):
                ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")

    def test_item_nao_dict_em_content_ignorado(self):
        payload = json.dumps(
            {"content": ["string_invalida", {"text": json.dumps(_parecer_api_mock())}]}
        ).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            r = ia_recebimento.analisar("servico", _dados_entrega_mock(), None, "key")
        assert "recebimento_provisorio" in r
```

- [ ] **Step 2: Verificar que os novos testes falham**

```
python3 -m pytest tests/test_ia_recebimento.py::TestAnalisar -v
```

Esperado: `AttributeError: module 'ia_recebimento' has no attribute 'analisar'`

- [ ] **Step 3: Adicionar _SISTEMA, _CONDICOES_POR_TIPO, _ESTRUTURA_PARECER, _chamar_anthropic e analisar ao ia_recebimento.py**

Adicionar ao final de `ia_recebimento.py` (após as constantes):

```python
_SISTEMA = (
    "Você é um fiscal de contratos especialista em recebimento de objetos contratuais "
    "nos termos do Art. 140 da Lei 14.133/2021. Avalie as condições de recebimento "
    "provisório e definitivo do objeto contratual com base nas informações fornecidas. "
    "Verifique cada condição legal aplicável ao tipo de objeto e emita parecer motivado. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_CONDICOES_POR_TIPO: dict = {
    "servico": {
        "provisorio": [
            "Serviço prestado conforme especificações do Termo de Referência",
            "Medição elaborada pelo fiscal do contrato",
            "Prazo contratual de execução respeitado",
            "Documentação fiscal (NF/fatura) apresentada",
        ],
        "definitivo": [
            "Qualidade do serviço confirmada após período de verificação",
            "Pendências do recebimento provisório sanadas",
            "Autoridade competente habilitada para emitir o ateste final",
        ],
    },
    "bem": {
        "provisorio": [
            "Quantidade conferida conforme ordem de fornecimento",
            "Qualidade aparente sem avarias visíveis",
            "Nota fiscal e documentos de entrega presentes",
            "Entrega realizada no local e prazo contratados",
        ],
        "definitivo": [
            "Inspeção técnica concluída com laudo",
            "Conformidade com especificações do TR confirmada",
            "Garantia do fabricante registrada (se aplicável)",
        ],
    },
    "obra": {
        "provisorio": [
            "Obra concluída fisicamente conforme projeto",
            "ART/RRT de conclusão anotada pelo responsável técnico",
            "Medição final elaborada pela fiscalização",
            "Vistoria realizada pela comissão de recebimento",
        ],
        "definitivo": [
            "Período de observação decorrido sem defeitos aparentes",
            "Ausência de vícios ocultos identificados",
            "As-built entregue pelo contratado",
            "Responsabilidade técnica do contratado formalmente encerrada",
        ],
    },
}

_ESTRUTURA_PARECER = """{
  "tipo_objeto": "servico|bem|obra",
  "recebimento_provisorio": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {"descricao": "...", "status": "ATENDIDA|PARCIAL|AUSENTE", "observacao": "..."}
    ],
    "pendencias": ["..."],
    "sintese": "..."
  },
  "recebimento_definitivo": {
    "parecer": "APTO|APTO COM RESSALVAS|INAPTO",
    "condicoes": [
      {"descricao": "...", "status": "ATENDIDA|PARCIAL|AUSENTE", "observacao": "..."}
    ],
    "pendencias": ["..."],
    "sintese": "..."
  },
  "recomendacoes_gerais": ["..."],
  "base_legal": ["Art. 140, I, Lei 14.133/2021"]
}"""


def _chamar_anthropic(prompt: str, api_key: str, modelo: str) -> str:
    corpo = json.dumps({
        "model": modelo,
        "max_tokens": 4000,
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
        raw_bytes = resp.read()
    try:
        dados = json.loads(raw_bytes.decode("utf-8"))
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não é JSON válido: {exc}") from exc
    return "".join(b.get("text", "") for b in (dados.get("content") or []) if isinstance(b, dict))


def analisar(
    tipo_objeto: str,
    dados_entrega: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if tipo_objeto not in TIPOS_OBJETO:
        raise ValueError(
            f"Tipo de objeto inválido: '{tipo_objeto}'. Esperado: {list(TIPOS_OBJETO)}"
        )

    conds = _CONDICOES_POR_TIPO[tipo_objeto]
    partes = [
        f"Análise de Recebimento Contratual — {TIPOS_OBJETO[tipo_objeto]}\n",
        f"Número do Contrato: {dados_entrega.get('numero_contrato') or 'não informado'}",
        f"Objeto: {dados_entrega.get('objeto') or 'não informado'}",
        f"Data de Entrega/Conclusão: {dados_entrega.get('data_entrega') or 'não informada'}",
        f"Valor do Contrato: R$ {float(dados_entrega.get('valor_contrato') or 0):.2f}",
        f"Descrição do que foi entregue/executado:\n{dados_entrega.get('descricao_entrega') or 'não informado'}",
    ]
    nao_conf = dados_entrega.get("nao_conformidades")
    if nao_conf:
        partes.append(f"\nNão conformidades/pendências identificadas:\n{nao_conf}")

    partes.append("\nCondições de Recebimento Provisório a verificar (Art. 140, I):")
    for i, c in enumerate(conds["provisorio"], 1):
        partes.append(f"{i}. {c}")

    partes.append("\nCondições de Recebimento Definitivo a verificar (Art. 140, II):")
    for i, c in enumerate(conds["definitivo"], 1):
        partes.append(f"{i}. {c}")

    if texto_docs:
        partes.append(f"\nDocumentos fornecidos:\n{texto_docs[:30000]}")
    else:
        partes.append(
            "\nNenhum documento adicional fornecido. Analise com base nas informações "
            "acima e sinalize as condições não verificáveis pela falta de documentação."
        )

    partes.append(f"\nRetorne a análise no formato JSON:\n{_ESTRUTURA_PARECER}")

    try:
        bruto = _chamar_anthropic("\n".join(partes), api_key, modelo)
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

    try:
        qualitativo = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(qualitativo, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(qualitativo).__name__}"
        )

    return {**qualitativo, "tipo_objeto": tipo_objeto, "dados_entrega": dados_entrega}
```

- [ ] **Step 4: Verificar que todos os testes passam**

```
python3 -m pytest tests/test_ia_recebimento.py -v
```

Esperado: `21 passed` (7 constantes + 14 analisar)

- [ ] **Step 5: Commit**

```bash
git add ia_recebimento.py tests/test_ia_recebimento.py
git commit -m "feat(m4a): ia_recebimento analisar() — provisório + definitivo + guards"
```

---

## Task 3: relatorio_recebimento.py — `gerar_pdf()`

**Files:**
- Create: `relatorio_recebimento.py`
- Create: `tests/test_relatorio_recebimento.py`

- [ ] **Step 1: Escrever smoke tests (falharão)**

```python
# tests/test_relatorio_recebimento.py
from __future__ import annotations
import relatorio_recebimento


def _dados_entrega_mock() -> dict:
    return {
        "numero_contrato": "010/2024",
        "objeto": "Serviços de manutenção predial",
        "data_entrega": "30/05/2025",
        "descricao_entrega": "Manutenção preventiva realizada em todos os andares",
        "nao_conformidades": "",
        "valor_contrato": 120000.0,
    }


def _parecer_completo_mock() -> dict:
    return {
        "tipo_objeto": "servico",
        "recebimento_provisorio": {
            "parecer": "APTO",
            "condicoes": [
                {"descricao": "Serviço prestado conforme TR", "status": "ATENDIDA", "observacao": ""},
                {"descricao": "Medição elaborada", "status": "ATENDIDA", "observacao": ""},
            ],
            "pendencias": [],
            "sintese": "Condições de recebimento provisório plenamente atendidas.",
        },
        "recebimento_definitivo": {
            "parecer": "APTO COM RESSALVAS",
            "condicoes": [
                {"descricao": "Qualidade confirmada", "status": "PARCIAL", "observacao": "Revisão pendente"},
            ],
            "pendencias": ["Revisão técnica agendada"],
            "sintese": "Recebimento definitivo condicionado à revisão técnica.",
        },
        "recomendacoes_gerais": ["Agendar revisão técnica em 30 dias"],
        "base_legal": ["Art. 140, I, Lei 14.133/2021", "Art. 140, II, Lei 14.133/2021"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios_com_magic_bytes_pdf(self):
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=_parecer_completo_mock(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
        assert pdf[:4] == b"%PDF"

    def test_todos_os_pareceres_possiveis_nao_quebram(self):
        for parecer_val in ["APTO", "APTO COM RESSALVAS", "INAPTO"]:
            parecer = _parecer_completo_mock()
            parecer["recebimento_provisorio"]["parecer"] = parecer_val
            parecer["recebimento_definitivo"]["parecer"] = parecer_val
            pdf = relatorio_recebimento.gerar_pdf(
                dados_entrega=_dados_entrega_mock(),
                tipo_objeto="bem",
                parecer=parecer,
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_todos_os_tipos_de_objeto_nao_quebram(self):
        for tipo in ["servico", "bem", "obra"]:
            pdf = relatorio_recebimento.gerar_pdf(
                dados_entrega=_dados_entrega_mock(),
                tipo_objeto=tipo,
                parecer=_parecer_completo_mock(),
            )
            assert isinstance(pdf, bytes)
            assert len(pdf) > 1000

    def test_listas_nulas_nao_quebram(self):
        parecer = _parecer_completo_mock()
        parecer["recebimento_provisorio"]["pendencias"] = None
        parecer["recebimento_definitivo"]["condicoes"] = None
        parecer["recomendacoes_gerais"] = None
        parecer["base_legal"] = None
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_condicao_nao_dict_ignorada(self):
        parecer = _parecer_completo_mock()
        parecer["recebimento_provisorio"]["condicoes"] = [
            None,
            {},
            {"descricao": "Condição válida", "status": "ATENDIDA", "observacao": ""},
        ]
        pdf = relatorio_recebimento.gerar_pdf(
            dados_entrega=_dados_entrega_mock(),
            tipo_objeto="servico",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
```

- [ ] **Step 2: Verificar que os testes falham**

```
python3 -m pytest tests/test_relatorio_recebimento.py -v
```

Esperado: `ModuleNotFoundError: No module named 'relatorio_recebimento'`

- [ ] **Step 3: Criar relatorio_recebimento.py**

```python
# relatorio_recebimento.py
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
from ia_recebimento import TIPOS_OBJETO

_COR_PARECER = {
    "APTO":               colors.HexColor(_COR_STATUS["ok"]),
    "APTO COM RESSALVAS": colors.HexColor("#F39C12"),
    "INAPTO":             colors.HexColor(_COR_STATUS["critico"]),
}

_estilos_base    = getSampleStyleSheet()
_ESTILO_TITULO   = ParagraphStyle("recv_titulo",   parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1       = ParagraphStyle("recv_h1",       parent=_estilos_base["Heading1"])
_ESTILO_H2       = ParagraphStyle("recv_h2",       parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO    = ParagraphStyle("recv_corpo",    parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO  = ParagraphStyle("recv_peq",      parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE    = ParagraphStyle("recv_badge",    parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_COND_OK  = ParagraphStyle("recv_cond_ok",  parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["ok"]))
_ESTILO_COND_PAR = ParagraphStyle("recv_cond_par", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor("#F39C12"))
_ESTILO_COND_AUS = ParagraphStyle("recv_cond_aus", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["critico"]))

_ICONE_COND = {"ATENDIDA": "✓ ATENDIDA", "PARCIAL": "⚠ PARCIAL", "AUSENTE": "✗ AUSENTE"}
_ESTILO_COND_MAP = {
    "ATENDIDA": _ESTILO_COND_OK,
    "PARCIAL":  _ESTILO_COND_PAR,
    "AUSENTE":  _ESTILO_COND_AUS,
}


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _render_bloco(story: list, titulo: str, bloco: dict) -> None:
    parecer_val = str(bloco.get("parecer") or "INAPTO").strip().upper()
    cor_badge = _COR_PARECER.get(parecer_val, colors.grey)

    story.append(Paragraph(titulo, _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(parecer_val)}</b>", _ESTILO_BADGE)]],
        colWidths=[17 * cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.3 * cm))

    sintese = str(bloco.get("sintese") or "-")
    story.append(Paragraph(html.escape(sintese), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3 * cm))

    condicoes = _as_list(bloco.get("condicoes"))
    if condicoes:
        story.append(Paragraph("Condições Verificadas:", _ESTILO_H2))
        for cond in condicoes:
            if not isinstance(cond, dict) or not cond:
                continue
            status = str(cond.get("status") or "AUSENTE").strip().upper()
            icone = _ICONE_COND.get(status, html.escape(status))
            estilo = _ESTILO_COND_MAP.get(status, _ESTILO_CORPO)
            descricao = html.escape(str(cond.get("descricao") or ""))
            obs = html.escape(str(cond.get("observacao") or ""))
            linha = f"<b>[{icone}]</b> {descricao}"
            if obs:
                linha += f" — {obs}"
            story.append(Paragraph(linha, estilo))
        story.append(Spacer(1, 0.2 * cm))

    pendencias = _as_list(bloco.get("pendencias"))
    if pendencias:
        story.append(Paragraph("Pendências:", _ESTILO_H2))
        for i, p in enumerate(pendencias, 1):
            if p:
                story.append(Paragraph(f"{i}. {html.escape(str(p))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.4 * cm))


def gerar_pdf(dados_entrega: dict, tipo_objeto: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    story = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Monitor de Recebimento Contratual", _ESTILO_H1))
    story.append(Paragraph("Art. 140, I e II — Lei 14.133/2021", _ESTILO_PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _ESTILO_PEQUENO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("Identificação do Contrato", _ESTILO_H2))
    tipo_label = TIPOS_OBJETO.get(tipo_objeto, tipo_objeto)
    linhas_id = [
        ["Número do Contrato",       html.escape(str(dados_entrega.get("numero_contrato") or "-"))],
        ["Objeto",                   html.escape(str(dados_entrega.get("objeto") or "-"))],
        ["Data de Entrega/Conclusão",html.escape(str(dados_entrega.get("data_entrega") or "-"))],
        ["Valor do Contrato",        _fmt_brl(float(dados_entrega.get("valor_contrato") or 0))],
        ["Tipo de Objeto",           html.escape(tipo_label)],
    ]
    t_id = Table(linhas_id, colWidths=[5 * cm, 12 * cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4 * cm))

    _render_bloco(
        story,
        "Recebimento Provisório (Art. 140, I)",
        parecer.get("recebimento_provisorio") or {},
    )
    _render_bloco(
        story,
        "Recebimento Definitivo (Art. 140, II)",
        parecer.get("recebimento_definitivo") or {},
    )

    recs = _as_list(parecer.get("recomendacoes_gerais"))
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if rec:
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.4 * cm))

    base_legal = _as_list(parecer.get("base_legal"))
    if base_legal:
        story.append(Paragraph("Base Legal", _ESTILO_H2))
        for bl in base_legal:
            if bl:
                story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Verificar que os smoke tests passam**

```
python3 -m pytest tests/test_relatorio_recebimento.py -v
```

Esperado: `5 passed`

- [ ] **Step 5: Verificar suite completa até agora**

```
python3 -m pytest --tb=short -q
```

Esperado: `≥ 147 passed` (141 baseline + 21 ia_recebimento + 5 relatorio_recebimento)

- [ ] **Step 6: Commit**

```bash
git add relatorio_recebimento.py tests/test_relatorio_recebimento.py
git commit -m "feat(m4a): relatorio_recebimento gerar_pdf() com dois badges ReportLab"
```

---

## Task 4: app.py — Aba6 "Monitor de Contratos" + sub-aba M4a

**Files:**
- Modify: `app.py` linha 26 (adicionar 2 imports)
- Modify: `app.py` linhas 760-949 (substituir bloco `with aba6:` completo)

- [ ] **Step 1: Adicionar imports ao topo de app.py**

Localizar a linha:
```python
import relatorio_contratos
```

Substituir por:
```python
import relatorio_contratos
import ia_recebimento
import relatorio_recebimento
```

- [ ] **Step 2: Substituir o bloco `with aba6:` completo**

Localizar o trecho exato que começa em `with aba6:` (linha 760) e termina na última linha `)` (linha 949) e substituir por:

```python
with aba6:
    st.subheader("Monitor de Contratos")
    _sub_aba_alt, _sub_aba_recv = st.tabs([
        "⚖️ Alterações Contratuais",
        "📦 Recebimento Contratual",
    ])

    with _sub_aba_alt:
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
                        _texto_cont, _avisos_cont = (
                            etp_extrator.extrair_texto(_arqs_cont)
                            if _arqs_cont
                            else (None, [])
                        )
                        for _av_cont in _avisos_cont:
                            st.warning(_av_cont)
                        if _texto_cont and len(_texto_cont) > 30_000:
                            st.warning(
                                "Documentos muito extensos: apenas os primeiros 30 000 "
                                "caracteres serão analisados."
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
                except Exception as _e:
                    st.error(str(_e))

        if "cont_parecer" in st.session_state:
            _pr_cont = st.session_state["cont_parecer"]

            st.divider()
            _parecer_val_cont = str(_pr_cont.get("parecer") or "INDEFERÍVEL").strip().upper()
            _parecer_val_cont = {
                "DEFERIVEL":               "DEFERÍVEL",
                "DEFERIVEL COM RESSALVAS": "DEFERÍVEL COM RESSALVAS",
                "INDEFERIVEL":             "INDEFERÍVEL",
            }.get(_parecer_val_cont, _parecer_val_cont)
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
                f"{_icone_parecer_cont.get(_parecer_val_cont, '⚪')} {html.escape(_parecer_val_cont)}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            _sintese_cont = str(_pr_cont.get("sintese") or "")
            if _sintese_cont:
                st.info(_safe_md(_sintese_cont))

            _requisitos_cont = _pr_cont.get("requisitos")
            _requisitos_cont = _requisitos_cont if isinstance(_requisitos_cont, list) else []
            if _requisitos_cont:
                st.markdown("**Verificação de Requisitos:**")
                _icone_req_cont = {"ATENDIDO": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌"}
                for _req_cont in _requisitos_cont:
                    if not isinstance(_req_cont, dict) or not _req_cont:
                        continue
                    _status_req = str(_req_cont.get("status") or "AUSENTE").strip().upper()
                    _ic_req = _icone_req_cont.get(_status_req, "ℹ️")
                    _obs_req = " ".join(str(_req_cont.get("observacao") or "").split())
                    _desc_req = " ".join(str(_req_cont.get("descricao") or "").split())
                    _linha_req = f"{_ic_req} **{_safe_md(_desc_req)}**"
                    if _obs_req:
                        _linha_req += f" — {_safe_md(_obs_req)}"
                    st.markdown(_linha_req)

            _lacunas_cont = _pr_cont.get("lacunas_documentais")
            _lacunas_cont = _lacunas_cont if isinstance(_lacunas_cont, list) else []
            if _lacunas_cont:
                with st.expander("📋 Lacunas Documentais"):
                    for _lac in _lacunas_cont:
                        if _lac:
                            st.warning(_safe_md(_lac))

            _recs_cont = _pr_cont.get("recomendacoes")
            _recs_cont = _recs_cont if isinstance(_recs_cont, list) else []
            if _recs_cont:
                with st.expander("💡 Recomendações ao Gestor"):
                    for _i_cont, _r_cont in enumerate(_recs_cont, 1):
                        if _r_cont:
                            st.info(f"{_i_cont}. {_safe_md(_r_cont)}")

            _fls_cont = _pr_cont.get("fundamentos_legais")
            _fls_cont = _fls_cont if isinstance(_fls_cont, list) else []
            if _fls_cont:
                with st.expander("⚖️ Fundamentos Legais"):
                    for _fl_cont in _fls_cont:
                        if _fl_cont:
                            st.markdown(f"• {_safe_md(_fl_cont)}")

            if "cont_pdf" in st.session_state:
                _num_pdf_cont = (
                    (st.session_state.get("cont_dados") or {}).get("numero_contrato")
                    or "contrato"
                )
                _nome_pdf_cont = f"Alteracao_{_num_pdf_cont.replace('/', '-').replace(' ', '_')}.pdf"
                st.download_button(
                    label="⬇️ Baixar Relatório PDF",
                    data=st.session_state["cont_pdf"],
                    file_name=_nome_pdf_cont,
                    mime="application/pdf",
                )

    with _sub_aba_recv:
        st.subheader("Recebimento Contratual")
        st.caption("Art. 140, I e II — Lei 14.133/2021")

        _api_key_recv = os.environ.get("ANTHROPIC_API_KEY")
        if not _api_key_recv:
            try:
                _val = st.secrets.get("ANTHROPIC_API_KEY")
                if _val:
                    _api_key_recv = str(_val)
            except _SecretsNotFound:
                pass
            except Exception as _e:
                st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
        _modelo_recv = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

        _tipos_recv_chaves = list(ia_recebimento.TIPOS_OBJETO.keys())
        _tipos_recv_labels = list(ia_recebimento.TIPOS_OBJETO.values())
        _tipo_recv_idx = st.selectbox(
            "Tipo de objeto contratual",
            options=range(len(_tipos_recv_chaves)),
            format_func=lambda i: _tipos_recv_labels[i],
            key="recv_tipo_select",
        )
        _tipo_recv = _tipos_recv_chaves[_tipo_recv_idx]

        _col_num_recv, _col_data_recv = st.columns(2)
        _num_recv = _col_num_recv.text_input(
            "Número do contrato", key="recv_numero", placeholder="001/2024"
        )
        _data_recv = _col_data_recv.text_input(
            "Data de entrega/conclusão", key="recv_data", placeholder="DD/MM/AAAA"
        )
        _objeto_recv = st.text_input("Objeto do contrato (resumido)", key="recv_objeto")
        _desc_recv = st.text_area(
            "Descrição do que foi entregue/executado", key="recv_descricao"
        )
        _nao_conf_recv = st.text_area(
            "Não conformidades ou pendências identificadas (opcional)", key="recv_nao_conf"
        )
        _valor_recv = st.number_input(
            "Valor do contrato (R$)",
            min_value=0.0, format="%.2f", step=10_000.0, key="recv_valor",
        )
        _arqs_recv = st.file_uploader(
            "Documentos de suporte (opcional — PDF ou DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="recv_docs",
        )

        if st.button("Analisar Recebimento", type="primary", key="btn_recv"):
            if not _api_key_recv:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            elif not _desc_recv.strip():
                st.error("Preencha a descrição do que foi entregue/executado.")
            else:
                for _k in ("recv_parecer", "recv_pdf", "recv_dados"):
                    st.session_state.pop(_k, None)
                _dados_recv = {
                    "numero_contrato": _num_recv or "não informado",
                    "objeto": _objeto_recv or "não informado",
                    "data_entrega": _data_recv or "não informada",
                    "descricao_entrega": _desc_recv,
                    "nao_conformidades": _nao_conf_recv or "",
                    "valor_contrato": _valor_recv,
                }
                try:
                    with st.spinner(
                        "Analisando recebimento contratual com IA (pode levar 1-2 minutos)..."
                    ):
                        _texto_recv, _avisos_recv = (
                            etp_extrator.extrair_texto(_arqs_recv)
                            if _arqs_recv
                            else (None, [])
                        )
                        for _av_recv in _avisos_recv:
                            st.warning(_safe_md(_av_recv))
                        if _texto_recv and len(_texto_recv) > 30_000:
                            st.warning(
                                "Documentos muito extensos: apenas os primeiros 30 000 "
                                "caracteres serão analisados."
                            )
                        _parecer_recv = ia_recebimento.analisar(
                            _tipo_recv,
                            _dados_recv,
                            _texto_recv,
                            _api_key_recv,
                            _modelo_recv,
                        )
                    st.session_state["recv_parecer"] = _parecer_recv
                    st.session_state["recv_dados"] = _dados_recv
                    try:
                        st.session_state["recv_pdf"] = relatorio_recebimento.gerar_pdf(
                            dados_entrega=_dados_recv,
                            tipo_objeto=_tipo_recv,
                            parecer=_parecer_recv,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("recv_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except Exception as _e:
                    st.error(str(_e))

        if "recv_parecer" in st.session_state:
            _pr_recv = st.session_state["recv_parecer"]
            st.divider()

            _icone_parecer_recv = {"APTO": "🟢", "APTO COM RESSALVAS": "🟡", "INAPTO": "🔴"}
            _cor_parecer_recv = {
                "APTO": "#27AE60", "APTO COM RESSALVAS": "#F39C12", "INAPTO": "#C0392B",
            }

            def _render_bloco_recv(bloco_key: str, titulo: str) -> None:
                _bloco = (_pr_recv.get(bloco_key) or {})
                _pval = str(_bloco.get("parecer") or "INAPTO").strip().upper()
                st.markdown(
                    f"<div style='background:{_cor_parecer_recv.get(_pval, '#888888')};"
                    f"padding:12px;border-radius:8px;color:white;font-size:16px;"
                    f"font-weight:bold;text-align:center'>"
                    f"{_icone_parecer_recv.get(_pval, '⚪')} {html.escape(_pval)}</div>",
                    unsafe_allow_html=True,
                )
                st.caption(titulo)
                _sint = str(_bloco.get("sintese") or "")
                if _sint:
                    st.info(_safe_md(_sint))
                _conds = _bloco.get("condicoes")
                _conds = _conds if isinstance(_conds, list) else []
                if _conds:
                    st.markdown("**Condições Verificadas:**")
                    _icone_cond = {"ATENDIDA": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌"}
                    for _cond in _conds:
                        if not isinstance(_cond, dict) or not _cond:
                            continue
                        _st_c = str(_cond.get("status") or "AUSENTE").strip().upper()
                        _ic_c = _icone_cond.get(_st_c, "ℹ️")
                        _obs_c = " ".join(str(_cond.get("observacao") or "").split())
                        _desc_c = " ".join(str(_cond.get("descricao") or "").split())
                        _linha_c = f"{_ic_c} **{_safe_md(_desc_c)}**"
                        if _obs_c:
                            _linha_c += f" — {_safe_md(_obs_c)}"
                        st.markdown(_linha_c)
                _pends = _bloco.get("pendencias")
                _pends = _pends if isinstance(_pends, list) else []
                for _p in _pends:
                    if _p:
                        st.warning(_safe_md(_p))

            _col_prov, _col_def = st.columns(2)
            with _col_prov:
                _render_bloco_recv(
                    "recebimento_provisorio", "Recebimento Provisório — Art. 140, I"
                )
            with _col_def:
                _render_bloco_recv(
                    "recebimento_definitivo", "Recebimento Definitivo — Art. 140, II"
                )

            _recs_recv = _pr_recv.get("recomendacoes_gerais")
            _recs_recv = _recs_recv if isinstance(_recs_recv, list) else []
            if _recs_recv:
                with st.expander("💡 Recomendações ao Gestor"):
                    for _i_recv, _r_recv in enumerate(_recs_recv, 1):
                        if _r_recv:
                            st.info(f"{_i_recv}. {_safe_md(_r_recv)}")

            _bl_recv = _pr_recv.get("base_legal")
            _bl_recv = _bl_recv if isinstance(_bl_recv, list) else []
            if _bl_recv:
                with st.expander("⚖️ Base Legal"):
                    for _b_recv in _bl_recv:
                        if _b_recv:
                            st.markdown(f"• {_safe_md(_b_recv)}")

            if "recv_pdf" in st.session_state:
                _num_pdf_recv = (
                    (st.session_state.get("recv_dados") or {}).get("numero_contrato")
                    or "contrato"
                )
                _nome_pdf_recv = (
                    f"Recebimento_{_num_pdf_recv.replace('/', '-').replace(' ', '_')}.pdf"
                )
                st.download_button(
                    label="⬇️ Baixar Relatório PDF",
                    data=st.session_state["recv_pdf"],
                    file_name=_nome_pdf_recv,
                    mime="application/pdf",
                )
```

**Atenção ao aplicar o Step 2:** Use o Edit tool com o `old_string` exato começando em `with aba6:` (linha 760) e terminando na última linha da aba6 (o `)` do `st.download_button` do M4b, linha 949). O `new_string` é o bloco completo acima.

- [ ] **Step 3: Verificar suite completa**

```
python3 -m pytest --tb=short -q
```

Esperado: `≥ 147 passed`, `0 failed`

- [ ] **Step 4: Verificar import de app.py não lança erros**

```
python3 -c "import ast; ast.parse(open('app.py').read()); print('OK — sintaxe válida')"
```

Esperado: `OK — sintaxe válida`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(m4a): aba6 → Monitor de Contratos com sub-abas + UI Recebimento Contratual"
```

---

## Critérios de Aceitação

- [ ] `python3 -m pytest --tb=short -q` → `≥ 147 passed, 0 failed`
- [ ] `python3 -c "import ast; ast.parse(open('app.py').read()); print('OK')"` → `OK`
- [ ] `ia_recebimento.TIPOS_OBJETO`, `PARECER_OPTIONS`, `STATUS_CONDICAO` existem como `MappingProxyType`
- [ ] `ia_recebimento.analisar()` aceita `tipo_objeto in {"servico","bem","obra"}`, retorna dict com `recebimento_provisorio` + `recebimento_definitivo`
- [ ] `relatorio_recebimento.gerar_pdf()` retorna bytes com magic bytes `%PDF`
- [ ] `app.py` importa `ia_recebimento` e `relatorio_recebimento`
- [ ] `with aba6:` contém `st.subheader("Monitor de Contratos")` + `st.tabs()`
- [ ] Guard `(dados.get("content") or []) + isinstance(b, dict)` presente em `ia_recebimento._chamar_anthropic()`
- [ ] Todos os campos LLM na sub-aba recv passam por `_safe_md()` ou `html.escape()`
