# Módulo 5 — Auditoria de Termo de Referência (TR) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar auditoria de Termos de Referência (IN SEGES 81/2022) com 3 tipos de objeto (serviço, bem, TIC), geração de relatório PDF e nova aba no app Streamlit.

**Architecture:** Módulo type-aware `ia_tr.py` com `_SISTEMA_POR_TIPO` despacha para system prompt correto conforme tipo; `relatorio_tr.py` gera PDF via ReportLab com labels por tipo; `app.py` ganha 7ª aba com upload PDF/DOCX reutilizando `etp_extrator.extrair_texto` já existente. Padrão split try/except (HTTP separado de JSON parse) idêntico a todos os outros módulos IA.

**Tech Stack:** Python 3.9+, Streamlit, ReportLab, pytest + unittest.mock, `ia_utils.chamar_anthropic`, `ia_utils.extrair_json`, `etp_extrator.extrair_texto`.

---

## Estrutura de arquivos

| Arquivo | Ação | Responsabilidade |
|---|---|---|
| `ia_tr.py` | Criar | Análise IA type-aware — 3 tipos, system prompts, normalização |
| `relatorio_tr.py` | Criar | Geração de PDF do parecer de TR via ReportLab |
| `tests/test_ia_tr.py` | Criar | 8 testes unitários do analisador |
| `tests/test_relatorio_tr.py` | Criar | 4 testes de geração de PDF |
| `app.py` | Modificar | Nova aba7 "📝 Auditoria de TR" |
| `etp_extrator.py` | Reutilizar | Extração de texto PDF/DOCX — sem modificação |
| `ia_utils.py` | Reutilizar | `chamar_anthropic`, `extrair_json` — sem modificação |

---

## Contexto do codebase (leia antes de implementar)

- **Patch target para testes:** todos os testes que mockam chamadas HTTP usam `@patch("ia_utils.urllib.request.urlopen")` — não use o namespace do módulo.
- **Split try/except:** o projeto usa dois blocos try separados — o primeiro captura erros HTTP (`urllib.error.HTTPError`, `URLError`, `OSError`), o segundo captura `ValueError` do `_extrair_json`. Ver `ia_etp.py` como referência.
- **Normalização de `adequacao_geral`:** valores fora de `{"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"}` são normalizados para `"INADEQUADO"`. Ver `ia_etp.py` linha 59.
- **Módulo de referência para type-aware:** `ia_recebimento.py` — tem `_SISTEMA_POR_TIPO` e `TIPOS_OBJETO` com `types.MappingProxyType`.
- **Módulo de referência para PDF:** `relatorio_etp.py` — layout idêntico ao que precisamos.
- **Módulo de referência para testes de IA:** `tests/test_ia_etp.py`.
- **Módulo de referência para testes de PDF:** `tests/test_relatorio_etp.py`.
- **`etp_extrator.extrair_texto(arquivos: list) -> tuple[str, list[str]]`** — retorna `(texto, avisos)`.

---

## Task 1: ia_tr.py — Testes unitários

**Files:**
- Create: `tests/test_ia_tr.py`

- [ ] **Step 1: Criar o arquivo de testes**

