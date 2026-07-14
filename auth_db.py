# -*- coding: utf-8 -*-
"""
=============================================================================
 auth_db.py  -  RM IA-Licita / RM Vertice Digital
 Autenticacao de usuarios com banco Supabase (Postgres via API REST).
=============================================================================
 O que faz:
   - Criar conta (fica PENDENTE ate um admin aprovar)
   - Login com usuario OU e-mail + senha (bcrypt)
   - Esqueci a senha: codigo de 6 digitos por e-mail, valido por 30 min
   - Administracao: listar usuarios, aprovar / suspender / reativar

 Configuracao (secrets.toml local ou Secrets do Streamlit Cloud):
   SUPABASE_URL         = "https://xxxx.supabase.co"
   SUPABASE_SERVICE_KEY = "chave service_role (Settings > API)"
   SMTP_USUARIO         = "seuemail@gmail.com"        (p/ esqueci a senha)
   SMTP_SENHA           = "senha de app do Gmail"     (idem)

 Tabela: ver supabase_schema_ialicita.sql
=============================================================================
"""
import os
import re
import secrets as _secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

import bcrypt

try:
    import streamlit as st
except ImportError:  # permite usar o modulo fora do Streamlit (testes)
    st = None

try:
    from supabase import create_client
except ImportError:
    create_client = None

TABELA = "usuarios"
RESET_VALIDADE_MIN = 30

_RE_USUARIO = re.compile(r"^[a-z0-9_.\-]{3,30}$")
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

MSG_PENDENTE = ("Sua conta ainda não foi aprovada pelo administrador. "
                "Você receberá a liberação em breve.")
MSG_SUSPENSA = "Conta suspensa. Contate o administrador."


# ---------------------------------------------------------------------------
# Configuracao / cliente
# ---------------------------------------------------------------------------
def _secret(nome: str):
    v = os.environ.get(nome)
    if v:
        return v
    if st is not None:
        try:
            v = st.secrets.get(nome)
            return str(v) if v else None
        except Exception:
            return None
    return None


def erro_configuracao():
    """Devolve mensagem de erro se a autenticacao nao esta configurada
    (ou None se esta tudo certo)."""
    if create_client is None:
        return ("Dependência 'supabase' não instalada. "
                "Rode: pip install supabase  (ou confira o requirements.txt).")
    if not _secret("SUPABASE_URL") or not _secret("SUPABASE_SERVICE_KEY"):
        return ("Acesso não configurado: defina SUPABASE_URL e "
                "SUPABASE_SERVICE_KEY nos secrets. "
                "Veja CONFIGURAR_ACESSO.md. Contate o administrador.")
    return None


_cliente = None


def _cli():
    global _cliente
    if _cliente is None:
        _cliente = create_client(
            _secret("SUPABASE_URL"), _secret("SUPABASE_SERVICE_KEY")
        )
    return _cliente


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------
def _hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _confere_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _publico(u: dict) -> dict:
    """Dados do usuario que podem ir para a sessao (sem hash/segredos)."""
    return {
        "usuario": u["usuario"],
        "nome": u["nome"],
        "email": u["email"],
        "status": u["status"],
        "is_admin": bool(u.get("is_admin")),
        "plano": u.get("plano") or "avulso",
    }


# ---------------------------------------------------------------------------
# Operacoes
# ---------------------------------------------------------------------------
def criar_conta(usuario: str, nome: str, email: str, senha: str):
    """Cria conta com status 'pendente'. Devolve (ok, mensagem)."""
    usuario = (usuario or "").strip().lower()
    nome = (nome or "").strip()
    email = (email or "").strip().lower()

    if not _RE_USUARIO.match(usuario):
        return False, ("Usuário inválido: use 3 a 30 caracteres, apenas "
                       "letras minúsculas, números, ponto, hífen ou _.")
    if len(nome) < 3:
        return False, "Informe seu nome completo."
    if not _RE_EMAIL.match(email):
        return False, "E-mail inválido."
    if len(senha or "") < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."

    try:
        ja = (_cli().table(TABELA).select("usuario,email")
              .or_(f"usuario.eq.{usuario},email.eq.{email}")
              .execute().data)
        if ja:
            return False, "Usuário ou e-mail já cadastrado."
        _cli().table(TABELA).insert({
            "usuario": usuario,
            "nome": nome,
            "email": email,
            "senha_hash": _hash_senha(senha),
            "status": "pendente",
        }).execute()
    except Exception as e:
        return False, f"Erro ao criar a conta: {e}"
    return True, ("Conta criada! Ela será liberada após aprovação do "
                  "administrador — você poderá entrar assim que for aprovado.")


def autenticar(usuario_ou_email: str, senha: str):
    """Devolve (True, dados_do_usuario) ou (False, mensagem)."""
    chave = (usuario_ou_email or "").strip().lower()
    if not chave or not senha:
        return False, "Informe usuário e senha."
    try:
        achados = (_cli().table(TABELA).select("*")
                   .or_(f"usuario.eq.{chave},email.eq.{chave}")
                   .limit(1).execute().data)
    except Exception as e:
        return False, f"Erro ao consultar o banco: {e}"
    if not achados or not _confere_senha(senha, achados[0]["senha_hash"]):
        return False, "Usuário ou senha incorretos."
    u = achados[0]
    if u["status"] == "pendente":
        return False, MSG_PENDENTE
    if u["status"] != "aprovado":
        return False, MSG_SUSPENSA
    return True, _publico(u)


