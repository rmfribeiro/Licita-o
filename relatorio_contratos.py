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
from ia_contratos import TIPOS_ALTERACAO

_COR_PARECER = {
    "DEFERÍVEL":               colors.HexColor(_COR_STATUS["ok"]),
    "DEFERÍVEL COM RESSALVAS": colors.HexColor("#F39C12"),
    "INDEFERÍVEL":             colors.HexColor(_COR_STATUS["critico"]),
}

_COR_REQUISITO = {
    "ATENDIDO": colors.HexColor(_COR_STATUS["ok"]),
    "PARCIAL":  colors.HexColor("#F39C12"),
    "AUSENTE":  colors.HexColor(_COR_STATUS["critico"]),
}

_estilos_base    = getSampleStyleSheet()
_ESTILO_TITULO   = ParagraphStyle("cont_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1       = ParagraphStyle("cont_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2       = ParagraphStyle("cont_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO    = ParagraphStyle("cont_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO  = ParagraphStyle("cont_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE    = ParagraphStyle("cont_badge",   parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_REQ_OK   = ParagraphStyle("cont_req_ok",  parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["ok"]))
_ESTILO_REQ_PAR  = ParagraphStyle("cont_req_par", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor("#F39C12"))
_ESTILO_REQ_AUS  = ParagraphStyle("cont_req_aus", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["critico"]))

_ICONE_REQ = {"ATENDIDO": "✓ ATENDIDO", "PARCIAL": "⚠ PARCIAL", "AUSENTE": "✗ AUSENTE"}
_ESTILO_REQ_MAP = {
    "ATENDIDO": _ESTILO_REQ_OK,
    "PARCIAL":  _ESTILO_REQ_PAR,
    "AUSENTE":  _ESTILO_REQ_AUS,
}


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(dados_contrato: dict, tipo: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Analisador de Alterações Contratuais", _ESTILO_H1))
    story.append(Paragraph(
        "Art. 124 II 'd' · Art. 25 §8º · Art. 137 §2º — Lei 14.133/2021 · Art. 37 XXI CF/88",
        _ESTILO_PEQUENO,
    ))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}",
        _ESTILO_PEQUENO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação do Contrato
    story.append(Paragraph("Identificação do Contrato", _ESTILO_H2))
    tipo_label = TIPOS_ALTERACAO.get(tipo, tipo)
    linhas_id = [
        ["Número do Contrato", html.escape(str(dados_contrato.get("numero_contrato") or "-"))],
        ["Objeto", html.escape(str(dados_contrato.get("objeto") or "-"))],
        ["Data de Assinatura", html.escape(str(dados_contrato.get("data_assinatura") or "-"))],
        ["Valor Atual", _fmt_brl(float(dados_contrato.get("valor_atual") or 0))],
        ["Tipo de Alteração", html.escape(tipo_label)],
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

    # Badge do parecer
    parecer_val = str(parecer.get("parecer") or "INDEFERÍVEL").strip().upper()
    cor_badge = _COR_PARECER.get(parecer_val, colors.grey)
    story.append(Paragraph("Parecer Conclusivo", _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(parecer_val)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_badge),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    # Síntese
    sintese = str(parecer.get("sintese") or "-")
    story.append(Paragraph("Síntese", _ESTILO_H2))
    story.append(Paragraph(html.escape(sintese), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Checklist de requisitos
    requisitos = parecer.get("requisitos") or []
    if requisitos:
        story.append(Paragraph("Verificação de Requisitos", _ESTILO_H2))
        for req in requisitos:
            if not req:
                continue
            status = str(req.get("status") or "AUSENTE").strip().upper()
            icone = _ICONE_REQ.get(status, status)
            estilo = _ESTILO_REQ_MAP.get(status, _ESTILO_CORPO)
            descricao = html.escape(str(req.get("descricao") or ""))
            obs = html.escape(str(req.get("observacao") or ""))
            linha = f"<b>[{icone}]</b> {descricao}"
            if obs:
                linha += f" — {obs}"
            story.append(Paragraph(linha, estilo))
        story.append(Spacer(1, 0.3*cm))

    # Lacunas documentais
    lacunas = parecer.get("lacunas_documentais") or []
    if lacunas:
        story.append(Paragraph("Lacunas Documentais", _ESTILO_H2))
        for i, lac in enumerate(lacunas, 1):
            if lac:
                story.append(Paragraph(f"{i}. {html.escape(str(lac))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Fundamentos legais
    story.append(Paragraph("Fundamentos Legais", _ESTILO_H2))
    for fl in (parecer.get("fundamentos_legais") or []):
        if fl:
            story.append(Paragraph(f"- {html.escape(str(fl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes") or []
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if rec:
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
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
