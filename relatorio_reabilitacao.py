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

_LABEL_SANCAO = {
    "impedimento":  "Impedimento de Licitar e Contratar (Art. 156, III)",
    "inidoneidade": "Declaração de Inidoneidade (Art. 156, IV)",
}

_COR_PARECER = {
    "ELEGÍVEL":               colors.HexColor(_COR_STATUS["ok"]),
    "ELEGÍVEL COM RESSALVAS": colors.HexColor(_COR_STATUS["alerta"]),
    "INELEGÍVEL":             colors.HexColor(_COR_STATUS["critico"]),
}

_STATUS_ICONE = {
    "ATENDIDA": "ATENDIDA",
    "PARCIAL":  "PARCIAL",
    "AUSENTE":  "AUSENTE",
    "N.A.":     "N.A.",
}

_estilos    = getSampleStyleSheet()
_TITULO     = ParagraphStyle("reab_titulo", parent=_estilos["Title"],   fontSize=16, spaceAfter=4)
_H1         = ParagraphStyle("reab_h1",     parent=_estilos["Heading1"])
_H2         = ParagraphStyle("reab_h2",     parent=_estilos["Heading2"], fontSize=12, spaceAfter=3)
_CORPO      = ParagraphStyle("reab_corpo",  parent=_estilos["Normal"],   fontSize=10, spaceAfter=3)
_PEQUENO    = ParagraphStyle("reab_peq",    parent=_estilos["Normal"],   fontSize=8,  textColor=colors.grey)
_BADGE      = ParagraphStyle("reab_badge",  parent=_estilos["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def gerar_relatorio_tecnico(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Reabilitação de Fornecedor — Relatório Técnico", _H1))
    story.append(Paragraph("Art. 163, Par. Único, Lei 14.133/2021", _PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("Identificação do Fornecedor", _H2))
    _tipo_key   = str(dados_sancao.get("tipo_sancao") or "")
    _tipo_label = _LABEL_SANCAO.get(_tipo_key, html.escape(_tipo_key))
    linhas_id = [
        ["Razão Social",      html.escape(str(dados_empresa.get("razao_social") or "-"))],
        ["CNPJ",              _fmt_cnpj(cnpj)],
        ["Tipo de Sanção",    html.escape(_tipo_label)],
        ["Data da Sanção",    html.escape(str(dados_sancao.get("data_aplicacao") or "-"))],
        ["Órgão Sancionador", html.escape(str(dados_sancao.get("orgao") or "-"))],
    ]
    t_id = Table(linhas_id, colWidths=[5*cm, 12*cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4*cm))

    _pval    = str(parecer.get("parecer") or "INELEGÍVEL").strip().upper()
    _cor_par = _COR_PARECER.get(_pval, colors.grey)
    story.append(Paragraph("Parecer de Elegibilidade", _H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(_pval)}</b>", _BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _cor_par),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Condições Art. 163, Par. Único (5 condições cumulativas)", _H2))
    for cond in (parecer.get("condicoes_avaliadas") or []):
        if not cond:
            continue
        _st = str(cond.get("status") or "AUSENTE").strip().upper()
        _ic = _STATUS_ICONE.get(_st, _st)
        story.append(Paragraph(
            f"<b>Condição {html.escape(str(cond.get('numero') or ''))}: </b>"
            f"{html.escape(str(cond.get('descricao') or ''))} — {html.escape(_ic)}",
            _CORPO,
        ))
        if cond.get("observacao"):
            story.append(Paragraph(
                f"  {html.escape(str(cond['observacao']))}",
                _PEQUENO,
            ))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Síntese", _H2))
    story.append(Paragraph(html.escape(str(parecer.get("sintese") or "-")), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("Base Legal", _H2))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _CORPO))
    story.append(Spacer(1, 0.4*cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita - RM Vertice Digital. "
        "Sujeito a verificacao humana. Nao substitui parecer juridico.",
        _PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
