from __future__ import annotations
import json
import re
import urllib.request
import urllib.error
from ia_utils import extrair_json as _extrair_json

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_ADEQ_VALIDOS = {"ADEQUADO", "ADEQUADO COM RESSALVAS", "INADEQUADO"}

_SISTEMA = (
    "Você é um auditor especialista em contratações públicas federais brasileiras. "
    "Analise o Estudo Técnico Preliminar (ETP) fornecido à luz da IN SEGES/MGI 58/2022 "
    "e do art. 18 da Lei 14.133/2021. Avalie cada uma das 8 dimensões obrigatórias do ETP. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)

_ESTRUTURA_PARECER = """{
  "adequacao_geral": "ADEQUADO | ADEQUADO COM RESSALVAS | INADEQUADO",
  "dimensoes": {
    "descricao_necessidade":       {"status": "ok|alerta|critico", "descricao": "..."},
    "alinhamento_estrategico":     {"status": "ok|alerta|critico", "descricao": "..."},
    "requisitos_contratacao":      {"status": "ok|alerta|critico", "descricao": "..."},
    "levantamento_mercado":        {"status": "ok|alerta|critico", "descricao": "..."},
    "estimativa_quantidade_valor": {"status": "ok|alerta|critico", "descricao": "..."},
    "sustentabilidade":            {"status": "ok|alerta|critico", "descricao": "..."},
    "parcelamento":                {"status": "ok|alerta|critico", "descricao": "..."},
    "posicionamento_conclusivo":   {"status": "ok|alerta|critico", "descricao": "..."}
  },
  "pontos_criticos": ["..."],
  "recomendacoes": ["..."],
  "base_legal": ["IN SEGES/MGI 58/2022", "Lei 14.133/2021, art. 18, I"]
}"""


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


def analisar_etp(texto: str, api_key: str, modelo: str = _MODELO_PADRAO) -> dict:
    prompt = (
        f"Analise o seguinte Estudo Técnico Preliminar (ETP) e documentos complementares:\n\n"
        f"{texto}\n\n"
        f"Retorne o parecer de auditoria no formato:\n{_ESTRUTURA_PARECER}"
    )
    try:
        bruto = _chamar_anthropic(prompt, api_key, modelo)
        parecer = _extrair_json(bruto)
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc
    except Exception as exc:
        raise RuntimeError(f"Resposta inesperada da API: {exc}") from exc

    if not isinstance(parecer, dict):
        raise RuntimeError(f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(parecer).__name__}")
    _adeq = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    parecer["adequacao_geral"] = _adeq if _adeq in _ADEQ_VALIDOS else "INADEQUADO"
    return parecer
