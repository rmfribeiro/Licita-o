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
    pass


def _buscar_ceis(cnpj: str) -> list:
    pass


def _buscar_cnep(cnpj: str) -> list:
    pass


def _verificar_pro_etica(cnpj: str) -> bool | None:
    pass


def consultar(cnpj: str, valor_contrato: float) -> dict:
    pass
