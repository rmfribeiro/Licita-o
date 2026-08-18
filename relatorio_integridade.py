from __future__ import annotations
import html
import ia_utils
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
import branding
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from ia_integridade import (
    LABEL_DIMENSAO as _LABEL_DIMENSAO,
    COR_MATURIDADE_HEX as _COR_NIVEL_HEX,
    NAO_AVALIADO as _NAO_AVALIADO,
)
import disclaimers  # >>> DISCLAIMER (1/3): importa os textos centralizados

_COR_MATURIDADE = {k: colors.HexColor(v) for k, v in _COR_NIVEL_HEX.items()}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("titulo", parent=_estilos_base["Title"],   fontSize=16, spaceAfter=4)
_ESTILO_H1      = ParagraphStyle("h1pip", parent=_estilos_base["Heading1"])
_ESTILO_H2      = ParagraphStyle("h2",     parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("corpo",  parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("peq",    parent=_estilos_base["Normal"],   fontSize=8,
                                 textColor=colors.grey)
_ESTILO_BADGE   = ParagraphStyle("badge",  parent=_estilos_base["Normal"],   fontSize=14,
                                 textColor=colors.white, alignment=1)

# >>> DISCLAIMER (2/3): estilo do rodapé fixo + função que o desenha em CADA página.
#     Usa TEXTO_PDF (aviso brando): este relatório é um diagnóstico de apoio, não uma minuta.
_ESTILO_RODAPE = ParagraphStyle(
    "pip_rodape",
    parent=_estilos_base["Normal"],
    fontSize=7,
    leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)


def _rodape_todas_paginas(canvas, doc):
    """Desenha o disclaimer de apoio no rodapé de TODAS as páginas."""
    canvas.saveState()
    largura, _altura = A4
    p = Paragraph(disclaimers.TEXTO_PDF, _ESTILO_RODAPE)
    largura_util = largura - 4 * cm  # margens de 2cm de cada lado
    p.wrap(largura_util, 2 * cm)
    p.drawOn(canvas, 2 * cm, 1.0 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(largura - 2 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


def gerar_pdf(municipio: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm,  # >>> DISCLAIMER
    )

    story = []

    # Cabeçalho
    story.extend(branding.cabecalho_pdf(_ESTILO_TITULO))
    story.append(Paragraph("Diagnóstico do Programa de Integridade Pública", _ESTILO_H1))
    story.append(Paragraph(
        "Decreto 11.129/2022 · IN CGU 21/2021 · Lei 12.846/2013, art. 7º, III · Decreto 8.420/2015",
        _ESTILO_PEQUENO,
    ))
    story.append(Paragraph(f"Município: {html.escape(str(municipio or ''))}", _ESTILO_PEQUENO))
    story.append(Paragraph(ia_utils.carimbo_brasilia(), _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Nível de maturidade geral
    # Ausencia de valor nao vira INEXISTENTE: sem base, o laudo diz NAO AVALIADO.
    maturidade = str(parecer.get("maturidade_geral") or _NAO_AVALIADO).strip().upper()
    cor = _COR_MATURIDADE.get(maturidade, colors.grey)
    story.append(Paragraph("Nível de Maturidade Geral", _ESTILO_H2))
    t_mat = Table(
        [[Paragraph(f"<b>{html.escape(maturidade)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm],
    )
    t_mat.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_mat)
    story.append(Spacer(1, 0.4*cm))
    if maturidade == _NAO_AVALIADO:
        _motivo = parecer.get("_motivo_nao_avaliado")
        story.append(Paragraph(
            "Não foi possível avaliar a maturidade"
            + (f": {html.escape(str(_motivo))}." if _motivo else ".")
            + " Isto <b>não</b> significa que o município não tenha Programa de Integridade: "
            "significa que não há informação suficiente para afirmar nada, nem a favor nem "
            "contra.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2*cm))
    _aviso_mat_pdf = parecer.get("_aviso_maturidade")
    if _aviso_mat_pdf is not None:
        story.append(Paragraph(
            f"⚠ Valor de maturidade_geral não reconhecido: '{html.escape(str(_aviso_mat_pdf))}'"
            " — registrado como NÃO AVALIADO. Verifique manualmente.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2*cm))
    _aviso_piso_pdf = parecer.get("_aviso_piso_maturidade")
    if _aviso_mat_pdf is None and _aviso_piso_pdf is not None:
        story.append(Paragraph(
            f"(i) A IA avaliou a maturidade como {html.escape(str(_aviso_piso_pdf))}; "
            f"rebaixada para {html.escape(maturidade)} pelo piso de maturidade "
            "(critérios estruturantes ausentes). Verifique manualmente.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2*cm))

    # Resumo executivo
    resumo = str(parecer.get("resumo_executivo") or "")
    if resumo:
        story.append(Paragraph("Resumo Executivo", _ESTILO_H2))
        story.append(Paragraph(html.escape(resumo), _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    dims = parecer.get("dimensoes") or {}
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave) or {}
        nivel = str(dim.get("nivel") or _NAO_AVALIADO).strip().upper()
        cor_n = _COR_NIVEL_HEX.get(nivel, "#000000")
        story.append(Paragraph(
            f"<b>{html.escape(label)}</b> — "
            f"<font color='{cor_n}'><b>{html.escape(nivel)}</b></font>",
            _ESTILO_CORPO,
        ))
        for achado in (dim.get("achados") or []):
            if achado:
                story.append(Paragraph(f"  • {html.escape(str(achado))}", _ESTILO_CORPO))
        for rec in (dim.get("recomendacoes") or []):
            if rec:
                story.append(Paragraph(f"  → {html.escape(str(rec))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.2*cm))

    # Prioridades imediatas
    prioridades = parecer.get("prioridades") or []
    if prioridades:
        story.append(Paragraph("Prioridades Imediatas", _ESTILO_H2))
        for i, p in enumerate(prioridades, 1):
            if p:
                story.append(Paragraph(f"{i}. {html.escape(str(p))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    # MANIFESTO (17/08/2026): o relatorio diz QUAIS arquivos leu. Sem isso, um
    # documento residual no uploader entra na analise sem ninguem perceber —
    # foi o que aconteceu no teste de Reabilitacao, e custou uma conversa
    # inteira de deducao por marcadores de texto para descobrir.
    _docs_lidos = parecer.get("_documentos_analisados") or []
    story.append(Paragraph("Documentos Analisados", _ESTILO_H2))
    if _docs_lidos:
        for _l in ia_utils.linhas_manifesto(_docs_lidos):
            story.append(Paragraph(f"- {html.escape(_l)}", _ESTILO_CORPO))
    else:
        story.append(Paragraph(
            f"<b>{html.escape(ia_utils.AVISO_SEM_LASTRO)}</b>", _ESTILO_CORPO))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Base Legal", _ESTILO_H2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por RM Lisura — RM Vértice Digital.",
        _ESTILO_PEQUENO,
    ))

    # >>> DISCLAIMER (3/3): rodapé fixo em todas as páginas
    doc.build(story, onFirstPage=_rodape_todas_paginas, onLaterPages=_rodape_todas_paginas)
    return buf.getvalue()
