# Módulo 6 — Reabilitação de Fornecedor: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o módulo de reabilitação de fornecedor (Art. 163, Par. Único, Lei 14.133/2021) com checklist de elegibilidade via IA e geração de dois PDFs (relatório técnico + minuta do requerimento).

**Architecture:** Dois novos módulos (`ia_reabilitacao.py` para lógica de análise, `relatorio_reabilitacao.py` para PDFs), nova aba9 em `app.py`. Reusa `ddi_consultas.py` para lookup CEIS/CNEP e `etp_extrator.extrair_texto()` para documentos. Fluxo 3-etapas em aba única: identificação → questionário → resultado.

**Tech Stack:** Python 3.9, Streamlit, ReportLab, Anthropic Claude Haiku API, unittest.mock, pytest.

---

## File Map

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `ia_reabilitacao.py` | Criar | Constantes legais, `calcular_prazo()`, `analisar()` |
| `relatorio_reabilitacao.py` | Criar | `gerar_relatorio_tecnico()`, `gerar_minuta_requerimento()` |
| `tests/test_ia_reabilitacao.py` | Criar | Testes de `calcular_prazo` e `analisar` |
| `tests/test_relatorio_reabilitacao.py` | Criar | Testes dos dois geradores de PDF |
| `app.py` | Modificar | Adicionar imports + aba9 com fluxo 3-etapas |

---

## Task 1: `ia_reabilitacao.py` — constantes + `calcular_prazo()`

**Files:**
- Create: `ia_reabilitacao.py`
- Test: `tests/test_ia_reabilitacao.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_ia_reabilitacao.py
from __future__ import annotations
import pytest
from datetime import date
import ia_reabilitacao


class TestConstantes:
    def test_tipos_sancao_tem_impedimento_e_inidoneidade(self):
        assert set(ia_reabilitacao.TIPOS_SANCAO.keys()) == {"impedimento", "inidoneidade"}

    def test_prazos_minimos_anos(self):
        assert ia_reabilitacao.PRAZOS_MINIMOS_ANOS["impedimento"] == 1
        assert ia_reabilitacao.PRAZOS_MINIMOS_ANOS["inidoneidade"] == 3

    def test_parecer_options_tem_3_opcoes(self):
        assert set(ia_reabilitacao.PARECER_OPTIONS.keys()) == {
            "ELEGÍVEL", "ELEGÍVEL COM RESSALVAS", "INELEGÍVEL"
        }

    def test_constantes_sao_mapping_proxy(self):
        import types
        assert isinstance(ia_reabilitacao.TIPOS_SANCAO, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.PRAZOS_MINIMOS_ANOS, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.PARECER_OPTIONS, types.MappingProxyType)
        assert isinstance(ia_reabilitacao.NORM_PARECER_REAB, types.MappingProxyType)


class TestCalcularPrazo:
    def test_prazo_atendido_impedimento_2_anos(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2024, 6, 8)  # 2 anos antes
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is True
        assert r["anos_decorridos"] == 2
        assert r["prazo_minimo_anos"] == 1

    def test_prazo_nao_atendido_inidoneidade_1_ano(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 8)  # 1 ano antes, mas precisa 3
        r = ia_reabilitacao.calcular_prazo("inidoneidade", aplicacao, data_referencia=ref)
        assert r["atendido"] is False
        assert r["prazo_minimo_anos"] == 3

    def test_exatamente_no_limite_atendido(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 8)  # exatamente 1 ano antes
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is True  # >= prazo mínimo

    def test_um_dia_antes_do_limite_nao_atendido(self):
        ref = date(2026, 6, 8)
        aplicacao = date(2025, 6, 9)  # 1 dia a mais que 1 ano
        r = ia_reabilitacao.calcular_prazo("impedimento", aplicacao, data_referencia=ref)
        assert r["atendido"] is False

    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="tipo_sancao inválido"):
            ia_reabilitacao.calcular_prazo("inexistente", date(2024, 1, 1))
```

- [ ] **Step 2: Rodar para confirmar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_reabilitacao.py -v 2>&1 | head -20
```

Esperado: `ModuleNotFoundError: No module named 'ia_reabilitacao'`

- [ ] **Step 3: Criar `ia_reabilitacao.py` com constantes + `calcular_prazo()`**

```python
# ia_reabilitacao.py
from __future__ import annotations
import types
import urllib.error
from datetime import date

from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

TIPOS_SANCAO: types.MappingProxyType[str, str] = types.MappingProxyType({
    "impedimento":  "Impedimento de Licitar e Contratar (Art. 156, III)",
    "inidoneidade": "Declaração de Inidoneidade (Art. 156, IV)",
})

PRAZOS_MINIMOS_ANOS: types.MappingProxyType[str, int] = types.MappingProxyType({
    "impedimento":  1,
    "inidoneidade": 3,
})

PARECER_OPTIONS: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ELEGÍVEL":               "ELEGÍVEL",
    "ELEGÍVEL COM RESSALVAS": "ELEGÍVEL COM RESSALVAS",
    "INELEGÍVEL":             "INELEGÍVEL",
})

NORM_PARECER_REAB: types.MappingProxyType[str, str] = types.MappingProxyType({
    "ELEGIVEL":               "ELEGÍVEL",
    "ELEGIVEL COM RESSALVAS": "ELEGÍVEL COM RESSALVAS",
    "INELEGIVEL":             "INELEGÍVEL",
})