```python
# tests/test_ia_tr.py
from __future__ import annotations
import io
import json
import pytest
import urllib.error
from unittest.mock import patch, MagicMock
import ia_tr


def _parecer_servico() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_objeto":          {"status": "ok",     "descricao": "Objeto bem descrito."},
            "fundamentacao":             {"status": "ok",     "descricao": "Necessidade justificada."},
            "requisitos_tecnicos":       {"status": "alerta", "descricao": "Incompleto."},
            "modelo_execucao":           {"status": "ok",     "descricao": "Definido."},
            "modelo_gestao":             {"status": "ok",     "descricao": "Fiscalização prevista."},
            "criterio_medicao":          {"status": "ok",     "descricao": "Unidade definida."},
            "criterio_julgamento":       {"status": "ok",     "descricao": "Menor preço."},
            "estimativa_preco":          {"status": "alerta", "descricao": "Fontes insuficientes."},
            "qualificacao_habilitacao":  {"status": "ok",     "descricao": "Proporcional."},
        },
        "pontos_criticos": ["Requisitos técnicos incompletos."],
        "recomendacoes": ["Detalhar especificações técnicas."],
        "base_legal": ["IN SEGES/MGI 81/2022", "Lei 14.133/2021, Art. 6º, XXIII"],
    }


def _parecer_bem() -> dict:
    return {
        "adequacao_geral": "ADEQUADO",
        "dimensoes": {
            "especificacao_tecnica":    {"status": "ok", "descricao": "Especificação completa."},
            "justificativa_quantidade": {"status": "ok", "descricao": "Histórico presente."},
            "qualificacao_tecnica":     {"status": "ok", "descricao": "INMETRO citado."},
            "garantia_assistencia":     {"status": "ok", "descricao": "Prazo definido."},
            "condicoes_entrega":        {"status": "ok", "descricao": "Local definido."},
            "criterio_julgamento":      {"status": "ok", "descricao": "Menor preço."},
            "estimativa_preco":         {"status": "ok", "descricao": "Pesquisa válida."},
            "sustentabilidade":         {"status": "ok", "descricao": "Critérios presentes."},
        },
        "pontos_criticos": [],
        "recomendacoes": [],
        "base_legal": ["IN SEGES/MGI 81/2022"],
    }


def _parecer_tic() -> dict:
    return {
        "adequacao_geral": "INADEQUADO",
        "dimensoes": {
            "alinhamento_pdtic":    {"status": "critico", "descricao": "PDTIC ausente."},
            "analise_viabilidade":  {"status": "critico", "descricao": "AVC ausente."},
            "solucao_ti":           {"status": "alerta",  "descricao": "Incompleta."},
            "criterios_aceite_ans": {"status": "ok",      "descricao": "ANS definidos."},
            "equipe_tecnica":       {"status": "ok",      "descricao": "INTECTI prevista."},
            "seguranca_lgpd":       {"status": "alerta",  "descricao": "LGPD incompleta."},
            "modelo_execucao":      {"status": "ok",      "descricao": "Metodologia ágil."},
            "transicao_contratual": {"status": "critico", "descricao": "Plano ausente."},
            "estimativa_preco":     {"status": "ok",      "descricao": "Benchmark presente."},
        },
        "pontos_criticos": ["PDTIC ausente.", "AVC não elaborada."],
        "recomendacoes": ["Elaborar PDTIC.", "Realizar AVC completa."],
        "base_legal": ["IN SGD/ME 21/2024", "IN SEGES/MGI 81/2022"],
    }


def _mock_urlopen(parecer: dict):
    resposta = json.dumps({"content": [{"text": json.dumps(parecer)}]}).encode("utf-8")
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestAnalisarTr:
    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_servico(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_servico())
        resultado = ia_tr.analisar_tr("Texto do TR de serviço.", "servico", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_bem(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_bem())
        resultado = ia_tr.analisar_tr("Texto do TR de bem.", "bem", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado

    @patch("ia_utils.urllib.request.urlopen")
    def test_retorna_estrutura_correta_tic(self, mock_urlopen):
        mock_urlopen.return_value = _mock_urlopen(_parecer_tic())
        resultado = ia_tr.analisar_tr("Texto do TR de TIC.", "tic", "sk-test")
        assert "adequacao_geral" in resultado
        assert "dimensoes" in resultado
        assert "pontos_criticos" in resultado
        assert "recomendacoes" in resultado
        assert "base_legal" in resultado

    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Tipo de objeto inválido"):
            ia_tr.analisar_tr("Texto", "invalido", "sk-test")

    @patch("ia_utils.urllib.request.urlopen")
    def test_adequacao_invalida_normalizada_para_inadequado(self, mock_urlopen):
        parecer = {**_parecer_servico(), "adequacao_geral": "PARCIALMENTE ADEQUADO"}
        mock_urlopen.return_value = _mock_urlopen(parecer)
        resultado = ia_tr.analisar_tr("Texto", "servico", "sk-test")
        assert resultado["adequacao_geral"] == "INADEQUADO"

    @patch("ia_utils.urllib.request.urlopen")
    def test_httperror_inclui_body_na_mensagem(self, mock_urlopen):
        fp = io.BytesIO(b'{"error": "invalid_api_key"}')
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/v1/messages", 401, "Unauthorized", {}, fp
        )
        with pytest.raises(RuntimeError) as exc_info:
            ia_tr.analisar_tr("Texto", "servico", "sk-test")
        assert "401" in str(exc_info.value)
        assert "invalid_api_key" in str(exc_info.value)

    @patch("ia_utils.urllib.request.urlopen")
    def test_resposta_sem_json_levanta_runtime_error(self, mock_urlopen):
        resposta = json.dumps({"content": [{"text": "Não consigo analisar este documento."}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm
        with pytest.raises(RuntimeError, match="JSON"):
            ia_tr.analisar_tr("Texto", "servico", "sk-test")

    @patch("ia_utils.urllib.request.urlopen")
    def test_content_null_nao_quebra(self, mock_urlopen):
        resposta = json.dumps({"content": None}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=resposta)))
        mock_cm.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_cm
        with pytest.raises(RuntimeError):
            ia_tr.analisar_tr("Texto", "servico", "sk-test")
```

