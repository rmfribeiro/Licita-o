from __future__ import annotations
import os
import json
import urllib.error
import streamlit as st
from ia_utils import extrair_json as _extrair_json, chamar_anthropic as _chamar_anthropic

_MODELO_PADRAO = "claude-haiku-4-5-20251001"
_RISCO_ORDEM = ["SEM RISCO IDENTIFICADO", "BAIXO", "MÉDIO", "ALTO"]

_SISTEMA = (
    "Você é um analista sênior de integridade de fornecedores do governo federal brasileiro. "
    "Avalie o perfil de integridade do licitante com base nos dados fornecidos e nos seguintes "
    "instrumentos: Portaria SEGES/ME 8.678/2021 art. 2º III; Decreto 12.304/2024; "
    "Portaria Normativa SE/CGU 226/2025; Lei 14.133/2021 arts. 25 §4º, 60 IV, 156 §1º, 163; "
    "Lei 12.846/2013 e Decreto 8.420/2015. "
    "Responda SOMENTE com JSON válido no formato especificado. Não inclua texto fora do JSON."
)


def _get_api_key() -> str | None:
    chave = os.environ.get("ANTHROPIC_API_KEY")
    if chave:
        return chave
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None


def _get_modelo() -> str:
    return os.environ.get("IA_LICITA_MODELO", _MODELO_PADRAO)


def _risco_max(a: str, b: str) -> str:
    return a if _RISCO_ORDEM.index(a) >= _RISCO_ORDEM.index(b) else b


def _aplicar_piso(dados: dict, fid: dict | None = None) -> str:
    piso = "SEM RISCO IDENTIFICADO"

    if isinstance(dados.get("ceis"), list) and any(r.get("situacaoAtual") == "Ativo" for r in dados["ceis"]):
        piso = _risco_max(piso, "ALTO")

    if isinstance(dados.get("cnep"), list) and any(r.get("situacaoAtual") == "Ativo" for r in dados["cnep"]):
        piso = _risco_max(piso, "MÉDIO")

    if (dados.get("situacao") or "").upper() in ("SUSPENSA", "BAIXADA", "INAPTA"):
        piso = _risco_max(piso, "MÉDIO")

    if dados.get("grande_vulto"):
        tem_pi = dados.get("pro_etica") or (
            fid is not None and sum(1 for v in fid.values() if v == "Sim") >= 3
        )
        if not tem_pi:
            piso = _risco_max(piso, "MÉDIO")

    return piso


_ESTRUTURA_PARECER = """{
  "risco_geral": "ALTO|MÉDIO|BAIXO|SEM RISCO IDENTIFICADO",
  "dimensoes": {
    "situacao_cadastral": {"status": "ok|alerta|critico", "descricao": "..."},
    "sancoes": {"status": "ok|alerta|critico", "achados": [{"fonte": "...", "descricao": "...", "gravidade": "alta|media|baixa"}]},
    "programa_integridade": {"status": "ok|alerta|critico", "obrigatorio": true, "pro_etica": false, "descricao": "..."},
    "fid": {"status": "ok|alerta|critico", "inconsistencias": [], "descricao": "..."},
    "contexto_contrato": {"status": "ok|alerta|critico", "grande_vulto": false, "descricao": "..."}
  },
  "resumo": "frase direta",
  "recomendacao": "orientacao ao gestor",
  "base_legal": ["Portaria SEGES/ME 8.678/2021, art. 2 III"],
  "validade_fid": "12 meses a partir da data desta consulta"
}"""


def analisar(dados: dict, fid: dict) -> dict:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY ausente. Configure a chave para a análise DDI."
        )

    piso = _aplicar_piso(dados, fid)

    prompt = (
        f"Dados do licitante:\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n\n"
        f"Respostas do FID:\n"
        f"- Código de Ética ou Conduta formal: {fid.get('q1', 'Não sei')}\n"
        f"- Canal de denúncias ativo: {fid.get('q2', 'Não sei')}\n"
        f"- Treinamentos periódicos de integridade: {fid.get('q3', 'Não sei')}\n"
        f"- Política de conflito de interesses: {fid.get('q4', 'Não sei')}\n"
        f"- Auditorias internas ou externas: {fid.get('q5', 'Não sei')}\n\n"
        f"Retorne o parecer no formato:\n{_ESTRUTURA_PARECER}"
    )

    try:
        bruto = _chamar_anthropic(prompt, api_key, _get_modelo(), _SISTEMA, max_tokens=3000)
    except urllib.error.HTTPError as exc:
        _body = ""
        try:
            _body = exc.read().decode("utf-8", errors="replace")
        except (OSError, IOError):
            pass
        raise RuntimeError(f"Falha na API Anthropic: HTTP {exc.code} {exc.reason} — {_body}") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(f"Falha na API Anthropic: {exc}") from exc

    try:
        parecer = _extrair_json(bruto)
    except ValueError as exc:
        raise RuntimeError(f"Resposta da API não contém JSON válido: {exc}") from exc

    if not isinstance(parecer, dict):
        raise RuntimeError(f"Resposta inesperada da API: objeto JSON esperado, recebeu {type(parecer).__name__}")
    _risco = str(parecer.get("risco_geral") or "SEM RISCO IDENTIFICADO").strip().upper()
    _risco = {"MEDIO": "MÉDIO"}.get(_risco, _risco)
    parecer["risco_geral"] = _risco if _risco in _RISCO_ORDEM else "SEM RISCO IDENTIFICADO"

    if _RISCO_ORDEM.index(piso) > _RISCO_ORDEM.index(parecer["risco_geral"]):
        parecer["risco_geral"] = piso

    return parecer