def calcular_prazo(
    tipo_sancao: str,
    data_aplicacao: date,
    data_referencia: date | None = None,
) -> dict:
    if tipo_sancao not in PRAZOS_MINIMOS_ANOS:
        raise ValueError(
            f"tipo_sancao inválido: '{tipo_sancao}'. Esperado: {list(TIPOS_SANCAO)}"
        )
    hoje = data_referencia or date.today()
    prazo_anos = PRAZOS_MINIMOS_ANOS[tipo_sancao]

    anos = hoje.year - data_aplicacao.year
    meses = hoje.month - data_aplicacao.month
    if hoje.day < data_aplicacao.day:
        meses -= 1
    if meses < 0:
        anos -= 1
        meses += 12

    total_meses = anos * 12 + meses
    return {
        "atendido":         total_meses >= prazo_anos * 12,
        "anos_decorridos":  anos,
        "meses_decorridos": meses,
        "prazo_minimo_anos": prazo_anos,
    }
```

- [ ] **Step 4: Rodar para confirmar que os testes passam**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_reabilitacao.py::TestConstantes tests/test_ia_reabilitacao.py::TestCalcularPrazo -v
```

Esperado: 9 PASSED

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/Daysival && git add ia_reabilitacao.py tests/test_ia_reabilitacao.py && git commit -m "feat(reabilitacao): constantes e calcular_prazo() com testes"
```

---

## Task 2: `ia_reabilitacao.py` — função `analisar()`

**Files:**
- Modify: `ia_reabilitacao.py`
- Modify: `tests/test_ia_reabilitacao.py`

- [ ] **Step 1: Adicionar testes de `analisar()` ao arquivo de testes existente**

Adicionar ao final de `tests/test_ia_reabilitacao.py`:

```python
import json
import urllib.error
from unittest.mock import patch, MagicMock


def _dados_empresa_mock() -> dict:
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "ceis": [],
        "cnep": [],
    }


def _dados_sancao_mock(tipo: str = "impedimento") -> dict:
    return {
        "tipo_sancao":            tipo,
        "data_aplicacao":         date(2024, 1, 1),
        "orgao":                  "Ministério da Gestão",
        "multa_aplicada":         True,
        "multa_valor":            5000.0,
        "multa_quitada":          True,
        "condicoes_ato_punitivo": "Implementar programa de compliance.",
    }


def _respostas_mock() -> dict:
    return {
        "reparacao":            "Sim (integral)",
        "reparacao_descricao":  "Ressarcimento comprovado via depósito.",
        "cond_ato_cumpridas":   "Sim",
        "analise_juridica":     "Realizada",
    }


def _parecer_api_mock() -> dict:
    return {
        "parecer": "ELEGÍVEL",
        "condicoes_avaliadas": [
            {"numero": "I",   "descricao": "Reparação do dano",   "status": "ATENDIDA", "observacao": ""},
            {"numero": "II",  "descricao": "Pagamento de multa",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "III", "descricao": "Prazo mínimo",        "status": "ATENDIDA", "observacao": ""},
            {"numero": "IV",  "descricao": "Cond. ato punitivo",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "V",   "descricao": "Análise jurídica",    "status": "ATENDIDA", "observacao": ""},
        ],
        "sintese":    "Todas as condições do Art. 163 estão atendidas.",
        "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"],
    }


def _mock_urlopen(payload: dict):
    data = json.dumps({"content": [{"text": json.dumps(payload)}]}).encode("utf-8")
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
    cm.__exit__ = MagicMock(return_value=False)
    return cm


