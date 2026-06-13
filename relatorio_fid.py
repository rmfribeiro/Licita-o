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
from ia_utils import as_list as _as_list
from ia_fid import FASES_PROCESSO

_estilos_base  = getSampleStyleSheet()
_ESTILO_TITULO = ParagraphStyle("fid_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1     = ParagraphStyle("fid_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2     = ParagraphStyle("fid_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO  = ParagraphStyle("fid_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQNO  = ParagraphStyle("fid_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE  = ParagraphStyle("fid_badge",   parent=_estilos_base["Normal"],   fontSize=13, textColor=colors.white, alignment=1)
_ESTILO_OFICIO = ParagraphStyle("fid_oficio",  parent=_estilos_base["Normal"],   fontSize=9,  spaceAfter=4, leading=14)

_COR_RESULTADO = {
    "SIM":          colors.HexColor("#C0392B"),
    "PARCIALMENTE": colors.HexColor("#F39C12"),
    "NÃO":          colors.HexColor("#27AE60"),
}
_LABEL_RESULTADO = {
    "SIM":          "DILIGÊNCIA NECESSÁRIA",
    "NÃO":          "DILIGÊNCIA DESNECESSÁRIA",
    "PARCIALMENTE": "DILIGÊNCIA PARCIALMENTE NECESSÁRIA",
}


def gerar_pdf(dados_licitante: dict, fase: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    story: list = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Instituto da Diligência", _ESTILO_H1))
    story.append(Paragraph(
        "Art. 42, §2º · Art. 59, §2º · Art. 64, I e II — Lei 14.133/2021",
        _ESTILO_PEQNO,
    ))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _ESTILO_PEQNO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("Identificação", _ESTILO_H2))
    fase_label = FASES_PROCESSO.get(fase, fase)
    linhas_id = [
        ["Licitante",          html.escape(str(dados_licitante.get("razao_social") or "-"))],
        ["CNPJ",               html.escape(str(dados_licitante.get("cnpj") or "-"))],
        ["Nº Edital/Processo", html.escape(str(dados_licitante.get("numero_edital") or "-"))],
        ["Objeto",             html.escape(str(dados_licitante.get("objeto") or "-"))],
        ["Órgão",              html.escape(str(dados_licitante.get("orgao") or "-"))],
        ["Fase",               html.escape(fase_label)],
    ]
    t_id = Table(linhas_id, colWidths=[4.5 * cm, 12.5 * cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4 * cm))

    _res = str(parecer.get("necessita_diligencia") or "PARCIALMENTE").strip().upper()
    _cor_badge = _COR_RESULTADO.get(_res, colors.grey)
    _label_badge = _LABEL_RESULTADO.get(_res, _res)
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(_label_badge)}</b>", _ESTILO_BADGE)]],
        colWidths=[17 * cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4 * cm))

    _aviso_nd = parecer.get("_aviso_nd")
    if _aviso_nd:
        story.append(Paragraph(
            f"⚠ Valor original não reconhecido: '{html.escape(str(_aviso_nd))}' — registrado como DILIGÊNCIA PARCIALMENTE NECESSÁRIA.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2 * cm))

    docs = _as_list(parecer.get("documentos_solicitados"))
    if docs:
        story.append(Paragraph("Documentos / Informações a Solicitar", _ESTILO_H2))
        linhas_docs: list[list] = [["#", "Documento / Informação", "Situação", "Fundamento Legal", "Prazo"]]
        for i, d in enumerate(docs, 1):
            if not isinstance(d, dict):
                continue
            linhas_docs.append([
                str(i),
                html.escape(str(d.get("documento") or "-")),
                html.escape(str(d.get("situacao") or "-")),
                html.escape(str(d.get("fundamento_legal") or "-")),
                f"{d.get('prazo_dias', 5)} dias",
            ])
        t_docs = Table(linhas_docs, colWidths=[0.6 * cm, 5.8 * cm, 2.3 * cm, 5.4 * cm, 1.9 * cm])
        t_docs.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
            ("FONTSIZE",   (0, 0), (-1, -1), 8),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING",    (0, 0), (-1, -1), 3),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t_docs)
        story.append(Spacer(1, 0.4 * cm))

    pontos = _as_list(parecer.get("pontos_de_atencao"))
    if pontos:
        story.append(Paragraph("Pontos de Atenção", _ESTILO_H2))
        for ponto in pontos:
            if str(ponto).strip():
                story.append(Paragraph(f"• {html.escape(str(ponto))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    minuta = str(parecer.get("minuta_oficio") or "").strip()
    if minuta:
        story.append(Paragraph("Minuta do Ofício de Diligência", _ESTILO_H2))
        story.append(Spacer(1, 0.2 * cm))
        for linha in minuta.split("\n"):
            story.append(Paragraph(html.escape(linha) if linha.strip() else " ", _ESTILO_OFICIO))
        story.append(Spacer(1, 0.4 * cm))

    conclusao = str(parecer.get("conclusao") or "").strip()
    if conclusao:
        story.append(Paragraph("Conclusão", _ESTILO_H2))
        story.append(Paragraph(html.escape(conclusao), _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    base_legal = _as_list(parecer.get("base_legal"))
    if base_legal:
        story.append(Paragraph("Base Legal", _ESTILO_H2))
        for bl in base_legal:
            if str(bl).strip():
                story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificação humana. "
        "Não substitui parecer jurídico.",
        _ESTILO_PEQNO,
    ))

    doc.build(story)
    return buf.getvalue()