- [ ] **Step 2: Verificar que os testes falham (ia_tr não existe ainda)**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python3 -m pytest tests/test_ia_tr.py -v 2>&1 | head -20
```

Esperado: `ModuleNotFoundError: No module named 'ia_tr'`

---

## Task 2: ia_tr.py — Implementação

**Files:**
- Create: `ia_tr.py`

- [ ] **Step 1: Criar ia_tr.py**

```python
# ia_tr.py
from __future__ import annotations
import types
import urllib.error

from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_ADEQ_VALIDOS = frozenset({"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"})

TIPOS_OBJETO_TR: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": "Serviço",
    "bem":     "Bem / Material",
    "tic":     "Serviço de TIC",
})

_SISTEMA_POR_TIPO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "servico": (
        "Você é um especialista em contratações públicas federais brasileiras. "
        "Analise o Termo de Referência de SERVIÇOS conforme a IN SEGES/MGI 81/2022, "
        "Lei 14.133/2021 art. 6º XXIII e art. 40. Avalie as 9 dimensões obrigatórias: "
        "descricao_objeto, fundamentacao, requisitos_tecnicos, modelo_execucao, modelo_gestao, "
        "criterio_medicao, criterio_julgamento, estimativa_preco, qualificacao_habilitacao. "
        "Para cada dimensão, atribua status ok/alerta/critico e uma descrição objetiva. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "bem": (
        "Você é um especialista em contratações públicas federais brasileiras. "
        "Analise o Termo de Referência de BENS/MATERIAIS conforme a IN SEGES/MGI 81/2022, "
        "Lei 14.133/2021 art. 6º XXIII, e critérios de sustentabilidade (IN SLTI 01/2010). "
        "Avalie as 8 dimensões obrigatórias: especificacao_tecnica, justificativa_quantidade, "
        "qualificacao_tecnica, garantia_assistencia, condicoes_entrega, criterio_julgamento, "
        "estimativa_preco, sustentabilidade. "
        "Para cada dimensão, atribua status ok/alerta/critico e uma descrição objetiva. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
    "tic": (
        "Você é um especialista em contratações públicas de Tecnologia da Informação. "
        "Analise o Termo de Referência de SERVIÇOS DE TIC conforme a IN SGD/ME 21/2024, "
        "IN SEGES/MGI 81/2022, Lei 14.133/2021 art. 6º XXIII, e LGPD (Lei 13.709/2018). "
        "Avalie as 9 dimensões obrigatórias: alinhamento_pdtic, analise_viabilidade, solucao_ti, "
        "criterios_aceite_ans, equipe_tecnica, seguranca_lgpd, modelo_execucao, "
        "transicao_contratual, estimativa_preco. "
        "Para cada dimensão, atribua status ok/alerta/critico e uma descrição objetiva. "
        "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
    ),
})

_BASE_LEGAL_PADRAO: types.MappingProxyType[str, tuple[str, ...]] = types.MappingProxyType({
    "servico": (
        "IN SEGES/MGI 81/2022 (Termo de Referência e Projeto Básico)",
        "Lei 14.133/2021, Art. 6º, XXIII (definição de TR)",
        "Lei 14.133/2021, Art. 40 (conteúdo do edital e TR)",
    ),
    "bem": (
        "IN SEGES/MGI 81/2022",
        "Lei 14.133/2021, Art. 6º, XXIII",
        "IN SLTI/MPOG 01/2010 (sustentabilidade ambiental)",
    ),
    "tic": (
        "IN SGD/ME 21/2024 (contratações de soluções de TIC)",
        "IN SEGES/MGI 81/2022",
        "Lei 14.133/2021, Art. 6º, XXIII",
        "Lei 13.709/2018 — LGPD (proteção de dados)",
    ),
})

_ESTRUTURA_JSON = """{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "<chave>": {"status": "ok|alerta|critico", "descricao": "avaliação da dimensão"}
  },
  "pontos_criticos": ["item 1", "item 2"],
  "recomendacoes": ["recomendação 1"],
  "base_legal": ["norma 1", "norma 2"]
}"""


