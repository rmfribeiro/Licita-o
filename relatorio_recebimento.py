# relatorio_recebimento.py
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
from ia_utils import COR_STATUS_HEX as _COR_STATUS, as_list as _as_list, fmt_brl as _fmt_brl, safe_float as _safe_float, fmt_brl_opcional as _fmt_brl_opcional
from ia_recebimento import TIPOS_OBJETO, NORM_PARECER_RECV as _NORM_PARECER_RECV

_COR_PARECER = {
    "APTO":               colors.HexColor(_COR_STATUS["ok"]),
    "APTO COM RESSALVAS": colors.HexColor("#F39C12"),
    "INAPTO":             colors.HexColor(_COR_STATUS["critico"]),
}

_estilos_base    = getSampleStyleSheet()
_ESTILO_TITULO   = ParagraphStyle("recv_titulo",   parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1       = ParagraphStyle("recv_h1",       parent=_estilos_base["Heading1"])
_ESTILO_H2       = ParagraphStyle("recv_h2",       parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO    = ParagraphStyle("recv_corpo",    parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO  = ParagraphStyle("recv_peq",      parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE    = ParagraphStyle("recv_badge",    parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_COND_OK  = ParagraphStyle("recv_cond_ok",  parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["ok"]))
_ESTILO_COND_PAR = ParagraphStyle("recv_cond_par", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor("#F39C12"))
_ESTILO_COND_AUS = ParagraphStyle("recv_cond_aus", parent=_estilos_base["Normal"],   fontSize=9,  textColor=colors.HexColor(_COR_STATUS["critico"]))

_ICONE_COND = {"ATENDIDA": "✓ ATENDIDA", "PARCIAL": "⚠ PARCIAL", "AUSENTE": "✗ AUSENTE"}
_ESTILO_COND_MAP = {
    "ATENDIDA": _ESTILO_COND_OK,
    "PARCIAL":  _ESTILO_COND_PAR,
    "AUSENTE":  _ESTILO_COND_AUS,
}


def _render_bloco(story: list, titulo: str, bloco: dict) -> None:
    parecer_val = str(bloco.get("parecer") or "INAPTO").strip().upper()
    parecer_val = _NORM_PARECER_RECV.get(parecer_val, parecer_val)
    cor_badge = _COR_PARECER.get(parecer_val, colors.grey)

    story.append(Paragraph(titulo, _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(parecer_val)}</b>", _ESTILO_BADGE)]],
        colWidths=[17 * cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.3 * cm))

    _aviso_pval = bloco.get("_aviso_parecer")
    if _aviso_pval is not None:
        story.append(Paragraph(
            f"⚠ Valor original não reconhecido: '{html.escape(str(_aviso_pval))}' — registrado como INAPTO.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2 * cm))

    sintese = str(bloco.get("sintese") or "-")
    story.append(Paragraph(html.escape(sintese), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3 * cm))

    condicoes = _as_list(bloco.get("condicoes"))
    if condicoes:
        story.append(Paragraph("Condições Verificadas:", _ESTILO_H2))
        for cond in condicoes:
            if not isinstance(cond, dict) or not cond:
                continue
            status = str(cond.get("status") or "AUSENTE").strip().upper()
            icone = _ICONE_COND.get(status, html.escape(status))
            estilo = _ESTILO_COND_MAP.get(status, _ESTILO_CORPO)
            descricao = html.escape(str(cond.get("descricao") or ""))
            obs = html.escape(str(cond.get("observacao") or ""))
            linha = f"<b>[{icone}]</b> {descricao}"
            if obs:
                linha += f" — {obs}"
            story.append(Paragraph(linha, estilo))
        story.append(Spacer(1, 0.2 * cm))

    pendencias = _as_list(bloco.get("pendencias"))
    if pendencias:
        story.append(Paragraph("Pendências:", _ESTILO_H2))
        for i, p in enumerate(pendencias, 1):
            if str(p).strip():
                story.append(Paragraph(f"{i}. {html.escape(str(p))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.2 * cm))

    story.append(Spacer(1, 0.4 * cm))


def gerar_pdf(dados_entrega: dict, tipo_objeto: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    )
    story = []

    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Monitor de Recebimento Contratual", _ESTILO_H1))
    story.append(Paragraph("Art. 140, I e II — Lei 14.133/2021", _ESTILO_PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _ESTILO_PEQUENO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("Identificação do Contrato", _ESTILO_H2))
    tipo_label = TIPOS_OBJETO.get(tipo_objeto, tipo_objeto)
    linhas_id = [
        ["Número do Contrato",        html.escape(str(dados_entrega.get("numero_contrato") or "-"))],
        ["Objeto",                    html.escape(str(dados_entrega.get("objeto") or "-"))],
        ["Data de Entrega/Conclusão", html.escape(str(dados_entrega.get("data_entrega") or "-"))],
        ["Valor do Contrato",         _fmt_brl_opcional(dados_entrega.get("valor_contrato"))],
        ["Tipo de Objeto",            html.escape(tipo_label)],
    ]
    t_id = Table(linhas_id, colWidths=[5 * cm, 12 * cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4 * cm))

    _render_bloco(
        story,
        "Recebimento Provisório (Art. 140, I)",
        parecer.get("recebimento_provisorio") or {},
    )
    _render_bloco(
        story,
        "Recebimento Definitivo (Art. 140, II)",
        parecer.get("recebimento_definitivo") or {},
    )

    recs = _as_list(parecer.get("recomendacoes_gerais"))
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if str(rec).strip():
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.4 * cm))

    base_legal = _as_list(parecer.get("base_legal"))
    if base_legal:
        story.append(Paragraph("Base Legal", _ESTILO_H2))
        for bl in base_legal:
            if str(bl).strip():
                story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificacao humana. "
        "Nao substitui parecer juridico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
