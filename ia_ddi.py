from __future__ import annotations
import logging
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

    if dados.get("grande_vulto") is True:
        tem_pi = dados.get("pro_etica") or (
            fid is not None and sum(1 for v in fid.values() if v == "Sim") >= 3
        )
        if not tem_pi:
            piso = _risco_max(piso, "MÉDIO")

    return piso


def _risco_por_dimensoes(parecer: dict) -> str | None:
    """Deriva o risco geral DOS STATUS das dimensões, por regra fixa.

    O `_aplicar_piso` protege contra SUBESTIMAÇÃO (a IA não pode dizer risco
    menor do que os dados comprovam), mas nada impedia a IA de escolher
    livremente um risco ACIMA do piso — e escolher diferente a cada execução.
    Foi o defeito medido no ETP em 13/08/2026: mesmo documento, conclusões
    opostas. Aqui o risco passa a ser consequência das dimensões avaliadas.

      alguma dimensão crítica  -> ALTO
      alguma dimensão alerta   -> MÉDIO
      todas ok                 -> SEM RISCO IDENTIFICADO

    O piso continua valendo por cima: o risco final é o MAIOR dos dois.
    """
    dims = parecer.get("dimensoes")
    if not isinstance(dims, dict) or not dims:
        return None
    status = []
    for v in dims.values():
        if isinstance(v, dict) and v.get("status"):
            status.append(str(v["status"]).strip().lower())
    if not status:
        return None
    if any(s in ("critico", "crítico") for s in status):
        return "ALTO"
    if any(s == "alerta" for s in status):
        return "MÉDIO"
    return "SEM RISCO IDENTIFICADO"


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

    # As bases CEIS/CNEP so foram efetivamente consultadas se havia chave da
    # CGU. Sem isso, listas vazias significam "nao consultei", e NAO "empresa
    # sem sancoes" — atestar idoneidade sem verificacao e o erro mais grave
    # que este modulo pode cometer (visto em 29/07/2026: dimensao "Sancoes e
    # Punicoes" saiu como [OK] com descricao vazia, sem nenhuma consulta).
    _consultou_sancoes = bool(dados.get("ceis_disponivel"))
    _aviso_sancoes = "" if _consultou_sancoes else (
        "\nATENÇÃO: as bases CEIS e CNEP NÃO foram consultadas nesta análise "
        "(chave da API da CGU ausente ou indisponível). É PROIBIDO afirmar que "
        "a empresa não possui sanções ou marcar a dimensão 'sancoes' como "
        "'ok'. Use status 'alerta' e descreva que a verificação de sanções "
        "está PENDENTE, recomendando consulta manual em "
        "portaldatransparencia.gov.br/sancoes antes de qualquer contratação.\n"
    )

    prompt = (
        f"Dados do licitante:\n{json.dumps(dados, ensure_ascii=False, indent=2)}\n"
        f"{_aviso_sancoes}\n"
        f"Respostas do FID:\n"
        f"- Código de Ética ou Conduta formal: {fid.get('q1', 'Não sei')}\n"
        f"- Canal de denúncias ativo: {fid.get('q2', 'Não sei')}\n"
        f"- Treinamentos periódicos de integridade: {fid.get('q3', 'Não sei')}\n"
        f"- Política de conflito de interesses: {fid.get('q4', 'Não sei')}\n"
        f"- Auditorias internas ou externas: {fid.get('q5', 'Não sei')}\n\n"
        f"Retorne o parecer no formato:\n{_ESTRUTURA_PARECER}"
    )

    try:
        bruto = _chamar_anthropic(prompt, api_key, _get_modelo(), _SISTEMA, max_tokens=6000)
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
    parecer.pop("_aviso_risco", None)
    parecer.pop("_aviso_piso_risco", None)
    parecer.pop("_risco_ia", None)
    _raw_risco = parecer.get("risco_geral")
    _risco = "SEM RISCO IDENTIFICADO" if _raw_risco is None else str(_raw_risco).strip().upper()
    _risco = {
        "MEDIO":     "MÉDIO",
        "SEM RISCO": "SEM RISCO IDENTIFICADO",
    }.get(_risco, _risco)
    _aviso_risco_val = None
    if _risco not in _RISCO_ORDEM:
        logging.warning("ia_ddi: risco_geral desconhecido %r → usando 'SEM RISCO IDENTIFICADO'", _risco)
        _aviso_risco_val = _risco
        _risco = "SEM RISCO IDENTIFICADO"
    parecer["risco_geral"] = _risco

    _risco_antes_piso = _risco

    # Trava do CEIS/CNEP ANTES do calculo do risco: sem consulta as bases, a
    # dimensao de sancoes vira "alerta" — e essa mudanca precisa entrar na conta
    # do risco derivado, senao o parecer diria "sem risco identificado" tendo
    # uma verificacao pendente logo abaixo.
    if not _consultou_sancoes:
        _dims = parecer.get("dimensoes")
        if isinstance(_dims, dict):
            _s = _dims.get("sancoes")
            if not isinstance(_s, dict):
                _s = {}
            _s["status"] = "alerta"
            _s["descricao"] = (
                "VERIFICAÇÃO PENDENTE: as bases CEIS e CNEP não foram "
                "consultadas (chave da API da CGU não configurada). A ausência "
                "de sanções NÃO foi confirmada. Consulte manualmente em "
                "portaldatransparencia.gov.br/sancoes antes de contratar."
            )
            _s.setdefault("achados", [])
            _dims["sancoes"] = _s
        parecer["sancoes_verificadas"] = False

    # Risco final = o MAIOR entre o piso (dados) e o derivado (dimensoes).
    # Nenhum dos dois vem do juizo livre do modelo.
    _derivado = _risco_por_dimensoes(parecer)
    if _derivado and _RISCO_ORDEM.index(_derivado) != _RISCO_ORDEM.index(_risco):
        parecer["_risco_ia"] = _risco
        _risco = _derivado
        parecer["risco_geral"] = _risco

    if _RISCO_ORDEM.index(piso) > _RISCO_ORDEM.index(_risco):
        parecer["risco_geral"] = piso
        if _aviso_risco_val is None:
            parecer["_aviso_piso_risco"] = _risco_antes_piso

    if _aviso_risco_val is not None:
        parecer["_aviso_risco"] = _aviso_risco_val

    return parecer
