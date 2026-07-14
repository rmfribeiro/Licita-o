# Módulo 3 — Avaliação de PI (Decreto 12.304/2024) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Criar Tab 5 no app.py para que gestores públicos avaliem o Programa de Integridade de empresas licitantes/contratadas com base nos 17 parâmetros do Decreto 12.304/2024, gerando score de aderência + parecer qualitativo por IA + relatório PDF.

**Architecture:** `ia_pi_empresas.py` contém constantes, scoring determinístico local e chamada à API Anthropic para análise qualitativa. `relatorio_pi_empresas.py` gera o PDF com ReportLab. `app.py` ganha Tab 5 com fluxo de 3 etapas via `st.session_state` (identificação → questionário → resultado), reutilizando `ddi_consultas.consultar()` para buscar dados da Receita Federal e `etp_extrator.extrair_texto()` para documentos opcionais.

**Tech Stack:** Python 3.9+, Streamlit, Anthropic API via `urllib` (sem SDK), ReportLab para PDF, pytest + unittest.mock para testes.

**Spec:** `docs/superpowers/specs/2026-06-05-modulo3-pi-empresas-design.md`

---

## Estrutura de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `ia_pi_empresas.py` | Criar | Constantes (17 parâmetros, 5 dimensões, 3 hipóteses, pesos), scoring local, chamada IA, `avaliar()` |
| `relatorio_pi_empresas.py` | Criar | Geração de PDF com ReportLab |
| `tests/test_ia_pi_empresas.py` | Criar | Testes de scoring, maturidade, `avaliar()` com mock |
| `tests/test_relatorio_pi_empresas.py` | Criar | Smoke test do PDF |
| `app.py` | Modificar | Adiciona Tab 5 (linhas 69 e ~530) |

---

## Task 1: `ia_pi_empresas.py` — Constantes e Scoring Local

**Files:**
- Create: `ia_pi_empresas.py`
- Create: `tests/test_ia_pi_empresas.py`

### Objetivo
Implementar as constantes (17 parâmetros, 5 dimensões, 3 hipóteses, pesos) e as duas funções de scoring local: `nivel_maturidade(score)` e `calcular_scores(respostas)`. Sem chamada IA ainda.

---

- [ ] **Step 1: Escrever os testes que devem falhar**

Crie `tests/test_ia_pi_empresas.py`:

```python
from __future__ import annotations
import pytest
import ia_pi_empresas


class TestNivelMaturidade:
    def test_score_0_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(0) == "INEXISTENTE"

    def test_score_24_retorna_inexistente(self):
        assert ia_pi_empresas.nivel_maturidade(24) == "INEXISTENTE"

    def test_score_25_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(25) == "INICIAL"

    def test_score_49_retorna_inicial(self):
        assert ia_pi_empresas.nivel_maturidade(49) == "INICIAL"

    def test_score_50_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(50) == "EM DESENVOLVIMENTO"

    def test_score_74_retorna_em_desenvolvimento(self):
        assert ia_pi_empresas.nivel_maturidade(74) == "EM DESENVOLVIMENTO"

    def test_score_75_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(75) == "CONSOLIDADO"

    def test_score_100_retorna_consolidado(self):
        assert ia_pi_empresas.nivel_maturidade(100) == "CONSOLIDADO"


def _respostas_todos_implementados() -> dict:
    return {p: "Implementado" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_nao_existem() -> dict:
    return {p: "Não existe" for p in ia_pi_empresas.QUESTOES_PI}


def _respostas_todos_parcialmente() -> dict:
    return {p: "Parcialmente" for p in ia_pi_empresas.QUESTOES_PI}


class TestCalcularScores:
    def test_todos_implementados_score_geral_100(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 100.0

    def test_todos_nao_existem_score_geral_0(self):
        r = _respostas_todos_nao_existem()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_todos_parcialmente_score_geral_50(self):
        r = _respostas_todos_parcialmente()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 50.0

    def test_retorna_por_parametro_com_17_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_parametro"]) == 17

    def test_retorna_por_dimensao_com_5_chaves(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert len(s["por_dimensao"]) == 5

    def test_nivel_derivado_do_score(self):
        r = _respostas_todos_implementados()
        s = ia_pi_empresas.calcular_scores(r)
        assert s["nivel"] == "CONSOLIDADO"

    def test_resposta_ausente_conta_como_nao_existe(self):
        r = {}  # nenhuma resposta
        s = ia_pi_empresas.calcular_scores(r)
        assert s["geral"] == 0.0

    def test_score_por_dimensao_media_simples_dos_parametros(self):
        # Comprometimento (p1, p2, p3): p1=100, p2=0, p3=0 → media=33.3
        r = _respostas_todos_nao_existem()
        r["p1"] = "Implementado"
        s = ia_pi_empresas.calcular_scores(r)
        assert abs(s["por_dimensao"]["comprometimento_alta_direcao"] - (100 / 3)) < 0.1

    def test_pesos_somam_1(self):
        total = sum(ia_pi_empresas.PESOS_DIMENSAO.values())
        assert abs(total - 1.0) < 1e-9
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd ~/Documents/Daysival && python3 -m pytest tests/test_ia_pi_empresas.py -v 2>&1 | head -20
```
Esperado: `ModuleNotFoundError: No module named 'ia_pi_empresas'`