class TestAnalisar:
    def test_tipo_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="tipo_sancao inválido"):
            ia_reabilitacao.analisar(
                "inexistente", {}, {}, {}, None, "key"
            )

    def test_prazo_nao_decorrido_retorna_inelegivel_sem_chamar_api(self):
        dados_sancao = {
            **_dados_sancao_mock("inidoneidade"),
            "data_aplicacao": date(2025, 6, 8),  # apenas 1 ano atrás, precisa 3
        }
        with patch("urllib.request.urlopen") as mock_url:
            r = ia_reabilitacao.analisar(
                "inidoneidade", _dados_empresa_mock(), dados_sancao, _respostas_mock(), None, "key"
            )
        mock_url.assert_not_called()
        assert r["parecer"] == "INELEGÍVEL"

    def test_retorna_elegivel_com_api_mock(self):
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_parecer_api_mock())):
            r = ia_reabilitacao.analisar(
                "impedimento",
                _dados_empresa_mock(),
                _dados_sancao_mock(),
                _respostas_mock(),
                None,
                "key",
            )
        assert r["parecer"] == "ELEGÍVEL"
        assert "dados_empresa" in r
        assert "dados_sancao" in r

    def test_alias_sem_acento_normalizado(self):
        payload = {**_parecer_api_mock(), "parecer": "ELEGIVEL"}
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(payload)):
            r = ia_reabilitacao.analisar(
                "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
            )
        assert r["parecer"] == "ELEGÍVEL"

    def test_json_malformado_levanta_runtime_error(self):
        data = json.dumps({"content": [{"text": "não é json"}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=data)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="JSON válido"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        payload = json.dumps({"content": [{"text": json.dumps([1, 2, 3])}]}).encode("utf-8")
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=MagicMock(read=MagicMock(return_value=payload)))
        cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )

    def test_http_error_levanta_runtime_error(self):
        err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid"}')),
        )
        with patch("urllib.request.urlopen", side_effect=err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_reabilitacao.analisar(
                    "impedimento", _dados_empresa_mock(), _dados_sancao_mock(), _respostas_mock(), None, "key"
                )
```

- [ ] **Step 2: Rodar para confirmar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_reabilitacao.py::TestAnalisar -v 2>&1 | head -20
```

Esperado: `AttributeError: module 'ia_reabilitacao' has no attribute 'analisar'`

- [ ] **Step 3: Adicionar `_SISTEMA`, `_ESTRUTURA_PARECER` e `analisar()` a `ia_reabilitacao.py`**

Adicionar ao final de `ia_reabilitacao.py` (após `calcular_prazo`):

```python
_SISTEMA = (
    "Você é um especialista em licitações e contratos públicos brasileiros. "
    "Analise o pedido de reabilitação de fornecedor com base no Art. 163, Parágrafo Único, "
    "da Lei 14.133/2021. Avalie cada uma das 5 condições cumulativas e emita parecer de "
    "elegibilidade motivado. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "parecer": "ELEGÍVEL|ELEGÍVEL COM RESSALVAS|INELEGÍVEL",
  "condicoes_avaliadas": [
    {
      "numero": "I",
      "descricao": "Reparação integral do dano",
      "status": "ATENDIDA|PARCIAL|AUSENTE|N.A.",
      "observacao": "..."
    }
  ],
  "sintese": "Parágrafo conclusivo fundamentado no Art. 163 Par. Único, Lei 14.133/2021",
  "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"]
}"""


def analisar(
    tipo_sancao: str,
    dados_empresa: dict,
    dados_sancao: dict,
    respostas_condicoes: dict,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    if tipo_sancao not in TIPOS_SANCAO:
        raise ValueError(
            f"tipo_sancao inválido: '{tipo_sancao}'. Esperado: {list(TIPOS_SANCAO)}"
        )

    # Guarda de prazo: retorna INELEGÍVEL sem chamar a IA
    _data_apl = dados_sancao.get("data_aplicacao")
    if isinstance(_data_apl, date):
        _prazo = calcular_prazo(tipo_sancao, _data_apl)
        if not _prazo["atendido"]:
            _min = _prazo["prazo_minimo_anos"]
            _a = _prazo["anos_decorridos"]
            _m = _prazo["meses_decorridos"]
            return {
                "parecer": "INELEGÍVEL",
                "condicoes_avaliadas": [{
                    "numero": "III",
                    "descricao": "Transcurso do prazo mínimo",
                    "status": "AUSENTE",
                    "observacao": (
                        f"Prazo mínimo de {_min} ano(s) não decorrido. "
                        f"Decorrido: {_a} ano(s) e {_m} mês(es)."
                    ),
                }],
                "sintese": (
                    f"Reabilitação inelegível: prazo mínimo de {_min} ano(s) previsto no "
                    "Art. 163, Par. Único, III, da Lei 14.133/2021 ainda não foi cumprido."
                ),
                "base_legal": ["Art. 163, Par. Único, III, Lei 14.133/2021"],
                "dados_empresa": dados_empresa,
                "dados_sancao":  dados_sancao,
            }

    _tipo_label    = TIPOS_SANCAO[tipo_sancao]
    _multa_apl     = dados_sancao.get("multa_aplicada", False)
    _multa_quit    = dados_sancao.get("multa_quitada",  False)
    _multa_valor   = dados_sancao.get("multa_valor") or 0.0

    partes = [
        f"Análise de Pedido de Reabilitação — {_tipo_label}\n",
        f"Empresa: {dados_empresa.get('razao_social') or 'não informado'}",
        f"CNPJ: {dados_empresa.get('cnpj') or 'não informado'}",
        f"Órgão sancionador: {dados_sancao.get('orgao') or 'não informado'}",
        f"Data de aplicação da sanção: {dados_sancao.get('data_aplicacao') or 'não informada'}",
        "",
        "Condições do Art. 163, Par. Único, Lei 14.133/2021:",
        f"Condição I — Reparação integral do dano: {respostas_condicoes.get('reparacao') or 'não informado'}",
        f"  Descrição/comprovação: {respostas_condicoes.get('reparacao_descricao') or 'não informada'}",
        f"Condição II — Multa aplicada: {'Sim' if _multa_apl else 'Não'}",
    ]
    if _multa_apl:
        partes.append(
            f"  Valor: {'não informado' if not _multa_valor else f'R$ {float(_multa_valor):.2f}'}"
        )
        partes.append(f"  Multa quitada: {'Sim' if _multa_quit else 'Não'}")

    partes += [
        f"Condição III — Prazo mínimo ({PRAZOS_MINIMOS_ANOS[tipo_sancao]} ano(s)): Decorrido (verificado automaticamente)",
        "Condição IV — Condições do ato punitivo:",
        f"  Descrição das condições: {dados_sancao.get('condicoes_ato_punitivo') or 'não informado'}",
        f"  Condições cumpridas: {respostas_condicoes.get('cond_ato_cumpridas') or 'não informado'}",
        f"Condição V — Análise jurídica prévia: {respostas_condicoes.get('analise_juridica') or 'não informado'}",
    ]

    if texto_docs:
        partes.append(f"\nDocumentos comprobatórios fornecidos:\n{texto_docs[:30000]}")
    else:
        partes.append("\nNenhum documento adicional fornecido.")

    partes.append(f"\nRetorne o parecer no formato JSON:\n{_ESTRUTURA_PARECER}")

    try:
        bruto = _chamar_anthropic(
            "\n".join(partes), api_key, modelo, _SISTEMA, max_tokens=3000
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
            f"Resposta inesperada da API: objeto JSON esperado, "
            f"recebeu {type(parecer).__name__}"
        )

    _pval = str(parecer.get("parecer") or "INELEGÍVEL").strip().upper()
    parecer["parecer"] = NORM_PARECER_REAB.get(_pval, _pval)
    return {**parecer, "dados_empresa": dados_empresa, "dados_sancao": dados_sancao}
```

- [ ] **Step 4: Rodar todos os testes de `ia_reabilitacao`**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_reabilitacao.py -v
```

Esperado: 16 PASSED

- [ ] **Step 5: Confirmar que a suite completa passa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: `226+ passed`

- [ ] **Step 6: Commit**

```bash
cd ~/Documents/Daysival && git add ia_reabilitacao.py tests/test_ia_reabilitacao.py && git commit -m "feat(reabilitacao): analisar() com guarda de prazo e normalização de parecer"
```

---

## Task 3: `relatorio_reabilitacao.py` — `gerar_relatorio_tecnico()`

**Files:**
- Create: `relatorio_reabilitacao.py`
- Create: `tests/test_relatorio_reabilitacao.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/test_relatorio_reabilitacao.py
from __future__ import annotations
import pytest
from datetime import date
import relatorio_reabilitacao


def _dados_empresa():
    return {
        "razao_social": "EMPRESA TESTE LTDA",
        "cnpj": "11222333000181",
        "porte": "MICRO EMPRESA",
    }


def _dados_sancao(tipo: str = "impedimento"):
    return {
        "tipo_sancao":    tipo,
        "data_aplicacao": date(2024, 1, 1),
        "orgao":          "Ministério da Gestão",
        "multa_aplicada": True,
        "multa_valor":    5000.0,
        "multa_quitada":  True,
    }


def _parecer_elegivel():
    return {
        "parecer": "ELEGÍVEL",
        "condicoes_avaliadas": [
            {"numero": "I",   "descricao": "Reparação do dano",  "status": "ATENDIDA", "observacao": ""},
            {"numero": "II",  "descricao": "Pagamento de multa", "status": "ATENDIDA", "observacao": ""},
            {"numero": "III", "descricao": "Prazo mínimo",       "status": "ATENDIDA", "observacao": ""},
            {"numero": "IV",  "descricao": "Cond. punitivo",     "status": "ATENDIDA", "observacao": ""},
            {"numero": "V",   "descricao": "Análise jurídica",   "status": "ATENDIDA", "observacao": ""},
        ],
        "sintese":    "Todas as condições estão atendidas.",
        "base_legal": ["Art. 163, Par. Único, Lei 14.133/2021"],
    }


class TestGerarRelatorioTecnico:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert pdf[:4] == b"%PDF"

    def test_caracteres_especiais_nao_quebram_pdf(self):
        dados = {**_dados_empresa(), "razao_social": "EMPRESA <TESTE> & CIA LTDA"}
        pdf = relatorio_reabilitacao.gerar_relatorio_tecnico(
            "11222333000181", dados, _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000


class TestGerarMinutaRequerimento:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 2000

    def test_comeca_com_magic_bytes_pdf(self):
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao(), _parecer_elegivel()
        )
        assert pdf[:4] == b"%PDF"

    def test_tipo_impedimento_menciona_art_156_iii(self):
        import pdfplumber, io
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao("impedimento"), _parecer_elegivel()
        )
        texto = ""
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            for pg in doc.pages:
                texto += pg.extract_text() or ""
        assert "156" in texto

    def test_tipo_inidoneidade_menciona_art_156_iv(self):
        import pdfplumber, io
        pdf = relatorio_reabilitacao.gerar_minuta_requerimento(
            "11222333000181", _dados_empresa(), _dados_sancao("inidoneidade"), _parecer_elegivel()
        )
        texto = ""
        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            for pg in doc.pages:
                texto += pg.extract_text() or ""
        assert "156" in texto