def solicitar_reset(email: str):
    """Gera codigo de 6 digitos, grava com validade e envia por e-mail."""
    email = (email or "").strip().lower()
    if not _RE_EMAIL.match(email):
        return False, "E-mail inválido."
    try:
        achados = (_cli().table(TABELA).select("usuario,nome")
                   .eq("email", email).limit(1).execute().data)
    except Exception as e:
        return False, f"Erro ao consultar o banco: {e}"
    if not achados:
        return False, "E-mail não encontrado no cadastro."

    codigo = f"{_secrets.randbelow(1000000):06d}"
    expira = (datetime.now(timezone.utc)
              + timedelta(minutes=RESET_VALIDADE_MIN)).isoformat()
    try:
        _cli().table(TABELA).update(
            {"reset_codigo": codigo, "reset_expira": expira}
        ).eq("email", email).execute()
    except Exception as e:
        return False, f"Erro ao registrar o código: {e}"

    ok, msg = _enviar_email_reset(email, achados[0]["nome"], codigo)
    if not ok:
        return False, msg
    return True, (f"Código enviado para {email}. Ele vale por "
                  f"{RESET_VALIDADE_MIN} minutos — confira também o spam.")


def redefinir_senha(email: str, codigo: str, nova_senha: str):
    email = (email or "").strip().lower()
    codigo = (codigo or "").strip()
    if len(nova_senha or "") < 8:
        return False, "A nova senha deve ter pelo menos 8 caracteres."
    try:
        achados = (_cli().table(TABELA)
                   .select("reset_codigo,reset_expira")
                   .eq("email", email).limit(1).execute().data)
    except Exception as e:
        return False, f"Erro ao consultar o banco: {e}"
    if not achados:
        return False, "E-mail não encontrado no cadastro."
    u = achados[0]
    if not u.get("reset_codigo") or not codigo or u["reset_codigo"] != codigo:
        return False, "Código incorreto. Solicite um novo se necessário."
    try:
        expira = datetime.fromisoformat(str(u["reset_expira"]))
        if expira < datetime.now(timezone.utc):
            return False, "Código expirado. Solicite um novo."
    except (ValueError, TypeError):
        return False, "Código expirado. Solicite um novo."
    try:
        _cli().table(TABELA).update({
            "senha_hash": _hash_senha(nova_senha),
            "reset_codigo": None,
            "reset_expira": None,
        }).eq("email", email).execute()
    except Exception as e:
        return False, f"Erro ao salvar a nova senha: {e}"
    return True, "Senha redefinida! Já dá para entrar com a nova senha."


# ---------------------------------------------------------------------------
# Administracao
# ---------------------------------------------------------------------------
def listar_usuarios():
    """Devolve (True, lista) ou (False, mensagem)."""
    try:
        dados = (_cli().table(TABELA)
                 .select("usuario,nome,email,status,is_admin,plano,criado_em")
                 .order("criado_em").execute().data)
        return True, dados
    except Exception as e:
        return False, f"Erro ao listar usuários: {e}"


def definir_status(usuario: str, status: str):
    """status: 'aprovado' | 'suspenso' | 'pendente'."""
    if status not in ("aprovado", "suspenso", "pendente"):
        return False, "Status inválido."
    try:
        _cli().table(TABELA).update({"status": status}) \
              .eq("usuario", usuario).execute()
        return True, f"Usuário '{usuario}' agora está '{status}'."
    except Exception as e:
        return False, f"Erro ao atualizar: {e}"


def definir_plano(usuario: str, plano: str):
    """plano: 'avulso' | 'basico' | 'profissional' | 'ilimitado'."""
    if plano not in ("avulso", "basico", "profissional", "ilimitado"):
        return False, "Plano inválido."
    try:
        _cli().table(TABELA).update({"plano": plano}) \
              .eq("usuario", usuario).execute()
        return True, f"Usuário '{usuario}' agora está no plano '{plano}'."
    except Exception as e:
        return False, f"Erro ao atualizar o plano: {e}"


# ---------------------------------------------------------------------------
# E-mail (esqueci a senha)
# ---------------------------------------------------------------------------
def _enviar_email_reset(email: str, nome: str, codigo: str):
    smtp_usuario = _secret("SMTP_USUARIO")
    smtp_senha = _secret("SMTP_SENHA")
    if not smtp_usuario or not smtp_senha:
        return False, ("Envio de e-mail não configurado (SMTP_USUARIO / "
                       "SMTP_SENHA). Peça ao administrador para redefinir "
                       "sua senha manualmente.")
    corpo = (
        f"Olá, {nome}!\n\n"
        f"Seu código para redefinir a senha do RM IA-Licita é:\n\n"
        f"    {codigo}\n\n"
        f"Ele vale por {RESET_VALIDADE_MIN} minutos. Se você não pediu "
        f"esta redefinição, ignore este e-mail.\n\n"
        f"RM Vértice Digital"
    )
    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = "RM IA-Licita — código para redefinir a senha"
    msg["From"] = smtp_usuario
    msg["To"] = email
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx,
                              timeout=30) as servidor:
            servidor.login(smtp_usuario, smtp_senha)
            servidor.sendmail(smtp_usuario, [email], msg.as_string())
        return True, "enviado"
    except Exception as e:
        return False, (f"Falha ao enviar o e-mail ({e}). Tente novamente ou "
                       f"contate o administrador.")