- [ ] **Step 3: Criar `ia_pi_empresas.py` com constantes e scoring**

Crie `~/Documents/Daysival/ia_pi_empresas.py`:

```python
from __future__ import annotations
import json
import types
import urllib.request
import urllib.error
import logging
from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"

DIMENSOES_PI: types.MappingProxyType[str, tuple[str, tuple[str, ...]]] = types.MappingProxyType({
    "comprometimento_alta_direcao": (
        "Comprometimento da Alta Direção",
        ("p1", "p2", "p3"),
    ),
    "analise_riscos": (
        "Análise de Riscos",
        ("p4", "p5"),
    ),
    "estrutura_controles": (
        "Estrutura de Controles",
        ("p6", "p7", "p8", "p9", "p10", "p11", "p12"),
    ),
    "monitoramento_melhoria": (
        "Monitoramento e Melhoria Contínua",
        ("p13", "p14", "p15"),
    ),
    "transparencia": (
        "Transparência e Comunicação",
        ("p16", "p17"),
    ),
})

QUESTOES_PI: types.MappingProxyType[str, str] = types.MappingProxyType({
    "p1":  "Política formal de integridade aprovada e publicada pela alta direção",
    "p2":  "Responsável formalmente designado com autonomia e recursos adequados",
    "p3":  "Programa incluído no planejamento estratégico e orçamento da empresa",
    "p4":  "Mapeamento e análise periódica de riscos de integridade",
    "p5":  "Procedimentos internos adaptados ao perfil de risco da empresa",
    "p6":  "Código de ética ou conduta formal",
    "p7":  "Canal de denúncias ativo, acessível, com garantia de anonimato",
    "p8":  "Política de conflito de interesses",
    "p9":  "Treinamentos periódicos de integridade para colaboradores",
    "p10": "Due diligence de terceiros (fornecedores, parceiros, agentes)",
    "p11": "Controles sobre doações, patrocínios, brindes e hospitalidade",
    "p12": "Procedimentos de integridade em interações com o setor público",
    "p13": "Auditorias internas ou externas periódicas do programa",
    "p14": "Indicadores (KPIs) de efetividade do programa",
    "p15": "Investigações internas e ações corretivas aplicadas",
    "p16": "Registros contábeis e financeiros íntegros e auditáveis",
    "p17": "Relatório periódico do programa publicado ou disponível para consulta",
})

HIPOTESES: types.MappingProxyType[str, str] = types.MappingProxyType({
    "grande_vulto": "Grande Vulto (Decreto 12.304/2024, Art. 4º)",
    "desempate":    "Desempate por PI (Lei 14.133/2021, Art. 60, IV)",
    "reabilitacao": "Reabilitação de Fornecedor (Lei 14.133/2021, Art. 163, Par. Único)",
})

PESOS_DIMENSAO: types.MappingProxyType[str, float] = types.MappingProxyType({
    "comprometimento_alta_direcao": 0.20,
    "analise_riscos":               0.15,
    "estrutura_controles":          0.35,
    "monitoramento_melhoria":       0.20,
    "transparencia":                0.10,
})

_VALORES_RESPOSTA: types.MappingProxyType[str, int] = types.MappingProxyType({
    "Não existe":  0,
    "Parcialmente": 50,
    "Implementado": 100,
})

_MATURIDADE_FAIXAS: tuple[tuple[float, str], ...] = (
    (75.0, "CONSOLIDADO"),
    (50.0, "EM DESENVOLVIMENTO"),
    (25.0, "INICIAL"),
    (0.0,  "INEXISTENTE"),
)


def nivel_maturidade(score: float) -> str:
    for limite, nivel in _MATURIDADE_FAIXAS:
        if score >= limite:
            return nivel
    return "INEXISTENTE"


def calcular_scores(respostas: dict) -> dict:
    por_parametro: dict[str, int] = {}
    for p in QUESTOES_PI:
        resp = str(respostas.get(p) or "Não existe")
        por_parametro[p] = _VALORES_RESPOSTA.get(resp, 0)

    por_dimensao: dict[str, float] = {}
    for dim_key, (_, params) in DIMENSOES_PI.items():
        scores_dim = [por_parametro[p] for p in params]
        por_dimensao[dim_key] = sum(scores_dim) / len(scores_dim)

    geral = sum(por_dimensao[d] * PESOS_DIMENSAO[d] for d in por_dimensao)
    geral = round(geral, 1)

    return {
        "por_parametro": por_parametro,
        "por_dimensao":  por_dimensao,
        "geral":         geral,
        "nivel":         nivel_maturidade(geral),
    }
```

- [ ] **Step 4: Rodar para confirmar passagem**

```bash
python3 -m pytest tests/test_ia_pi_empresas.py -v
```
Esperado: todos os testes da Task 1 PASS (17 testes).