def analisar_tr(
    texto: str,
    tipo_objeto: str,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    """
    Analisa um Termo de Referência e retorna parecer estruturado.

    Parâmetros:
        texto       — conteúdo textual do TR (extraído via etp_extrator)
        tipo_objeto — "servico" | "bem" | "tic"
        api_key     — chave da API Anthropic
        modelo      — modelo Claude a usar (padrão: Haiku)

    Retorna dict com: adequacao_geral, dimensoes, pontos_criticos, recomendacoes, base_legal
    Levanta ValueError para tipo_objeto inválido.
    Levanta RuntimeError para falha de API ou JSON inválido.
    """
    if tipo_objeto not in TIPOS_OBJETO_TR:
        raise ValueError(
            f"Tipo de objeto inválido: '{tipo_objeto}'. Esperado: {list(TIPOS_OBJETO_TR)}"
        )

    prompt = (
        f"Analise o seguinte Termo de Referência ({TIPOS_OBJETO_TR[tipo_objeto]}) "
        f"e avalie sua conformidade com a legislação vigente:\n\n"
        f"{texto}\n\n"
        f"Retorne o parecer no formato JSON:\n{_ESTRUTURA_JSON}"
    )

    try:
        bruto = _chamar_anthropic(
            prompt, api_key, modelo, _SISTEMA_POR_TIPO[tipo_objeto], max_tokens=3000
        )
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
        parecer = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(parecer, dict):
        raise RuntimeError(
            f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(parecer).__name__}"
        )

    _adeq = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    parecer["adequacao_geral"] = _adeq if _adeq in _ADEQ_VALIDOS else "INADEQUADO"

    if not parecer.get("base_legal"):
        parecer["base_legal"] = list(_BASE_LEGAL_PADRAO[tipo_objeto])

    return parecer
```

- [ ] **Step 2: Rodar os 8 testes e verificar que passam**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python3 -m pytest tests/test_ia_tr.py -v
```

Esperado: `8 passed`

- [ ] **Step 3: Rodar a suite completa para verificar não há regressões**

```bash
python3 -m pytest tests/ -q
```

Esperado: `176 passed` (168 anteriores + 8 novos)

- [ ] **Step 4: Commit**

```bash
git add ia_tr.py tests/test_ia_tr.py
git commit -m "feat(tr): implementar ia_tr — análise type-aware de TR (servico/bem/tic)"
```

---

## Task 3: relatorio_tr.py — Testes de PDF

**Files:**
- Create: `tests/test_relatorio_tr.py`

- [ ] **Step 1: Criar o arquivo de testes**

