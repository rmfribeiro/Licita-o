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

_COR_MATURIDADE = {
    "CONSOLIDADO":        colors.HexColor("#27AE60"),
    "EM DESENVOLVIMENTO": colors.HexColor("#2980B9"),
    "INICIAL":            colors.HexColor("#F39C12"),
    "INEXISTENTE":        colors.HexColor("#C0392B"),
}
_COR_NIVEL_HEX = {
    "CONSOLIDADO":        "#27AE60",
    "EM DESENVOLVIMENTO": "#2980B9",
    "INICIAL":            "#F39C12",
    "INEXISTENTE":        "#C0392B",
}
from ia_integridade import LABEL_DIMENSAO as _LABEL_DIMENSAO


def gerar_pdf(municipio: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    estilos = getSampleStyleSheet()
    titulo  = ParagraphStyle("titulo", parent=estilos["Title"],   fontSize=16, spaceAfter=4)
    h2      = ParagraphStyle("h2",    parent=estilos["Heading2"], fontSize=12, spaceAfter=3)
    corpo   = ParagraphStyle("corpo", parent=estilos["Normal"],   fontSize=10, spaceAfter=3)
    pequeno = ParagraphStyle("peq",   parent=estilos["Normal"],   fontSize=8,
                             textColor=colors.grey)

    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", titulo))
    story.append(Paragraph("Diagnóstico do Programa de Integridade Pública", estilos["Heading1"]))
    story.append(Paragraph(
        "Decreto 11.129/2022 · IN CGU 21/2021 · Lei 12.846/2013, art. 7º, III · Decreto 8.420/2015",
        pequeno,
    ))
    story.append(Paragraph(f"Município: {html.escape(str(municipio or ''))}", pequeno))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", pequeno))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Nível de maturidade geral
    maturidade = str(parecer.get("maturidade_geral") or "INEXISTENTE").strip().upper()
    cor = _COR_MATURIDADE.get(maturidade, colors.grey)
    story.append(Paragraph("Nível de Maturidade Geral", h2))
    t_mat = Table(
        [[Paragraph(
            f"<b>{html.escape(maturidade)}</b>",
            ParagraphStyle("m", fontSize=14, textColor=colors.white, alignment=1),
        )]],
        colWidths=[17*cm],
    )
    t_mat.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_mat)
    story.append(Spacer(1, 0.4*cm))

    # Resumo executivo
    resumo = str(parecer.get("resumo_executivo") or "")
    if resumo:
        story.append(Paragraph("Resumo Executivo", h2))
        story.append(Paragraph(html.escape(resumo), corpo))
        story.append(Spacer(1, 0.3*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", h2))
    dims = parecer.get("dimensoes") or {}
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave) or {}
        nivel = str(dim.get("nivel") or "INEXISTENTE").strip().upper()
        cor_n = _COR_NIVEL_HEX.get(nivel, "#000000")
        story.append(Paragraph(
            f"<b>{html.escape(label)}</b> — "
            f"<font color='{cor_n}'><b>{html.escape(nivel)}</b></font>",
            corpo,
        ))
        for achado in (dim.get("achados") or []):
            if achado:
                story.append(Paragraph(f"  • {html.escape(str(achado))}", corpo))
        for rec in (dim.get("recomendacoes") or []):
            if rec:
                story.append(Paragraph(f"  → {html.escape(str(rec))}", corpo))
        story.append(Spacer(1, 0.2*cm))

    # Prioridades imediatas
    prioridades = parecer.get("prioridades") or []
    if prioridades:
        story.append(Paragraph("Prioridades Imediatas", h2))
        for i, p in enumerate(prioridades, 1):
            if p:
                story.append(Paragraph(f"{i}. {html.escape(str(p))}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    story.append(Paragraph("Base Legal", h2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", corpo))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        pequeno,
    ))

    doc.build(story)
    return buf.getvalue()