```

- [ ] **Step 2: Rodar para confirmar que falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_reabilitacao.py -v 2>&1 | head -15
```

Esperado: `ModuleNotFoundError: No module named 'relatorio_reabilitacao'`

- [ ] **Step 3: Criar `relatorio_reabilitacao.py` com `gerar_relatorio_tecnico()`**

```python
# relatorio_reabilitacao.py
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

_LABEL_SANCAO = {
    "impedimento":  "Impedimento de Licitar e Contratar (Art. 156, III)",
    "inidoneidade": "Declaração de Inidoneidade (Art. 156, IV)",
}

_COR_PARECER = {
    "ELEGÍVEL":               colors.HexColor(_COR_STATUS["ok"]),
    "ELEGÍVEL COM RESSALVAS": colors.HexColor(_COR_STATUS["alerta"]),
    "INELEGÍVEL":             colors.HexColor(_COR_STATUS["critico"]),
}

_STATUS_ICONE = {
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
    "N.A.":     "N.A.",
}

_estilos       = getSampleStyleSheet()
_TITULO        = ParagraphStyle("reab_titulo", parent=_estilos["Title"],   fontSize=16, spaceAfter=4)
_H1            = ParagraphStyle("reab_h1",     parent=_estilos["Heading1"])
_H2            = ParagraphStyle("reab_h2",     parent=_estilos["Heading2"], fontSize=12, spaceAfter=3)
_CORPO         = ParagraphStyle("reab_corpo",  parent=_estilos["Normal"],   fontSize=10, spaceAfter=3)
_PEQUENO       = ParagraphStyle("reab_peq",    parent=_estilos["Normal"],   fontSize=8,  textColor=colors.grey)
_BADGE         = ParagraphStyle("reab_badge",  parent=_estilos["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_TITULO_REQ    = ParagraphStyle("reab_req_t",  parent=_estilos["Title"],    fontSize=14, alignment=1, spaceAfter=6)
_SECAO         = ParagraphStyle("reab_secao",  parent=_estilos["Heading2"], fontSize=11, spaceAfter=4)
_CORPO_REQ     = ParagraphStyle("reab_corpo_r", parent=_estilos["Normal"],  fontSize=10, spaceAfter=6, leading=14)


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def gerar_relatorio_tecnico(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Reabilitação de Fornecedor — Relatório Técnico", _H1))
    story.append(Paragraph("Art. 163, Par. Único, Lei 14.133/2021", _PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("Identificação do Fornecedor", _H2))
    _tipo_key   = str(dados_sancao.get("tipo_sancao") or "")
    _tipo_label = _LABEL_SANCAO.get(_tipo_key, html.escape(_tipo_key))
    linhas_id = [
        ["Razão Social",      html.escape(str(dados_empresa.get("razao_social") or "-"))],
        ["CNPJ",              _fmt_cnpj(cnpj)],
        ["Tipo de Sanção",    html.escape(_tipo_label)],
        ["Data da Sanção",    html.escape(str(dados_sancao.get("data_aplicacao") or "-"))],
        ["Órgão Sancionador", html.escape(str(dados_sancao.get("orgao") or "-"))],
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

    _pval    = str(parecer.get("parecer") or "INELEGÍVEL").strip().upper()
    _cor_par = _COR_PARECER.get(_pval, colors.grey)
    story.append(Paragraph("Parecer de Elegibilidade", _H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(_pval)}</b>", _BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _cor_par),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Condições Art. 163, Par. Único (5 condições cumulativas)", _H2))
    for cond in (parecer.get("condicoes_avaliadas") or []):
        if not cond:
            continue
        _st = str(cond.get("status") or "AUSENTE").strip().upper()
        _ic = _STATUS_ICONE.get(_st, _st)
        story.append(Paragraph(
            f"<b>Condição {html.escape(str(cond.get('numero') or ''))}:</b> "
            f"{html.escape(str(cond.get('descricao') or ''))} — {html.escape(_ic)}",
            _CORPO,
        ))
        if cond.get("observacao"):
            story.append(Paragraph(
                f"  {html.escape(str(cond['observacao']))}",
                _PEQUENO,
            ))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Síntese", _H2))
    story.append(Paragraph(html.escape(str(parecer.get("sintese") or "-")), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Base Legal", _H2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _CORPO))
    story.append(Spacer(1, 0.4*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita - RM Vertice Digital. "
        "Sujeito a verificacao humana. Nao substitui parecer juridico.",
        _PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Rodar testes de `gerar_relatorio_tecnico`**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_reabilitacao.py::TestGerarRelatorioTecnico -v
```