- [ ] **Step 5: Commit**

```bash
git add ia_pi_empresas.py tests/test_ia_pi_empresas.py
git commit -m "feat: ia_pi_empresas — constantes e scoring local (Task 1)"
```

---

## Task 2: `ia_pi_empresas.py` — Função `avaliar()` (chamada à IA)

**Files:**
- Modify: `ia_pi_empresas.py` (adiciona `_SISTEMA`, `_ESTRUTURA_PARECER`, `_chamar_anthropic`, `avaliar`)
- Modify: `tests/test_ia_pi_empresas.py` (adiciona testes de `avaliar`)

---

- [ ] **Step 1: Adicionar testes de `avaliar()` em `tests/test_ia_pi_empresas.py`**

Primeiro, adicione estas linhas no início do arquivo (após `import pytest`):

```python
import json
import urllib.error
from unittest.mock import patch, MagicMock
```

Em seguida, adicione ao **final** do arquivo:


def _qualitativo_mock() -> dict:
    return {
        "dimensoes": {
            "comprometimento_alta_direcao": {
                "sintese": "Alta direção comprometida.",
                "parametros": {
                    "p1": {"achados": ["Política publicada."], "recomendacoes": []},
                    "p2": {"achados": [], "recomendacoes": ["Designar CCO."]},
                    "p3": {"achados": [], "recomendacoes": []},
                },
            },
            "analise_riscos": {
                "sintese": "Mapeamento básico existente.",
                "parametros": {
                    "p4": {"achados": [], "recomendacoes": []},
                    "p5": {"achados": [], "recomendacoes": []},
                },
            },
            "estrutura_controles": {
                "sintese": "Controles parcialmente implantados.",
                "parametros": {
                    "p6": {"achados": [], "recomendacoes": []},
                    "p7": {"achados": [], "recomendacoes": []},
                    "p8": {"achados": [], "recomendacoes": []},
                    "p9": {"achados": [], "recomendacoes": []},
                    "p10": {"achados": [], "recomendacoes": []},
                    "p11": {"achados": [], "recomendacoes": []},
                    "p12": {"achados": [], "recomendacoes": []},
                },
            },
            "monitoramento_melhoria": {
                "sintese": "Monitoramento inexistente.",
                "parametros": {
                    "p13": {"achados": [], "recomendacoes": []},
                    "p14": {"achados": [], "recomendacoes": []},
                    "p15": {"achados": [], "recomendacoes": []},
                },
            },
            "transparencia": {
                "sintese": "Transparência adequada.",
                "parametros": {
                    "p16": {"achados": [], "recomendacoes": []},
                    "p17": {"achados": [], "recomendacoes": []},
                },
            },
        },
        "pontos_criticos": ["Canal de denúncias sem garantia de anonimato."],
        "conclusao_hipotese": "Empresa apta para desempate por PI.",
        "recomendacoes": ["Formalizar orçamento do PI."],
        "base_legal": ["Decreto 12.304/2024, Art. 4º"],
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


class TestAvaliar:
    def test_retorna_dict_com_scores_e_qualitativo(self):
        respostas = _respostas_todos_implementados()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")
        assert "scores" in resultado
        assert "dimensoes" in resultado
        assert "conclusao_hipotese" in resultado

    def test_scores_calculados_localmente(self):
        respostas = _respostas_todos_implementados()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")
        assert resultado["scores"]["geral"] == 100.0

    def test_hipotese_gravada_no_resultado(self):
        respostas = _respostas_todos_nao_existem()
        with patch("urllib.request.urlopen", return_value=_mock_urlopen(_qualitativo_mock())):
            resultado = ia_pi_empresas.avaliar(respostas, "grande_vulto", None, "key_teste")
        assert resultado["hipotese"] == "grande_vulto"

    def test_http_error_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        http_err = urllib.error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=401, msg="Unauthorized", hdrs=None,
            fp=MagicMock(read=MagicMock(return_value=b'{"error":"invalid key"}')),
        )
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="HTTP 401"):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_invalida")

    def test_api_retorna_nao_dict_levanta_runtime_error(self):
        respostas = _respostas_todos_implementados()
        payload = json.dumps({"content": [{"text": "[1, 2, 3]"}]}).encode("utf-8")
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(
            return_value=MagicMock(read=MagicMock(return_value=payload))
        )
        mock_cm.__exit__ = MagicMock(return_value=False)
        with patch("urllib.request.urlopen", return_value=mock_cm):
            with pytest.raises(RuntimeError, match="objeto JSON esperado"):
                ia_pi_empresas.avaliar(respostas, "desempate", None, "key_teste")
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python3 -m pytest tests/test_ia_pi_empresas.py::TestAvaliar -v
```
Esperado: `AttributeError: module 'ia_pi_empresas' has no attribute 'avaliar'`

- [ ] **Step 3: Adicionar `_SISTEMA`, `_ESTRUTURA_PARECER`, `_chamar_anthropic` e `avaliar` em `ia_pi_empresas.py`**

Adicione ao final de `ia_pi_empresas.py` (após `calcular_scores`):

```python
_SISTEMA = (
    "Você é um consultor sênior especialista em Programas de Integridade para empresas "
    "privadas e organismos que contratam com a Administração Pública brasileira. "
    "Avalie o Programa de Integridade da empresa com base nas respostas do questionário "
    "e nos documentos fornecidos, à luz do Decreto 12.304/2024, da Lei 12.846/2013 "
    "(art. 7º, IV) e da Lei 14.133/2021. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "dimensoes": {
    "comprometimento_alta_direcao": {
      "sintese": "...",
      "parametros": {
        "p1": {"achados": ["..."], "recomendacoes": ["..."]},
        "p2": {"achados": [], "recomendacoes": []},
        "p3": {"achados": [], "recomendacoes": []}
      }
    },
    "analise_riscos": {
      "sintese": "...",
      "parametros": {
        "p4": {"achados": [], "recomendacoes": []},
        "p5": {"achados": [], "recomendacoes": []}
      }
    },
    "estrutura_controles": {
      "sintese": "...",
      "parametros": {
        "p6":  {"achados": [], "recomendacoes": []},
        "p7":  {"achados": [], "recomendacoes": []},
        "p8":  {"achados": [], "recomendacoes": []},
        "p9":  {"achados": [], "recomendacoes": []},
        "p10": {"achados": [], "recomendacoes": []},
        "p11": {"achados": [], "recomendacoes": []},
        "p12": {"achados": [], "recomendacoes": []}
      }
    },
    "monitoramento_melhoria": {
      "sintese": "...",
      "parametros": {
        "p13": {"achados": [], "recomendacoes": []},
        "p14": {"achados": [], "recomendacoes": []},
        "p15": {"achados": [], "recomendacoes": []}
      }
    },
    "transparencia": {
      "sintese": "...",
      "parametros": {
        "p16": {"achados": [], "recomendacoes": []},
        "p17": {"achados": [], "recomendacoes": []}
      }
    }
  },
  "pontos_criticos": ["..."],
  "conclusao_hipotese": "Texto específico para a hipótese.",
  "recomendacoes": ["..."],
  "base_legal": ["Decreto 12.304/2024, Art. 4º", "Lei 14.133/2021, Art. 60, IV"]
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
        dados = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in dados.get("content", []))