```python
# tests/test_relatorio_tr.py
from __future__ import annotations
import relatorio_tr


def _parecer_servico() -> dict:
    return {
        "adequacao_geral": "ADEQUADO COM RESSALVAS",
        "dimensoes": {
            "descricao_objeto":         {"status": "ok",     "descricao": "Objeto claro."},
            "fundamentacao":            {"status": "ok",     "descricao": "Justificado."},
            "requisitos_tecnicos":      {"status": "alerta", "descricao": "Incompleto."},
            "modelo_execucao":          {"status": "ok",     "descricao": "Definido."},
            "modelo_gestao":            {"status": "ok",     "descricao": "Fiscalização prevista."},
            "criterio_medicao":         {"status": "ok",     "descricao": "Unidade definida."},
            "criterio_julgamento":      {"status": "ok",     "descricao": "Menor preço."},
            "estimativa_preco":         {"status": "alerta", "descricao": "Fontes insuficientes."},
            "qualificacao_habilitacao": {"status": "ok",     "descricao": "Proporcional."},
        },
        "pontos_criticos": ["Requisitos incompletos."],
        "recomendacoes": ["Detalhar especificações."],
        "base_legal": ["IN SEGES/MGI 81/2022", "Lei 14.133/2021, Art. 6º, XXIII"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_tr.gerar_pdf("Serviço de Limpeza", "servico", _parecer_servico())
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_tr.gerar_pdf("Aquisição de Computadores", "bem", {
            "adequacao_geral": "ADEQUADO",
            "dimensoes": {
                "especificacao_tecnica":    {"status": "ok", "descricao": "Completa."},
                "justificativa_quantidade": {"status": "ok", "descricao": "Histórico."},
                "qualificacao_tecnica":     {"status": "ok", "descricao": "INMETRO."},
                "garantia_assistencia":     {"status": "ok", "descricao": "24 meses."},
                "condicoes_entrega":        {"status": "ok", "descricao": "30 dias."},
                "criterio_julgamento":      {"status": "ok", "descricao": "Menor preço."},
                "estimativa_preco":         {"status": "ok", "descricao": "Pesquisa ok."},
                "sustentabilidade":         {"status": "ok", "descricao": "Critérios ok."},
            },
            "pontos_criticos": [],
            "recomendacoes": [],
            "base_legal": ["IN SEGES/MGI 81/2022"],
        })
        assert pdf[:4] == b"%PDF"

    def test_tamanho_minimo(self):
        pdf = relatorio_tr.gerar_pdf("Sistema de Gestão", "tic", {
            "adequacao_geral": "INADEQUADO",
            "dimensoes": {
                "alinhamento_pdtic":    {"status": "critico", "descricao": "Ausente."},
                "analise_viabilidade":  {"status": "critico", "descricao": "AVC ausente."},
                "solucao_ti":           {"status": "alerta",  "descricao": "Incompleta."},
                "criterios_aceite_ans": {"status": "ok",      "descricao": "ANS ok."},
                "equipe_tecnica":       {"status": "ok",      "descricao": "INTECTI ok."},
                "seguranca_lgpd":       {"status": "alerta",  "descricao": "LGPD parcial."},
                "modelo_execucao":      {"status": "ok",      "descricao": "Ágil."},
                "transicao_contratual": {"status": "critico", "descricao": "Ausente."},
                "estimativa_preco":     {"status": "ok",      "descricao": "Benchmark ok."},
            },
            "pontos_criticos": ["PDTIC ausente."],
            "recomendacoes": ["Elaborar PDTIC."],
            "base_legal": ["IN SGD/ME 21/2024"],
        })
        assert len(pdf) > 1024

    def test_todos_os_tipos_de_objeto_nao_levantam_excecao(self):
        parecer_base = {
            "adequacao_geral": "ADEQUADO",
            "dimensoes": {},
            "pontos_criticos": [],
            "recomendacoes": [],
            "base_legal": [],
        }
        for tipo in ("servico", "bem", "tic"):
            pdf = relatorio_tr.gerar_pdf("Objeto de teste", tipo, parecer_base)
            assert pdf[:4] == b"%PDF", f"Falhou para tipo={tipo}"
```

- [ ] **Step 2: Verificar que os testes falham (relatorio_tr não existe ainda)**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python3 -m pytest tests/test_relatorio_tr.py -v 2>&1 | head -10
```

Esperado: `ModuleNotFoundError: No module named 'relatorio_tr'`

---

## Task 4: relatorio_tr.py — Implementação

**Files:**
- Create: `relatorio_tr.py`

- [ ] **Step 1: Criar relatorio_tr.py**

```python
# relatorio_tr.py
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

_COR_ADEQUACAO = {
    "ADEQUADO":               colors.HexColor(_COR_STATUS["ok"]),
    "ADEQUADO COM RESSALVAS": colors.HexColor("#F39C12"),
    "INADEQUADO":             colors.HexColor(_COR_STATUS["critico"]),
}

_LABEL_DIMENSAO_SERVICO = {
    "descricao_objeto":         "Descrição do Objeto",
    "fundamentacao":            "Fundamentação da Necessidade",
    "requisitos_tecnicos":      "Requisitos Técnicos",
    "modelo_execucao":          "Modelo de Execução",
    "modelo_gestao":            "Modelo de Gestão",
    "criterio_medicao":         "Critério de Medição e Pagamento",
    "criterio_julgamento":      "Critério de Julgamento",
    "estimativa_preco":         "Estimativa de Preços",
    "qualificacao_habilitacao": "Qualificação e Habilitação",
}

_LABEL_DIMENSAO_BEM = {
    "especificacao_tecnica":    "Especificação Técnica",
    "justificativa_quantidade": "Justificativa de Quantidade",
    "qualificacao_tecnica":     "Qualificação Técnica",
    "garantia_assistencia":     "Garantia e Assistência Técnica",
    "condicoes_entrega":        "Condições de Entrega",
    "criterio_julgamento":      "Critério de Julgamento",
    "estimativa_preco":         "Estimativa de Preços",
    "sustentabilidade":         "Sustentabilidade",
}

