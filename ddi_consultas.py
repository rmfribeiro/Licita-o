from __future__ import annotations

import re
import os
import requests
import streamlit as st

_TIMEOUT = 10
_GRANDE_VULTO_LIMITE = 239_000_000.0
_PRO_ETICA_URL = (
    "https://www.gov.br/cgu/pt-br/assuntos/etica-e-integridade"
    "/empresa-pro-etica/lista-das-empresas-pro-etica"
)


def _get_cgu_key() -> str | None:
    chave = os.environ.get("CGU_API_KEY")
    if chave:
        return chave
    try:
        return st.secrets.get("CGU_API_KEY")
    except Exception:
        return None


def _validar_cnpj(cnpj: str) -> bool:
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    d1 = 0 if soma % 11 < 2 else 11 - soma % 11
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    d2 = 0 if soma % 11 < 2 else 11 - soma % 11
    return int(cnpj[12]) == d1 and int(cnpj[13]) == d2


def _e_grande_vulto(valor: float) -> bool:
    return valor > _GRANDE_VULTO_LIMITE


def _buscar_receita(cnpj: str) -> dict | None:
    try:
        resp = requests.get(
            f"https://publica.cnpj.ws/cnpj/{cnpj}",
            timeout=_TIMEOUT,
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return None
        d = resp.json()
        return {
            "razao_social": d.get("razao_social", ""),
            "nome_fantasia": d.get("nome_fantasia", ""),
            "situacao": d.get("descricao_situacao_cadastral", ""),
            "porte": d.get("descricao_porte", ""),
            "cnae": d.get("cnae_fiscal_descricao", ""),
            "data_abertura": d.get("data_inicio_atividade", ""),
            "socios": [
                {"nome": s.get("nome_socio", ""), "cargo": s.get("cargo", "")}
                for s in d.get("qsa", [])
            ],
        }
    except requests.exceptions.RequestException:
        return None


def _buscar_ceis(cnpj: str) -> list:
    chave = _get_cgu_key()
    if not chave:
        return []
    try:
        resp = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/ceis",
            params={"cnpjSancionado": cnpj, "pagina": 1},
            headers={"chave-api": chave, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "nomeInfrator": r.get("nomeInfrator", ""),
                "orgaoSancionador": (r.get("orgaoSancionador") or {}).get("nome", ""),
                "dataInicioSancao": r.get("dataInicioSancao", ""),
                "dataFimSancao": r.get("dataFimSancao", ""),
                "situacaoAtual": r.get("situacaoAtual", ""),
                "fundamentacaoLegal": r.get("fundamentacaoLegal", ""),
            }
            for r in (resp.json() or [])
        ]
    except requests.exceptions.RequestException:
        return []


def _buscar_cnep(cnpj: str) -> list:
    chave = _get_cgu_key()
    if not chave:
        return []
    try:
        resp = requests.get(
            "https://api.portaldatransparencia.gov.br/api-de-dados/cnep",
            params={"cnpjSancionado": cnpj, "pagina": 1},
            headers={"chave-api": chave, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return [
            {
                "nomeInfrator": r.get("nomeInfrator", ""),
                "orgaoSancionador": (r.get("orgaoSancionador") or {}).get("nome", ""),
                "dataInicioSancao": r.get("dataInicioSancao", ""),
                "dataFimSancao": r.get("dataFimSancao"),
                "situacaoAtual": r.get("situacaoAtual", ""),
                "tipoPenalidade": r.get("tipoPenalidade", ""),
                "fundamentacaoLegal": r.get("fundamentacaoLegal", ""),
            }
            for r in (resp.json() or [])
        ]
    except requests.exceptions.RequestException:
        return []


def _verificar_pro_etica(cnpj: str) -> bool | None:
    cnpj_fmt = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    try:
        resp = requests.get(_PRO_ETICA_URL, timeout=_TIMEOUT)
        if resp.status_code != 200:
            return None
        return cnpj_fmt in resp.text or cnpj in resp.text
    except requests.exceptions.RequestException:
        return None


def consultar(cnpj: str, valor_contrato: float) -> dict:
    pass