def avaliar(
    respostas: dict,
    hipotese: str,
    texto_docs: str | None,
    api_key: str,
    modelo: str = _MODELO_PADRAO,
) -> dict:
    scores = calcular_scores(respostas)

    partes = [
        f"Avaliação do Programa de Integridade — Hipótese: {HIPOTESES.get(hipotese, hipotese)}\n"
        f"Score geral calculado: {scores['geral']}/100 ({scores['nivel']})\n"
    ]
    for dim_key, (dim_label, params) in DIMENSOES_PI.items():
        partes.append(
            f"\n=== {dim_label} (score: {scores['por_dimensao'][dim_key]:.0f}/100) ==="
        )
        for p in params:
            valor = scores["por_parametro"][p]
            resp_txt = {0: "Não existe", 50: "Parcialmente", 100: "Implementado"}.get(valor, str(valor))
            partes.append(f"- {QUESTOES_PI[p]} → {resp_txt} ({valor}/100)")

    if texto_docs:
        partes.append(f"\nDocumentos fornecidos pela empresa:\n{texto_docs[:30000]}")

    partes.append(f"\nRetorne a análise qualitativa no formato:\n{_ESTRUTURA_PARECER}")

    try:
        bruto = _chamar_anthropic("\n".join(partes), api_key, modelo)
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
            f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(qualitativo).__name__}"
        )

    return {
        "scores":  scores,
        "hipotese": hipotese,
        **qualitativo,
    }
```

- [ ] **Step 4: Rodar toda a suite de testes de ia_pi_empresas**

```bash
python3 -m pytest tests/test_ia_pi_empresas.py -v
```
Esperado: todos os testes PASS (22 testes).

- [ ] **Step 5: Rodar suite completa para confirmar sem regressão**

```bash
python3 -m pytest tests/ -q
```
Esperado: 109 passed (87 existentes + 22 novos).

- [ ] **Step 6: Commit**

```bash
git add ia_pi_empresas.py tests/test_ia_pi_empresas.py
git commit -m "feat: ia_pi_empresas — avaliar() com chamada Anthropic (Task 2)"
```

---

## Task 3: `relatorio_pi_empresas.py` — Geração de PDF

**Files:**
- Create: `relatorio_pi_empresas.py`
- Create: `tests/test_relatorio_pi_empresas.py`

---

- [ ] **Step 1: Escrever o teste de smoke do PDF**

Crie `tests/test_relatorio_pi_empresas.py`:

```python
from __future__ import annotations
import relatorio_pi_empresas