_LABEL_DIMENSAO_TIC = {
    "alinhamento_pdtic":    "Alinhamento ao PDTIC",
    "analise_viabilidade":  "Análise de Viabilidade (AVC)",
    "solucao_ti":           "Solução de TI",
    "criterios_aceite_ans": "Critérios de Aceite e ANS/SLA",
    "equipe_tecnica":       "Equipe Técnica (INTECTI)",
    "seguranca_lgpd":       "Segurança da Informação e LGPD",
    "modelo_execucao":      "Modelo de Execução",
    "transicao_contratual": "Transição Contratual",
    "estimativa_preco":     "Estimativa de Preços",
}

_LABEL_DIMENSAO_POR_TIPO = {
    "servico": _LABEL_DIMENSAO_SERVICO,
    "bem":     _LABEL_DIMENSAO_BEM,
    "tic":     _LABEL_DIMENSAO_TIC,
}

_TIPO_LABEL = {
    "servico": "Serviço",
    "bem":     "Bem / Material",
    "tic":     "Serviço de TIC",
}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("tr_titulo", parent=_estilos_base["Title"],   fontSize=16, spaceAfter=4)
_ESTILO_H1      = ParagraphStyle("tr_h1",     parent=_estilos_base["Heading1"])
_ESTILO_H2      = ParagraphStyle("tr_h2",     parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("tr_corpo",  parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("tr_peq",    parent=_estilos_base["Normal"],   fontSize=8, textColor=colors.grey)
_ESTILO_BADGE   = ParagraphStyle("tr_badge",  parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def gerar_pdf(
    nome_objeto: str,
    tipo_objeto: str,
    parecer: dict,
) -> bytes:
    """Gera PDF do parecer de Termo de Referência. Retorna bytes do PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []
    tipo_label = _TIPO_LABEL.get(tipo_objeto, tipo_objeto)

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Auditoria de Termo de Referência", _ESTILO_H1))
    story.append(Paragraph("IN SEGES/MGI 81/2022 · Lei 14.133/2021, art. 6º, XXIII", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Tipo de objeto: {html.escape(tipo_label)}", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Objeto analisado
    story.append(Paragraph("Objeto Analisado", _ESTILO_H2))
    story.append(Paragraph(html.escape(str(nome_objeto)), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Adequação geral — badge colorido
    adequacao = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    cor = _COR_ADEQUACAO.get(adequacao, colors.grey)
    story.append(Paragraph("Adequação Geral", _ESTILO_H2))
    t_adeq = Table(
        [[Paragraph(f"<b>{html.escape(adequacao)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm],
    )
    t_adeq.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_adeq)
    story.append(Spacer(1, 0.4*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    label_map = _LABEL_DIMENSAO_POR_TIPO.get(tipo_objeto, {})
    dims = parecer.get("dimensoes") or {}
    for chave, label in label_map.items():
        dim = dims.get(chave) or {}
        status = (dim.get("status") or "ok").lower()
        cor_s = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor_s}'><b>[{icone}] {html.escape(label)}</b></font>: "
            f"{html.escape(str(dim.get('descricao') or '-'))}",
            _ESTILO_CORPO,
        ))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos") or []
    if criticos:
        story.append(Paragraph("Pontos Críticos", _ESTILO_H2))
        for i, ponto in enumerate(criticos, 1):
            story.append(Paragraph(f"{i}. {html.escape(str(ponto or ''))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes") or []
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            story.append(Paragraph(f"{i}. {html.escape(str(rec or ''))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    story.append(Paragraph("Base Legal", _ESTILO_H2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificação humana. "
        "Não substitui parecer jurídico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 2: Rodar os 4 testes de PDF**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python3 -m pytest tests/test_relatorio_tr.py -v
```

Esperado: `4 passed`

- [ ] **Step 3: Rodar a suite completa**

```bash
python3 -m pytest tests/ -q
```

Esperado: `180 passed` (168 + 8 + 4)

- [ ] **Step 4: Commit**

```bash
git add relatorio_tr.py tests/test_relatorio_tr.py
git commit -m "feat(tr): implementar relatorio_tr — geração de PDF do parecer de TR"
```

---

## Task 5: app.py — Nova aba "📝 Auditoria de TR"

**Files:**
- Modify: `app.py`

- [ ] **Step 1: Adicionar imports de ia_tr e relatorio_tr**

No topo de `app.py`, após as outras importações de módulos IA (buscar por `import ia_pi_empresas` ou similar), adicionar:

```python
import ia_tr
import relatorio_tr
```

Exemplo de onde inserir (após a linha `import ia_recebimento` ou agrupado com os demais):

```python
import ia_ddi
import ia_etp
import ia_integridade
import ia_pi_empresas
import ia_contratos
import ia_recebimento
import ia_tr           # <-- adicionar aqui
import relatorio_tr    # <-- e aqui
```

- [ ] **Step 2: Expandir st.tabs para incluir a 7ª aba**

Localizar a linha atual:

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

Substituir por:

```python
aba1, aba2, aba3, aba4, aba5, aba6, aba7 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
    "📝 Auditoria de TR",
])
```

- [ ] **Step 3: Adicionar o bloco `with aba7:` no final do arquivo**

Adicionar após o último bloco `with aba6:` (que termina antes do `if __name__ == "__main__":` ou simplesmente no final do arquivo):

```python
with aba7:
    st.subheader("Auditoria de Termo de Referência — IN SEGES 81/2022")
    st.caption("Lei 14.133/2021, Art. 6º, XXIII · IN SEGES/MGI 81/2022 · IN SGD/ME 21/2024 (TIC)")

    _api_key_tr = _get_api_key()
    _modelo_tr = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    _tipo_tr_opcoes = {"Serviço": "servico", "Bem / Material": "bem", "Serviço de TIC": "tic"}
    _tipo_tr_label = st.radio(
        "Tipo de objeto",
        list(_tipo_tr_opcoes.keys()),
        horizontal=True,
        key="tr_tipo",
    )
    _tipo_tr = _tipo_tr_opcoes[_tipo_tr_label]

    _arq_tr = st.file_uploader(
        "Envie o TR em PDF ou DOCX",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="tr_arquivo",
    )

    if st.button("Analisar TR", type="primary", key="btn_tr", disabled=not _arq_tr):
        if not _api_key_tr:
            st.error("ANTHROPIC_API_KEY não configurada — configure via variável de ambiente ou secrets.toml.")
        else:
            try:
                with st.spinner("Extraindo texto e analisando com IA (pode levar 1-2 minutos)..."):
                    _texto_tr, _avisos_tr = etp_extrator.extrair_texto(_arq_tr)
                    _parecer_tr = ia_tr.analisar_tr(_texto_tr, _tipo_tr, _api_key_tr, _modelo_tr)
                st.session_state["tr_parecer"] = _parecer_tr
                st.session_state["tr_avisos"] = _avisos_tr
                st.session_state["tr_tipo"] = _tipo_tr
                st.session_state["tr_nome"] = _arq_tr[0].name if _arq_tr else "TR"
            except ValueError as e:
                st.error(str(e))
            except RuntimeError as e:
                st.error(str(e))

    if "tr_parecer" in st.session_state:
        _pr_tr = st.session_state["tr_parecer"]
        _av_tr = st.session_state["tr_avisos"]
        _tipo_tr_saved = st.session_state["tr_tipo"]
        _nome_tr = st.session_state["tr_nome"]

        for _aviso in _av_tr:
            st.warning(_safe_md(_aviso))

        st.divider()
        _adeq_tr = str(_pr_tr.get("adequacao_geral") or "INADEQUADO").strip().upper()
        _icone_adeq_tr = {"ADEQUADO": "🟢", "ADEQUADO COM RESSALVAS": "🟡", "INADEQUADO": "🔴"}
        st.subheader(f"{_icone_adeq_tr.get(_adeq_tr, '⚪')} Adequação Geral: {_safe_md(_adeq_tr)}")

        _dims_tr = _pr_tr.get("dimensoes") or {}
        _labels_tr = relatorio_tr._LABEL_DIMENSAO_POR_TIPO.get(_tipo_tr_saved, {})
        _ic_st_tr = {"ok": "✅", "alerta": "⚠️", "critico": "❌"}
        for _ch_tr, _lb_tr in _labels_tr.items():
            _d_tr = _dims_tr.get(_ch_tr) or {}
            _ic_tr = _ic_st_tr.get((_d_tr.get("status") or "ok").lower(), "ℹ️")
            with st.expander(f"{_ic_tr} {_lb_tr}"):
                st.write(_safe_md(_d_tr.get("descricao") or "—"))

        _criticos_tr = _pr_tr.get("pontos_criticos") or []
        if _criticos_tr:
            st.subheader("Pontos Críticos")
            for _c_tr in _criticos_tr:
                if _c_tr:
                    st.error(_safe_md(_c_tr))

        _recs_tr = _pr_tr.get("recomendacoes") or []
        if _recs_tr:
            st.subheader("Recomendações ao Gestor")
            for _r_tr in _recs_tr:
                if _r_tr:
                    st.info(_safe_md(_r_tr))

        with st.expander("Base Legal"):
            for _bl_tr in (_pr_tr.get("base_legal") or []):
                if _bl_tr:
                    st.write(f"• {_safe_md(_bl_tr)}")

        try:
            _pdf_tr = relatorio_tr.gerar_pdf(_nome_tr, _tipo_tr_saved, _pr_tr)
            st.download_button(
                label="Baixar Relatório PDF",
                data=_pdf_tr,
                file_name="TR_auditoria.pdf",
                mime="application/pdf",
                key="tr_download",
            )
        except Exception as _e_tr:
            st.error(f"Erro ao gerar PDF: {_e_tr}")
```

- [ ] **Step 4: Verificar que o app importa sem erros**

```bash
cd /Users/robertomauricioferreiraribeiro/Documents/Daysival
python3 -c "import app" 2>&1 | head -5
```

Esperado: nenhuma saída (importação limpa)

- [ ] **Step 5: Rodar a suite completa — garantir 180 testes passando**

```bash
python3 -m pytest tests/ -q
```

Esperado: `180 passed`

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat(tr): adicionar aba 'Auditoria de TR' ao app Streamlit"
```

---

## Task 6: Push para produção

- [ ] **Step 1: Verificar estado do repositório**

```bash
git log --oneline -5
git status
```

- [ ] **Step 2: Push**

```bash
git -c credential.helper= push origin main
```

Após o push, o Streamlit Cloud detecta automaticamente e faz redeploy em ~1 minuto.

---

## Self-Review

### Cobertura da spec

| Requisito da spec | Task que implementa |
|---|---|
| `TIPOS_OBJETO_TR = {"servico", "bem", "tic"}` | Task 2 — `ia_tr.py` |
| `analisar_tr(texto, tipo_objeto, api_key, modelo) -> dict` | Task 2 |
| `adequacao_geral` normalização para INADEQUADO | Task 2 |
| Raises `ValueError` para tipo inválido | Task 2 + Task 1 (test_tipo_invalido) |
| Raises `RuntimeError` para API failure | Task 2 + Task 1 (test_httperror) |
| Split try/except (HTTP + JSON separados) | Task 2 |
| 9 dimensões para serviço | Task 2 (system prompt lista todas) |
| 8 dimensões para bem | Task 2 (system prompt lista todas) |
| 9 dimensões para TIC (+ LGPD) | Task 2 (system prompt lista todas) |
| `gerar_pdf(nome_objeto, tipo_objeto, parecer) -> bytes` | Task 4 |
| Badge colorido de `adequacao_geral` | Task 4 |
| Labels por tipo no PDF | Task 4 (`_LABEL_DIMENSAO_POR_TIPO`) |
| Rodapé com aviso "Sujeito a verificação humana" | Task 4 |
| `COR_STATUS_HEX` de ia_utils | Task 4 |
| Nova aba7 "📝 Auditoria de TR" | Task 5 |
| `st.radio` tipo de objeto | Task 5 |
| Upload PDF/DOCX via `etp_extrator.extrair_texto` | Task 5 |
| Botão desabilitado sem arquivo | Task 5 (`disabled=not _arq_tr`) |
| Avisos de extração exibidos | Task 5 |
| Download button para PDF | Task 5 |
| 8 testes unitários para ia_tr | Task 1 |
| 4 testes para relatorio_tr | Task 3 |
| Patch via `@patch("ia_utils.urllib.request.urlopen")` | Tasks 1 e 3 |
| Base legal por tipo (fallback) | Task 2 (`_BASE_LEGAL_PADRAO`) |

### Verificação de consistência de tipos

- `ia_tr.analisar_tr(texto, tipo_objeto, api_key, modelo)` — usado em Task 5 com todos os 4 parâmetros ✓
- `relatorio_tr.gerar_pdf(nome_objeto, tipo_objeto, parecer)` — usado em Task 5 com 3 parâmetros ✓
- `relatorio_tr._LABEL_DIMENSAO_POR_TIPO` — acessado em Task 5 como dict indexado por tipo ✓
- `etp_extrator.extrair_texto(_arq_tr)` — retorna `(str, list[str])` ✓
