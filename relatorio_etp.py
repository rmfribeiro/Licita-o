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
from ia_utils import COR_STATUS_HEX as _COR_STATUS

_COR_ADEQUACAO = {
    "ADEQUADO":               colors.HexColor(_COR_STATUS["ok"]),
    "ADEQUADO COM RESSALVAS": colors.HexColor("#F39C12"),
    "INADEQUADO":             colors.HexColor(_COR_STATUS["critico"]),
}

_LABEL_DIMENSAO = {
    "descricao_necessidade":       "Descrição da Necessidade",
    "alinhamento_estrategico":     "Alinhamento Estratégico",
    "requisitos_contratacao":      "Requisitos da Contratação",
    "levantamento_mercado":        "Levantamento de Mercado",
    "estimativa_quantidade_valor": "Estimativa de Quantidade e Valor",
    "sustentabilidade":            "Sustentabilidade",
    "parcelamento":                "Parcelamento do Objeto",
    "posicionamento_conclusivo":   "Posicionamento Conclusivo",
}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("etp_titulo", parent=_estilos_base["Title"],   fontSize=16, spaceAfter=4)
_ESTILO_H2      = ParagraphStyle("etp_h2",     parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("etp_corpo",  parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("etp_peq",    parent=_estilos_base["Normal"],   fontSize=8, textColor=colors.grey)
_ESTILO_H1      = ParagraphStyle("etp_h1",     parent=_estilos_base["Heading1"])
_ESTILO_ALERTA  = ParagraphStyle("etp_alerta", parent=_ESTILO_CORPO, textColor=colors.HexColor(_COR_STATUS["alerta"]))


def gerar_pdf(nomes_arquivos: list[str], avisos: list[str], parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Auditoria de ETP — Estudo Técnico Preliminar", _ESTILO_H1))
    story.append(Paragraph("IN SEGES/MGI 58/2022 · Lei 14.133/2021, art. 18, I", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Documentos analisados
    story.append(Paragraph("Documentos Analisados", _ESTILO_H2))
    for nome in nomes_arquivos:
        story.append(Paragraph(f"- {html.escape(str(nome))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Avisos
    if avisos:
        story.append(Paragraph("Avisos", _ESTILO_H2))
        for aviso in avisos:
            story.append(Paragraph(f"AVISO: {html.escape(str(aviso))}", _ESTILO_ALERTA))
        story.append(Spacer(1, 0.3*cm))

    # Adequação geral
    adequacao = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    cor = _COR_ADEQUACAO.get(adequacao, colors.grey)
    story.append(Paragraph("Adequação Geral", _ESTILO_H2))
    t_adeq = Table(
        [[Paragraph(f"<b>{html.escape(str(adequacao))}</b>",
                    ParagraphStyle("a", fontSize=14, textColor=colors.white, alignment=1))]],
        colWidths=[17*cm],
    )
    t_adeq.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_adeq)
    story.append(Spacer(1, 0.4*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    dims = parecer.get("dimensoes") or {}
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave) or {}
        status = (dim.get("status") or "ok").lower()
        cor_s = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor_s}'><b>[{icone}] {html.escape(label)}</b></font>: {html.escape(str(dim.get('descricao') or '-'))}",
            _ESTILO_CORPO,
        ))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos", [])
    if criticos:
        story.append(Paragraph("Pontos Críticos", _ESTILO_H2))
        for i, ponto in enumerate(criticos, 1):
            story.append(Paragraph(f"{i}. {html.escape(str(ponto or ''))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes", [])
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            story.append(Paragraph(f"{i}. {html.escape(str(rec or ''))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Base legal
    story.append(Paragraph("Base Legal", _ESTILO_H2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