def _parecer_minimo() -> dict:
    return {
        "scores": {
            "por_parametro": {f"p{i}": 50 for i in range(1, 18)},
            "por_dimensao": {
                "comprometimento_alta_direcao": 50.0,
                "analise_riscos":               50.0,
                "estrutura_controles":          50.0,
                "monitoramento_melhoria":       50.0,
                "transparencia":               50.0,
            },
            "geral": 50.0,
            "nivel": "EM DESENVOLVIMENTO",
        },
        "hipotese": "grande_vulto",
        "dimensoes": {
            "comprometimento_alta_direcao": {
                "sintese": "Comprometimento parcial.",
                "parametros": {
                    "p1": {"achados": ["Política existe."], "recomendacoes": []},
                    "p2": {"achados": [], "recomendacoes": ["Designar CCO."]},
                    "p3": {"achados": [], "recomendacoes": []},
                },
            },
            "analise_riscos": {
                "sintese": "Riscos mapeados.",
                "parametros": {
                    "p4": {"achados": [], "recomendacoes": []},
                    "p5": {"achados": [], "recomendacoes": []},
                },
            },
            "estrutura_controles": {
                "sintese": "Controles presentes.",
                "parametros": {k: {"achados": [], "recomendacoes": []} for k in
                               ["p6", "p7", "p8", "p9", "p10", "p11", "p12"]},
            },
            "monitoramento_melhoria": {
                "sintese": "Monitoramento básico.",
                "parametros": {k: {"achados": [], "recomendacoes": []} for k in
                               ["p13", "p14", "p15"]},
            },
            "transparencia": {
                "sintese": "Transparência adequada.",
                "parametros": {
                    "p16": {"achados": [], "recomendacoes": []},
                    "p17": {"achados": [], "recomendacoes": []},
                },
            },
        },
        "pontos_criticos": ["Canal sem anonimato."],
        "conclusao_hipotese": "PI obrigatório. Score limítrofe.",
        "recomendacoes": ["Implantar KPIs."],
        "base_legal": ["Decreto 12.304/2024, Art. 4º"],
    }


