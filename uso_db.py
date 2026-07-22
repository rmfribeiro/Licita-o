# -*- coding: utf-8 -*-
"""
=============================================================================
 uso_db.py  -  RM IA-Licita / RM Vertice Digital
 Contador de relatorios gerados (base da cobranca por uso - Fase 2).
=============================================================================
 - registrar_uso(usuario, modulo): grava 1 relatorio na tabela
   uso_relatorios do Supabase, com nivel e valor de referencia da epoca
   (snapshot: se a tabela de precos mudar, o historico nao muda).
 - uso_do_mes / resumo_do_mes: consultas para o painel do usuario e a
   consolidacao de cobranca do administrador.
 Tabela: ver supabase_schema_ialicita.sql (uso_relatorios).
=============================================================================
"""
from __future__ import annotations

from datetime import datetime, timezone

import auth_db
import precos

TABELA_USO = "uso_relatorios"


def _limites_mes(ano: int | None = None, mes: int | None = None):
    agora = datetime.now(timezone.utc)
    ano = ano or agora.year
    mes = mes or agora.month
    ini = datetime(ano, mes, 1, tzinfo=timezone.utc)
    fim = (datetime(ano + 1, 1, 1, tzinfo=timezone.utc) if mes == 12
           else datetime(ano, mes + 1, 1, tzinfo=timezone.utc))
    return ini.isoformat(), fim.isoformat()


def registrar_uso(usuario: str, modulo: str):
    """Grava 1 relatorio gerado. Devolve (ok, mensagem)."""
    nivel = precos.nivel_do_modulo(modulo)
    try:
        auth_db._cli().table(TABELA_USO).insert({
            "usuario": usuario,
            "modulo": modulo,
            "nivel": nivel,
            "valor_ref": precos.VALOR_REFERENCIA[nivel],
        }).execute()
        return True, "registrado"
    except Exception as e:
        return False, f"Erro ao registrar uso: {e}"


def uso_do_mes(usuario: str | None = None,
               ano: int | None = None, mes: int | None = None):
    """Lista os registros do mes (de um usuario, ou de todos).
    Devolve (ok, lista | mensagem)."""
    ini, fim = _limites_mes(ano, mes)
    try:
        q = (auth_db._cli().table(TABELA_USO)
             .select("usuario,modulo,nivel,valor_ref,criado_em")
             .gte("criado_em", ini).lt("criado_em", fim))
        if usuario:
            q = q.eq("usuario", usuario)
        return True, q.order("criado_em").execute().data
    except Exception as e:
        return False, f"Erro ao consultar uso: {e}"


def contagem_do_mes(usuario: str,
                    ano: int | None = None, mes: int | None = None) -> int:
    """Quantos relatorios o usuario gerou no mes (0 em caso de erro)."""
    ok, dados = uso_do_mes(usuario, ano, mes)
    return len(dados) if ok else 0


def pode_gerar(plano: str, usuario: str):
    """Controle de acesso pelo plano contratado.
    Devolve (pode, mensagem, usados_no_mes, limite).
    Limites: Avulso 3 (cortesia) | Básico 20 | Profissional 50 | Ilimitado ∞.
    O admin deve ser isentado pelo chamador."""
    info = precos.plano_info(plano)
    limite = info.get("limite")
    usados = contagem_do_mes(usuario)
    if limite is None or usados < limite:
        return True, "", usados, limite
    if info["mensalidade"] > 0:
        msg = (f"Limite do plano {info['rotulo']} atingido: {usados} de "
               f"{limite} relatórios neste mês. Para continuar gerando, "
               f"fale com o administrador sobre ampliar o plano.")
    else:
        msg = (f"Os {limite} relatórios de cortesia deste mês já foram "
               f"usados. Para continuar gerando, contrate um plano com o "
               f"administrador.")
    return False, msg, usados, limite


def resumo_do_mes(ano: int | None = None, mes: int | None = None):
    """Consolidacao de cobranca por usuario.
    Devolve (ok, {usuario: {"Simples": n, "Médio": n, "Alto": n,
                            "total": n, "valor_avulso": x}} | mensagem)."""
    ok, dados = uso_do_mes(None, ano, mes)
    if not ok:
        return False, dados
    resumo: dict = {}
    for r in dados:
        u = resumo.setdefault(r["usuario"], {
            "Simples": 0, "Médio": 0, "Alto": 0,
            "total": 0, "valor_avulso": 0.0,
        })
        nivel = r.get("nivel") or "Médio"
        if nivel not in ("Simples", "Médio", "Alto"):
            nivel = "Médio"
        u[nivel] += 1
        u["total"] += 1
        try:
            u["valor_avulso"] += float(r.get("valor_ref") or 0.0)
        except (ValueError, TypeError):
            pass
    return True, resumo


def cobranca_sugerida(plano: str, resumo_usuario: dict):
    """Sugestao de cobranca do mes para um usuario.
    Devolve (valor, observacao)."""
    info = precos.plano_info(plano)
    total = resumo_usuario.get("total", 0)
    if info["mensalidade"] <= 0:  # avulso
        return resumo_usuario.get("valor_avulso", 0.0), "por relatório (avulso)"
    obs = f"mensalidade {info['rotulo']}"
    limite = info.get("limite")
    if limite and total > limite:
        obs += f" — ATENÇÃO: {total} relatórios excedem o limite de {limite}"
    justo = info.get("uso_justo")
    if justo and total > justo:
        obs += f" — acima da referência de uso justo ({justo})"
    return info["mensalidade"], obs