Esperado: 3 PASSED

- [ ] **Step 5: Commit parcial**

```bash
cd ~/Documents/Daysival && git add relatorio_reabilitacao.py tests/test_relatorio_reabilitacao.py && git commit -m "feat(reabilitacao): gerar_relatorio_tecnico() com testes"
```

---

## Task 4: `relatorio_reabilitacao.py` — `gerar_minuta_requerimento()`

**Files:**
- Modify: `relatorio_reabilitacao.py`
- Modify: `tests/test_relatorio_reabilitacao.py` (testes já escritos na Task 3)

- [ ] **Step 1: Confirmar que os testes de `gerar_minuta_requerimento` ainda falham**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_reabilitacao.py::TestGerarMinutaRequerimento -v 2>&1 | head -15
```

Esperado: `AttributeError: module 'relatorio_reabilitacao' has no attribute 'gerar_minuta_requerimento'`

- [ ] **Step 2: Adicionar `gerar_minuta_requerimento()` ao final de `relatorio_reabilitacao.py`**

```python
def gerar_minuta_requerimento(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=3*cm, rightMargin=3*cm, topMargin=3*cm, bottomMargin=2.5*cm,
    )
    story = []

    _tipo_key   = str(dados_sancao.get("tipo_sancao") or "")
    _tipo_label = _LABEL_SANCAO.get(_tipo_key, _tipo_key)
    _razao      = html.escape(str(dados_empresa.get("razao_social") or "REQUERENTE"))
    _cnpj_fmt   = _fmt_cnpj(cnpj)
    _orgao      = html.escape(str(dados_sancao.get("orgao") or "não identificado"))
    _data_apl   = html.escape(str(dados_sancao.get("data_aplicacao") or "não informada"))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>REQUERIMENTO DE REABILITAÇÃO</b>", _TITULO_REQ))
    story.append(Paragraph(
        "Fundamento: Art. 163, Parágrafo Único, Lei 14.133/2021", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=12))

    story.append(Paragraph(
        f"<b>{_razao}</b>, pessoa jurídica de direito privado, inscrita no CNPJ sob "
        f"n.º {_cnpj_fmt}, vem respeitosamente à presença de Vossa Senhoria, autoridade "
        "competente do órgão abaixo identificado, com fundamento no Art. 163, Parágrafo "
        "Único, da Lei n.º 14.133/2021, requerer sua <b>REABILITAÇÃO</b>.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>I — DOS FATOS</b>", _SECAO))
    story.append(Paragraph(
        f"A requerente foi objeto de sanção de <b>{html.escape(_tipo_label)}</b>, "
        f"aplicada pelo órgão/entidade <b>{_orgao}</b>, em {_data_apl}.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>II — DO DIREITO</b>", _SECAO))
    story.append(Paragraph(
        "O Art. 163, Parágrafo Único, da Lei n.º 14.133/2021, autoriza a reabilitação "
        "do fornecedor sancionado mediante o cumprimento cumulativo das seguintes condições:",
        _CORPO_REQ,
    ))
    _conds_legais = [
        ("I",   "Reparação integral do dano causado à Administração Pública;"),
        ("II",  "Pagamento de multa eventualmente aplicada;"),
        ("III", "Transcurso do prazo mínimo de 1 (um) ano, no caso do Art. 156, III, "
                "ou de 3 (três) anos, no caso do Art. 156, IV;"),
        ("IV",  "Cumprimento das condições de reabilitação definidas no ato punitivo;"),
        ("V",   "Análise jurídica prévia, com posicionamento conclusivo quanto ao "
                "cumprimento dos requisitos."),
    ]
    for _n, _desc in _conds_legais:
        story.append(Paragraph(f"{_n}. {html.escape(_desc)}", _CORPO_REQ))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "A requerente demonstra o cumprimento das condições acima, conforme documentação "
        "comprobatória anexa e Relatório Técnico de Elegibilidade.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>III — DO PEDIDO</b>", _SECAO))
    story.append(Paragraph(
        f"Ante o exposto, requer seja deferida sua <b>REABILITAÇÃO</b> nos termos do "
        "Art. 163, Parágrafo Único, da Lei n.º 14.133/2021, com o consequente "
        "levantamento da restrição imposta.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph(
        f"_________________, _____ de _________________ de _______.", _CORPO_REQ
    ))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph(
        "________________________________________", _CORPO_REQ
    ))
    story.append(Paragraph(
        f"{_razao}", _CORPO_REQ
    ))
    story.append(Paragraph(
        f"CNPJ: {_cnpj_fmt}", _CORPO_REQ
    ))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Minuta gerada por IA-Licita - RM Vertice Digital. Revisar antes de protocolar.",
        _PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 3: Rodar todos os testes de `relatorio_reabilitacao`**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_relatorio_reabilitacao.py -v