class TestGerarPdf:
    def test_retorna_bytes_nao_vazios(self):
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="grande_vulto",
            parecer=_parecer_minimo(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_pdf_sem_pontos_criticos_nao_quebra(self):
        parecer = _parecer_minimo()
        parecer["pontos_criticos"] = []
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="desempate",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000

    def test_pdf_com_achados_nulos_nao_quebra(self):
        parecer = _parecer_minimo()
        parecer["dimensoes"]["comprometimento_alta_direcao"]["parametros"]["p1"]["achados"] = [None, "Válido"]
        pdf = relatorio_pi_empresas.gerar_pdf(
            cnpj="11222333000181",
            razao_social="EMPRESA TESTE LTDA",
            hipotese="reabilitacao",
            parecer=parecer,
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 1000
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
python3 -m pytest tests/test_relatorio_pi_empresas.py -v
```
Esperado: `ModuleNotFoundError: No module named 'relatorio_pi_empresas'`

- [ ] **Step 3: Criar `relatorio_pi_empresas.py`**

Crie `~/Documents/Daysival/relatorio_pi_empresas.py`:

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
from ia_integridade import COR_MATURIDADE_HEX as _COR_MATURIDADE_HEX
from ia_pi_empresas import DIMENSOES_PI, HIPOTESES, QUESTOES_PI

_COR_MATURIDADE = {k: colors.HexColor(v) for k, v in _COR_MATURIDADE_HEX.items()}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("pi_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1      = ParagraphStyle("pi_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2      = ParagraphStyle("pi_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("pi_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("pi_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE   = ParagraphStyle("pi_badge",   parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def gerar_pdf(cnpj: str, razao_social: str, hipotese: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Avaliação do Programa de Integridade (PI)", _ESTILO_H1))
    story.append(Paragraph("Decreto 12.304/2024 · Lei 14.133/2021 · Lei 12.846/2013", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação
    story.append(Paragraph("Identificação da Empresa", _ESTILO_H2))
    linhas_id = [
        ["Razão Social", html.escape(str(razao_social or "-"))],
        ["CNPJ", _fmt_cnpj(cnpj)],
        ["Hipótese Avaliada", html.escape(str(HIPOTESES.get(hipotese, hipotese)))],
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

    # Score geral + nível de maturidade
    scores = parecer.get("scores") or {}
    score_geral = scores.get("geral", 0.0)
    nivel = str(scores.get("nivel") or "INEXISTENTE").strip().upper()
    cor_nivel = _COR_MATURIDADE.get(nivel, colors.grey)

    story.append(Paragraph("Score Geral de Aderência", _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(
            f"<b>{html.escape(nivel)} — {score_geral:.0f}/100</b>",
            _ESTILO_BADGE,
        )]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_nivel),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    # Score por dimensão
    story.append(Paragraph("Score por Dimensão", _ESTILO_H2))
    por_dimensao = scores.get("por_dimensao") or {}
    linhas_dim = [["Dimensão", "Score"]]
    for dim_key, (dim_label, _) in DIMENSOES_PI.items():
        s = por_dimensao.get(dim_key, 0.0)
        linhas_dim.append([html.escape(dim_label), f"{s:.0f}/100"])
    t_dim = Table(linhas_dim, colWidths=[13*cm, 4*cm])
    t_dim.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(t_dim)
    story.append(Spacer(1, 0.4*cm))

    # Conclusão para a hipótese
    conclusao = str(parecer.get("conclusao_hipotese") or "-")
    story.append(Paragraph("Conclusão para a Hipótese", _ESTILO_H2))
    story.append(Paragraph(html.escape(conclusao), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos") or []
    if criticos:
        story.append(Paragraph("Pontos Críticos", _ESTILO_H2))
        for i, ponto in enumerate(criticos, 1):
            if ponto:
                story.append(Paragraph(f"{i}. {html.escape(str(ponto))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Análise por dimensão (achados e recomendações)
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    dims_qualitativo = parecer.get("dimensoes") or {}
    for dim_key, (dim_label, params) in DIMENSOES_PI.items():
        dim = dims_qualitativo.get(dim_key) or {}
        sintese = str(dim.get("sintese") or "-")
        score_d = por_dimensao.get(dim_key, 0.0)
        story.append(Paragraph(
            f"<b>{html.escape(dim_label)} ({score_d:.0f}/100):</b> {html.escape(sintese)}",
            _ESTILO_CORPO,
        ))
        params_qualit = dim.get("parametros") or {}
        for p in params:
            p_data = params_qualit.get(p) or {}
            rotulo = QUESTOES_PI.get(p, p)
            for achado in (p_data.get("achados") or []):
                if achado:
                    story.append(Paragraph(
                        f"  • {html.escape(rotulo)}: {html.escape(str(achado))}",
                        _ESTILO_CORPO,
                    ))
            for rec in (p_data.get("recomendacoes") or []):
                if rec:
                    story.append(Paragraph(
                        f"  → Recomendação: {html.escape(str(rec))}",
                        _ESTILO_CORPO,
                    ))
    story.append(Spacer(1, 0.3*cm))

    # Recomendações gerais
    recs = parecer.get("recomendacoes") or []
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if rec:
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
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
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 4: Rodar para confirmar passagem**

```bash
python3 -m pytest tests/test_relatorio_pi_empresas.py -v
```
Esperado: 3 testes PASS.

- [ ] **Step 5: Rodar suite completa**

```bash
python3 -m pytest tests/ -q
```
Esperado: 112 passed (109 + 3 novos).

- [ ] **Step 6: Commit**

```bash
git add relatorio_pi_empresas.py tests/test_relatorio_pi_empresas.py
git commit -m "feat: relatorio_pi_empresas — PDF com score por dimensão (Task 3)"
```

---

## Task 4: `app.py` — Tab 5 (Avaliação de PI)

**Files:**
- Modify: `app.py` (linha 69 para adicionar aba; final do arquivo para o conteúdo da aba)

O fluxo segue o mesmo padrão das abas DDI e PIP existentes: `session_state` com chave `pi_etapa` (1, 2, 3).

---

- [ ] **Step 1: Adicionar imports e expandir `st.tabs` em `app.py`**

Encontre a linha:
```python
import ia_integridade
import relatorio_integridade
```

Adicione após:
```python
import ia_pi_empresas
import relatorio_pi_empresas
```

Encontre:
```python
aba1, aba2, aba3, aba4 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
])
```

Substitua por:
```python
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📄 Auditoria de Edital",
    "🔍 Due Diligence de Integridade",
    "📋 Auditoria de ETP",
    "🏛️ Diagnóstico de Integridade",
    "🏢 Avaliação de PI",
])
```

- [ ] **Step 2: Verificar que o app carrega sem erro**

```bash
cd ~/Documents/Daysival && python3 -c "import app" 2>&1 | head -5
```
Esperado: nenhum erro (pode haver warnings do Streamlit, normal).

- [ ] **Step 3: Adicionar Tab 5 ao final de `app.py`**

Adicione ao final do arquivo (após o bloco `with aba4:`):

```python
with aba5:
    st.subheader("Avaliação do Programa de Integridade — Decreto 12.304/2024")
    st.caption(
        "Decreto 12.304/2024 · Lei 14.133/2021, arts. 60-IV e 163 · Lei 12.846/2013, art. 7º, IV"
    )

    _api_key_pi = os.environ.get("ANTHROPIC_API_KEY")
    if not _api_key_pi:
        try:
            _val = st.secrets.get("ANTHROPIC_API_KEY")
            if _val:
                _api_key_pi = str(_val)
        except _SecretsNotFound:
            pass
        except Exception as _e:
            st.warning(f"Erro ao ler configurações (secrets.toml): {_e}")
    _modelo_pi = os.environ.get("IA_LICITA_MODELO", "claude-haiku-4-5-20251001")

    # ── Etapa 1: Identificação ─────────────────────────────────────────────
    st.markdown("### Etapa 1 — Identificação da Empresa")
    _col_cnpj, _col_hip = st.columns([2, 3])
    _cnpj_pi = _col_cnpj.text_input("CNPJ da empresa", key="pi_cnpj_input",
                                     placeholder="00.000.000/0000-00")
    _hip_opcoes = {k: v for k, v in ia_pi_empresas.HIPOTESES.items()}
    _hip_chaves = list(_hip_opcoes.keys())
    _hip_labels = list(_hip_opcoes.values())
    _hip_idx = _col_hip.selectbox(
        "Hipótese legal",
        options=range(len(_hip_chaves)),
        format_func=lambda i: _hip_labels[i],
        key="pi_hipotese_select",
    )
    _hipotese_pi = _hip_chaves[_hip_idx]

    if st.button("Consultar empresa", key="btn_pi_etapa1", disabled=not _cnpj_pi):
        for _k in ("pi_etapa", "pi_dados", "pi_cnpj", "pi_hipotese",
                   "pi_respostas", "pi_parecer", "pi_pdf"):
            st.session_state.pop(_k, None)
        try:
            with st.spinner("Consultando Receita Federal..."):
                _dados_pi = ddi_consultas.consultar(_cnpj_pi, 0.0)
            st.session_state["pi_dados"] = _dados_pi
            st.session_state["pi_cnpj"] = _dados_pi["cnpj"]
            st.session_state["pi_hipotese"] = _hipotese_pi
            st.session_state["pi_etapa"] = 2
        except ValueError as _e:
            st.error(str(_e))
        except Exception as _e:
            st.error(f"Erro ao consultar empresa: {_e}")

    if st.session_state.get("pi_etapa", 0) >= 2:
        _d_pi = st.session_state["pi_dados"]
        _hip_pi = st.session_state["pi_hipotese"]
        st.success(f"**{_d_pi.get('razao_social') or 'Empresa'}** — "
                   f"CNPJ: {st.session_state['pi_cnpj']} — "
                   f"Situação: {_d_pi.get('situacao') or '-'} — "
                   f"Porte: {_d_pi.get('porte') or '-'}")
        if _hip_pi == "grande_vulto" and "GRANDE" not in str(_d_pi.get("porte") or "").upper():
            st.warning(
                "⚠️ PI obrigatório somente para contratos > R$ 239M (grande vulto). "
                "Confirme o enquadramento antes de prosseguir."
            )

        # ── Etapa 2: Questionário ──────────────────────────────────────────
        st.divider()
        st.markdown("### Etapa 2 — Questionário (17 parâmetros)")

        _respostas_pi = {}
        for _dim_key, (_dim_label, _params) in ia_pi_empresas.DIMENSOES_PI.items():
            with st.expander(f"**{_dim_label}** ({len(_params)} parâmetros)"):
                for _p in _params:
                    _rotulo_p = ia_pi_empresas.QUESTOES_PI[_p]
                    _respostas_pi[_p] = st.radio(
                        _rotulo_p,
                        options=["Não existe", "Parcialmente", "Implementado"],
                        key=f"pi_{_p}",
                        horizontal=True,
                    )

        _arqs_pi = st.file_uploader(
            "Documentos da empresa (opcional — PDF ou Word): regulamento interno, "
            "código de ética, relatório do PI, etc.",
            type=["pdf", "docx"],
            accept_multiple_files=True,
            key="pi_docs",
        )

        if st.button("Gerar Avaliação", type="primary", key="btn_pi_etapa2"):
            if not _api_key_pi:
                st.error(
                    "ANTHROPIC_API_KEY não configurada — "
                    "configure via variável de ambiente ou secrets.toml."
                )
            else:
                for _k in ("pi_respostas", "pi_parecer", "pi_pdf"):
                    st.session_state.pop(_k, None)
                try:
                    with st.spinner(
                        "Avaliando programa de integridade com IA (pode levar 1-2 minutos)..."
                    ):
                        _texto_pi, _ = (
                            etp_extrator.extrair_texto(_arqs_pi) if _arqs_pi else (None, [])
                        )
                        _parecer_pi = ia_pi_empresas.avaliar(
                            _respostas_pi,
                            st.session_state["pi_hipotese"],
                            _texto_pi,
                            _api_key_pi,
                            _modelo_pi,
                        )
                    st.session_state["pi_respostas"] = _respostas_pi
                    st.session_state["pi_parecer"] = _parecer_pi
                    st.session_state["pi_etapa"] = 3
                    _razao_pi = st.session_state["pi_dados"].get("razao_social") or ""
                    try:
                        st.session_state["pi_pdf"] = relatorio_pi_empresas.gerar_pdf(
                            cnpj=st.session_state["pi_cnpj"],
                            razao_social=_razao_pi,
                            hipotese=st.session_state["pi_hipotese"],
                            parecer=_parecer_pi,
                        )
                    except Exception as _pdf_e:
                        st.session_state.pop("pi_pdf", None)
                        st.warning(f"Não foi possível gerar o PDF: {_pdf_e}")
                except (ValueError, RuntimeError) as _e:
                    st.error(str(_e))

    # ── Etapa 3: Resultado ─────────────────────────────────────────────────
    if st.session_state.get("pi_etapa", 0) >= 3:
        _pr_pi = st.session_state["pi_parecer"]
        _sc_pi = _pr_pi.get("scores") or {}

        st.divider()
        st.markdown("### Resultado da Avaliação")

        _nivel_pi = str(_sc_pi.get("nivel") or "INEXISTENTE").strip().upper()
        _score_pi = _sc_pi.get("geral", 0.0)
        _cor_pi = ia_integridade.COR_MATURIDADE_HEX.get(_nivel_pi, "#888888")
        _icone_pi = ia_integridade.ICONE_MATURIDADE.get(_nivel_pi, "⚪")
        st.markdown(
            f"<div style='background:{_cor_pi};padding:16px;border-radius:8px;"
            f"color:white;font-size:20px;font-weight:bold;text-align:center'>"
            f"{_icone_pi} {_nivel_pi} — {_score_pi:.0f}/100"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("")

        # Scores por dimensão
        _por_dim = _sc_pi.get("por_dimensao") or {}
        st.markdown("**Score por Dimensão:**")
        for _dim_key, (_dim_label, _) in ia_pi_empresas.DIMENSOES_PI.items():
            _s = _por_dim.get(_dim_key, 0.0)
            st.write(f"• **{_dim_label}:** {_s:.0f}/100")

        # Conclusão para a hipótese
        _conc_pi = str(_pr_pi.get("conclusao_hipotese") or "")
        if _conc_pi:
            st.info(_conc_pi)

        # Pontos críticos
        _crit_pi = _pr_pi.get("pontos_criticos") or []
        if _crit_pi:
            st.markdown("**Pontos Críticos**")
            for _i, _c in enumerate(_crit_pi, 1):
                if _c:
                    st.error(f"{_i}. {_c}")

        # Análise por dimensão
        _dims_pi = _pr_pi.get("dimensoes") or {}
        for _dim_key, (_dim_label, _params_d) in ia_pi_empresas.DIMENSOES_PI.items():
            _dim_d = _dims_pi.get(_dim_key) or {}
            _sintese_d = str(_dim_d.get("sintese") or "-")
            _score_d = _por_dim.get(_dim_key, 0.0)
            with st.expander(f"**{_dim_label}** — {_score_d:.0f}/100"):
                st.write(_sintese_d)
                _params_q = _dim_d.get("parametros") or {}
                for _p in _params_d:
                    _pdata = _params_q.get(_p) or {}
                    for _ach in (_pdata.get("achados") or []):
                        if _ach:
                            st.warning(f"**{ia_pi_empresas.QUESTOES_PI[_p]}:** {_ach}")
                    for _rec in (_pdata.get("recomendacoes") or []):
                        if _rec:
                            st.info(f"→ {_rec}")

        # Recomendações gerais
        _recs_pi = _pr_pi.get("recomendacoes") or []
        if _recs_pi:
            with st.expander("**Recomendações ao Gestor**"):
                for _i, _r in enumerate(_recs_pi, 1):
                    if _r:
                        st.write(f"{_i}. {_r}")

        # Base legal
        with st.expander("Base Legal"):
            for _bl in (_pr_pi.get("base_legal") or []):
                if _bl:
                    st.write(f"• {_bl}")

        # Download PDF
        if "pi_pdf" in st.session_state:
            _razao_final = (st.session_state.get("pi_dados") or {}).get("razao_social") or "PI"
            _nome_pdf_pi = f"PI_{_razao_final.replace(' ', '_')[:30]}.pdf"
            st.download_button(
                label="⬇️ Baixar Relatório PDF",
                data=st.session_state["pi_pdf"],
                file_name=_nome_pdf_pi,
                mime="application/pdf",
            )
```

- [ ] **Step 4: Verificar que o módulo carrega sem erro de sintaxe**

```bash
cd ~/Documents/Daysival && python3 -c "
import ast, sys
with open('app.py') as f:
    src = f.read()
try:
    ast.parse(src)
    print('OK — sem erros de sintaxe')
except SyntaxError as e:
    print(f'SyntaxError: {e}')
    sys.exit(1)
"
```
Esperado: `OK — sem erros de sintaxe`

- [ ] **Step 5: Rodar suite completa para confirmar sem regressão**

```bash
python3 -m pytest tests/ -q
```
Esperado: 112 passed (nenhuma regressão).

- [ ] **Step 6: Commit**

```bash
git add app.py
git commit -m "feat: app.py — Tab 5 Avaliação de PI (Módulo 3, Decreto 12.304/2024)"
```

---

## Verificação Final

- [ ] **Checar que todos os 112 testes passam**

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

- [ ] **Confirmar que o app carrega e os 5 tabs são renderizados**

```bash
python3 -m streamlit run ~/Documents/Daysival/app.py &
sleep 5
curl -s http://localhost:8501 | grep -c "IA-Licita" && echo "App respondendo"
kill %1 2>/dev/null
```

- [ ] **Commit final se necessário**

```bash
git log --oneline -5
```
