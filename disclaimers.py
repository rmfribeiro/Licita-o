# -*- coding: utf-8 -*-
"""
disclaimers.py — Avisos legais centralizados do IA-Licita.

Centraliza todos os textos de disclaimer em um único lugar.
Para ajustar a redação, edite AQUI e todas as abas/PDFs se atualizam.

Uso nas abas (tela):
    import disclaimers
    disclaimers.rodape_tela()                 # aviso padrão de apoio
    disclaimers.aviso_minuta()                # aviso forte p/ documentos gerados

Uso nos relatórios (PDF):
    import disclaimers
    texto = disclaimers.TEXTO_PDF             # string p/ inserir no rodapé do PDF
    texto_minuta = disclaimers.TEXTO_PDF_MINUTA
"""
# Nota: o streamlit é importado dentro das funções de tela (não no topo),
# para que os módulos de PDF possam usar apenas os TEXTOS sem depender do streamlit.

# ─────────────────────────────────────────────────────────────────────────────
# TEXTOS-BASE — edite aqui para alterar em todo o sistema
# ─────────────────────────────────────────────────────────────────────────────

# Aviso padrão: usado em abas de auditoria/análise (apoio à decisão)
TEXTO_APOIO = (
    "Ferramenta de apoio à decisão — não substitui a análise técnica e jurídica "
    "individual. Todos os apontamentos, cálculos e fundamentos legais gerados, "
    "inclusive por inteligência artificial, devem ser conferidos e validados por "
    "profissional habilitado antes de qualquer uso oficial."
)

# Aviso forte: usado em abas que GERAM documentos (minutas de atos, ofícios, requerimentos)
TEXTO_MINUTA = (
    "MINUTA SUJEITA À REVISÃO — Este documento foi gerado com auxílio de inteligência "
    "artificial e tem caráter de rascunho. NÃO constitui ato administrativo, parecer "
    "jurídico ou peça oficial. Deve ser integralmente revisado, corrigido e validado "
    "por profissional habilitado antes de qualquer assinatura, publicação ou efeito legal."
)

# Versão dos textos para inserir dentro dos PDFs (sem markup do Streamlit)
TEXTO_PDF = (
    "AVISO: Ferramenta de apoio à decisão — não substitui a análise técnica e jurídica "
    "individual. Os apontamentos, cálculos e fundamentos legais deste relatório, gerados "
    "inclusive por inteligência artificial, devem ser conferidos e validados por "
    "profissional habilitado antes de qualquer uso oficial."
)

TEXTO_PDF_MINUTA = (
    "MINUTA SUJEITA À REVISÃO — Documento gerado com auxílio de inteligência artificial, "
    "com caráter de rascunho. NÃO constitui ato administrativo, parecer jurídico ou peça "
    "oficial. Deve ser integralmente revisado e validado por profissional habilitado antes "
    "de qualquer assinatura, publicação ou efeito legal."
)


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES PARA A TELA (Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

def rodape_tela() -> None:
    """Aviso padrão de apoio à decisão. Use ao final de cada aba de análise."""
    import streamlit as st
    st.caption(f"⚖️ {TEXTO_APOIO}")


def aviso_minuta() -> None:
    """Aviso forte e destacado. Use em abas que geram minutas/atos/ofícios."""
    import streamlit as st
    st.warning(f"⚠️ **{TEXTO_MINUTA}**")