```

Esperado: 7 PASSED

- [ ] **Step 4: Confirmar suite completa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: `241+ passed`

- [ ] **Step 5: Commit**

```bash
cd ~/Documents/Daysival && git add relatorio_reabilitacao.py && git commit -m "feat(reabilitacao): gerar_minuta_requerimento() com testes"
```

---

## Task 5: `app.py` — aba9 Reabilitação de Fornecedor

**Files:**
- Modify: `app.py` (linhas 7-33, 98-107, final do arquivo)

- [ ] **Step 1: Adicionar imports ao topo de `app.py`**

Localizar o bloco de imports que termina com:
```python
import ia_sancoes
import relatorio_sancoes
```

Substituir por:
```python
import ia_sancoes
import relatorio_sancoes
import ia_reabilitacao
import relatorio_reabilitacao
```

- [ ] **Step 2: Adicionar aba9 ao `st.tabs`**

Localizar (linha 98-107):
```python
aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
    "📝 Auditoria de TR",
    "⚖️ Dosimetria de Sanções",
])
```

Substituir por:
```python
aba1, aba2, aba3, aba4, aba5, aba6, aba7, aba8, aba9 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
    "⚖️ Alterações Contratuais",
    "📝 Auditoria de TR",
    "⚖️ Dosimetria de Sanções",
    "🔄 Reabilitação de Fornecedor",
])
```

- [ ] **Step 3: Verificar que o app ainda importa sem erro**

```bash
cd ~/Documents/Daysival && python3 -c "import app" 2>&1 | head -5
```

Esperado: sem saída (sem erros)

- [ ] **Step 4: Adicionar o bloco `with aba9:` ao final de `app.py`**

Adicionar após o bloco `with aba8:` existente (após a última linha do arquivo):

```python

with aba9:
    st.subheader("Reabilitação de Fornecedor")
    st.caption("Art. 163, Par. Único, Lei 14.133/2021")

    _api_key_reab = _get_api_key()
    _modelo_reab  = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    # ── Etapa 1: Identificação e Dados da Sanção ─────────────────────────────
    _col_reab1, _col_reab2 = st.columns(2)
    with _col_reab1:
        _cnpj_reab = st.text_input(
            "CNPJ do Fornecedor",
            placeholder="00.000.000/0000-00",
            key="reab_cnpj_input",
        )
    with _col_reab2:
        _tipo_sancao_opcoes = list(ia_reabilitacao.TIPOS_SANCAO.keys())
        _tipo_sancao_labels = list(ia_reabilitacao.TIPOS_SANCAO.values())
        _tipo_sancao_idx    = st.selectbox(
            "Tipo de Sanção",
            options=range(len(_tipo_sancao_opcoes)),
            format_func=lambda i: _tipo_sancao_labels[i],
            key="reab_tipo_sancao_select",
        )
    _tipo_sancao_reab = _tipo_sancao_opcoes[_tipo_sancao_idx]

    _col_reab3, _col_reab4 = st.columns(2)
    with _col_reab3:
        _data_sancao_reab = st.date_input(
            "Data de aplicação da sanção",
            value=None,
            key="reab_data_sancao",
        )
    with _col_reab4:
        _orgao_reab = st.text_input(
            "Órgão/Entidade sancionadora",
            placeholder="Ex.: Ministério da Gestão",
            key="reab_orgao",
        )

    _multa_aplicada_reab = st.radio(
        "Multa foi aplicada?",
        options=["Não", "Sim"],
        horizontal=True,
        key="reab_multa_aplicada",
    ) == "Sim"

    _multa_valor_reab = 0.0
    _multa_quitada_reab = False
    if _multa_aplicada_reab:
        _col_mv, _col_mq = st.columns(2)
        with _col_mv:
            _multa_valor_reab = st.number_input(
                "Valor da multa (R$)",
                min_value=0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
                key="reab_multa_valor",
            )
        with _col_mq:
            _multa_quitada_reab = st.radio(
                "Multa quitada?",
                options=["Não", "Sim"],
                horizontal=True,
                key="reab_multa_quitada",
            ) == "Sim"

    _conds_ato_reab = st.text_area(
        "Condições definidas no ato punitivo (Condição IV)",
        placeholder="Descreva as condições impostas pelo ato que aplicou a sanção...",
        key="reab_conds_ato",
    )

    if st.button(
        "Verificar Elegibilidade →",
        type="primary",
        key="btn_reab_etapa1",
        disabled=not _cnpj_reab,
    ):
        for _k in ("reab_etapa", "reab_dados_empresa", "reab_prazo",
                   "reab_dados_sancao", "reab_respostas", "reab_parecer",
                   "reab_pdf_tecnico", "reab_pdf_requerimento"):
            st.session_state.pop(_k, None)
        try:
            with st.spinner("Consultando CEIS/CNEP..."):
                _dados_empresa_reab = ddi_consultas.consultar(_cnpj_reab, 0.0)
            _dados_sancao_reab = {
                "tipo_sancao":            _tipo_sancao_reab,
                "data_aplicacao":         _data_sancao_reab,
                "orgao":                  _orgao_reab,
                "multa_aplicada":         _multa_aplicada_reab,
                "multa_valor":            _multa_valor_reab,
                "multa_quitada":          _multa_quitada_reab,
                "condicoes_ato_punitivo": _conds_ato_reab,
            }
            _prazo_reab = None
            if _data_sancao_reab:
                _prazo_reab = ia_reabilitacao.calcular_prazo(
                    _tipo_sancao_reab, _data_sancao_reab
                )
            st.session_state["reab_dados_empresa"] = _dados_empresa_reab
            st.session_state["reab_dados_sancao"]  = _dados_sancao_reab
            st.session_state["reab_prazo"]          = _prazo_reab
            st.session_state["reab_etapa"]          = 2
        except ValueError as _e:
            st.error(str(_e))
        except Exception as _e:
            st.error(f"Erro ao consultar: {_e}")

    # Resultado CEIS/CNEP (Etapa 1)
    if st.session_state.get("reab_etapa", 0) >= 2:
        _de_reab = st.session_state["reab_dados_empresa"]
        _ds_reab = st.session_state["reab_dados_sancao"]
        _pr_reab = st.session_state.get("reab_prazo")

        st.divider()
        st.markdown(
            f"**Empresa:** {_safe_md(_de_reab.get('razao_social') or '-')} &nbsp;|&nbsp; "
            f"**CNPJ:** {_safe_md(_de_reab.get('cnpj') or '-')} &nbsp;|&nbsp; "
            f"**Situação:** {_safe_md(_de_reab.get('situacao') or '-')}"
        )

        _ceis_reab = _de_reab.get("ceis") or []
        _cnep_reab = _de_reab.get("cnep") or []
        if _ceis_reab:
            with st.expander(f"CEIS — {len(_ceis_reab)} registro(s)"):
                for _r in _ceis_reab:
                    st.write(
                        f"• **{_safe_md(_r.get('orgaoSancionador',''))}** — "
                        f"{_safe_md(_r.get('fundamentacaoLegal',''))} — "
                        f"Situação: {_safe_md(_r.get('situacaoAtual',''))}"
                    )
        else:
            st.info("Nenhum registro encontrado no CEIS para este CNPJ.")

        if _cnep_reab:
            with st.expander(f"CNEP — {len(_cnep_reab)} registro(s)"):
                for _r in _cnep_reab:
                    st.write(
                        f"• **{_safe_md(_r.get('orgaoSancionador',''))}** — "
                        f"{_safe_md(_r.get('tipoPenalidade',''))} — "
                        f"Situação: {_safe_md(_r.get('situacaoAtual',''))}"
                    )

        # ── Etapa 2: Questionário ──────────────────────────────────────────
        st.divider()
        st.markdown("### Etapa 2 — Avaliação das Condições (Art. 163, Par. Único)")

        if _pr_reab:
            if _pr_reab["atendido"]:
                st.success(
                    f"✅ **Condição III — Prazo mínimo: Decorrido** — "
                    f"{_pr_reab['anos_decorridos']}a {_pr_reab['meses_decorridos']}m "
                    f"(mínimo: {_pr_reab['prazo_minimo_anos']} ano(s))"
                )
            else:
                st.error(
                    f"❌ **Condição III — Prazo mínimo: NÃO decorrido** — "
                    f"Decorrido: {_pr_reab['anos_decorridos']}a {_pr_reab['meses_decorridos']}m. "
                    f"Mínimo exigido: {_pr_reab['prazo_minimo_anos']} ano(s). "
                    "Reabilitação ainda não é possível."
                )
        else:
            st.warning("Data de aplicação não informada — prazo não calculado.")

        _reparacao_reab = st.radio(
            "Condição I — Reparação integral do dano à Administração:",
            options=["Sim (integral)", "Parcial", "Não", "N.A. (sem dano apurado)"],
            horizontal=True,
            key="reab_reparacao",
        )
        _reparacao_desc_reab = st.text_input(
            "Descrição/comprovação da reparação:",
            placeholder="Ex.: ressarcimento comprovado via depósito identificado",
            key="reab_reparacao_desc",
        )
        _cond_ato_cumpridas_reab = st.radio(
            "Condição IV — Condições do ato punitivo foram cumpridas?",
            options=["Sim", "Parcial", "Não", "N.A. (sem condições no ato)"],
            horizontal=True,
            key="reab_cond_ato_cumpridas",
        )
        _analise_juridica_reab = st.radio(
            "Condição V — Análise jurídica prévia:",
            options=["Realizada", "Em andamento", "Não realizada"],
            horizontal=True,
            key="reab_analise_juridica",
        )

        _arqs_reab = st.file_uploader(
            "Documentos comprobatórios (opcional — PDF/DOCX)",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="reab_docs",
        )

        if st.button(
            "Analisar Elegibilidade →",
            type="primary",
            key="btn_reab_etapa2",
        ):
            if not _api_key_reab:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            else:
                try:
                    _texto_reab = None
                    _avisos_reab = []
                    if _arqs_reab:
                        with st.spinner("Extraindo documentos..."):
                            _texto_reab, _avisos_reab = etp_extrator.extrair_texto(_arqs_reab)
                    for _av in _avisos_reab:
                        st.warning(_safe_md(_av))

                    _respostas_reab = {
                        "reparacao":           _reparacao_reab,
                        "reparacao_descricao": _reparacao_desc_reab,
                        "cond_ato_cumpridas":  _cond_ato_cumpridas_reab,
                        "analise_juridica":    _analise_juridica_reab,
                    }
                    with st.spinner("Analisando elegibilidade com IA..."):
                        _parecer_reab = ia_reabilitacao.analisar(
                            _ds_reab["tipo_sancao"],
                            _de_reab,
                            _ds_reab,
                            _respostas_reab,
                            _texto_reab,
                            _api_key_reab,
                            _modelo_reab,
                        )
                    st.session_state["reab_respostas"]  = _respostas_reab
                    st.session_state["reab_parecer"]    = _parecer_reab
                    st.session_state["reab_etapa"]      = 3

                    try:
                        st.session_state["reab_pdf_tecnico"] = (
                            relatorio_reabilitacao.gerar_relatorio_tecnico(
                                _de_reab["cnpj"], _de_reab, _ds_reab, _parecer_reab
                            )
                        )
                    except Exception as _e_pdf:
                        st.session_state.pop("reab_pdf_tecnico", None)
                        st.warning(f"Relatório técnico indisponível: {_e_pdf}")

                    try:
                        st.session_state["reab_pdf_requerimento"] = (
                            relatorio_reabilitacao.gerar_minuta_requerimento(
                                _de_reab["cnpj"], _de_reab, _ds_reab, _parecer_reab
                            )
                        )
                    except Exception as _e_pdf:
                        st.session_state.pop("reab_pdf_requerimento", None)
                        st.warning(f"Minuta do requerimento indisponível: {_e_pdf}")

                except (ValueError, RuntimeError) as _e:
                    st.error(str(_e))

    # ── Etapa 3: Resultado ────────────────────────────────────────────────────
    if st.session_state.get("reab_etapa", 0) >= 3:
        _pr3_reab = st.session_state.get("reab_parecer") or {}
        if not _pr3_reab:
            st.error("Resultado não encontrado. Por favor, refaça a análise.")
            st.stop()

        st.divider()
        st.markdown("### Resultado da Análise de Elegibilidade")

        _pval_reab = str(_pr3_reab.get("parecer") or "INELEGÍVEL").strip().upper()
        _icone_reab = {
            "ELEGÍVEL":               "🟢",
            "ELEGÍVEL COM RESSALVAS": "🟡",
            "INELEGÍVEL":             "🔴",
        }
        st.subheader(f"{_icone_reab.get(_pval_reab, '⚪')} {_safe_md(_pval_reab)}")

        _conds_reab = _pr3_reab.get("condicoes_avaliadas") or []
        _ic_st_reab = {"ATENDIDA": "✅", "PARCIAL": "⚠️", "AUSENTE": "❌", "N.A.": "—"}
        for _c in _conds_reab:
            if not _c:
                continue
            _st_c = str(_c.get("status") or "AUSENTE").strip().upper()
            _ic_c = _ic_st_reab.get(_st_c, "ℹ️")
            with st.expander(
                f"{_ic_c} Condição {_safe_md(_c.get('numero','?'))}: "
                f"{_safe_md(_c.get('descricao',''))}"
            ):
                st.write(_safe_md(_c.get("observacao") or "—"))

        if _pr3_reab.get("sintese"):
            st.info(_safe_md(_pr3_reab["sintese"]))

        with st.expander("Base Legal"):
            for _bl in (_pr3_reab.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_safe_md(_bl)}")

        _col_dl1, _col_dl2 = st.columns(2)
        with _col_dl1:
            if "reab_pdf_tecnico" in st.session_state:
                st.download_button(
                    label="⬇ Relatório Técnico (PDF)",
                    data=st.session_state["reab_pdf_tecnico"],
                    file_name="reabilitacao_relatorio_tecnico.pdf",
                    mime="application/pdf",
                    key="reab_dl_tecnico",
                )
        with _col_dl2:
            if "reab_pdf_requerimento" in st.session_state:
                st.download_button(
                    label="⬇ Minuta do Requerimento (PDF)",
                    data=st.session_state["reab_pdf_requerimento"],
                    file_name="reabilitacao_minuta_requerimento.pdf",
                    mime="application/pdf",
                    key="reab_dl_requerimento",
                )
```

- [ ] **Step 5: Verificar importação sem erros**

```bash
cd ~/Documents/Daysival && python3 -c "import app" 2>&1
```

Esperado: sem saída

- [ ] **Step 6: Rodar suite completa**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/ -q 2>&1 | tail -5
```

Esperado: `241+ passed`

- [ ] **Step 7: Commit final**

```bash
cd ~/Documents/Daysival && git add app.py && git commit -m "feat(app): aba9 Reabilitação de Fornecedor — fluxo 3-etapas"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Todas as 5 seções do spec cobertas — constantes, calcular_prazo, analisar, gerar_relatorio_tecnico, gerar_minuta_requerimento, aba9
- [x] **Sem placeholders:** Código completo em cada step
- [x] **Consistência de tipos:** `calcular_prazo` recebe `date`, `analisar` recebe `str`+`dict`, retorna `dict` — consistente em todos os tasks
- [x] **Reuso correto:** `ddi_consultas.consultar()` chamado com `valor_contrato=0.0`; `etp_extrator.extrair_texto()` retorna `(str, list)` — ambos usados corretamente
- [x] **html.escape:** aplicado em todos os campos dinâmicos nos dois PDFs
- [x] **NORM_PARECER_REAB:** cobre "ELEGIVEL", "ELEGIVEL COM RESSALVAS", "INELEGIVEL"
- [x] **Guarda de prazo:** só executa quando `data_aplicacao` é instância de `date`; se for `None`, deixa IA avaliar
