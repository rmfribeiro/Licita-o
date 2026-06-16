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
from ia_utils import COR_STATUS_HEX as _COR_STATUS, fmt_brl_opcional as _fmt_brl_opcional
import disclaimers

_COR_RISCO = {
    "ALTO":                   colors.HexColor(_COR_STATUS["critico"]),
    "MEDIO":                  colors.HexColor(_COR_STATUS["alerta"]),
    "BAIXO":                  colors.HexColor(_COR_STATUS["ok"]),
    "SEM RISCO IDENTIFICADO": colors.HexColor(_COR_STATUS["ok"]),
}

_LABEL_DIMENSAO = {
    "situacao_cadastral": "Situação Cadastral",
    "sancoes": "Sanções e Punições",
    "programa_integridade": "Programa de Integridade",
    "fid": "Autoavaliação (FID)",
    "contexto_contrato": "Contexto do Contrato",
}
_PERGUNTAS_FID = {
    "q1": "Código de Ética ou Conduta formal",
    "q2": "Canal de denúncias ativo",
    "q3": "Treinamentos periódicos de integridade",
    "q4": "Política de conflito de interesses",
    "q5": "Auditorias internas ou externas",
}
_BOOL_PT = {True: "Sim", False: "Não"}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("ddi_titulo", parent=_estilos_base["Title"],   fontSize=16, spaceAfter=4)
_ESTILO_H2      = ParagraphStyle("ddi_h2",     parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("ddi_corpo",  parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("ddi_peq",    parent=_estilos_base["Normal"],   fontSize=8, textColor=colors.grey)
_ESTILO_H1      = ParagraphStyle("ddi_h1",     parent=_estilos_base["Heading1"])
_ESTILO_BADGE   = ParagraphStyle("ddi_badge",  parent=_estilos_base["Normal"], fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_RODAPE  = ParagraphStyle(
    "ddi_rodape",
    parent=_estilos_base["Normal"],
    fontSize=7, leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)


def _rodape_todas_paginas(canvas, doc):
    canvas.saveState()
    largura, _altura = A4
    p = Paragraph(disclaimers.TEXTO_PDF, _ESTILO_RODAPE)
    largura_util = largura - 4 * cm
    p.wrap(largura_util, 2 * cm)
    p.drawOn(canvas, 2 * cm, 1.0 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(largura - 2 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def gerar_pdf(cnpj: str, valor_contrato: float | None, dados: dict, fid: dict, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Due Diligence de Integridade (DDI)", _ESTILO_H1))
    story.append(Paragraph("Portaria SEGES/ME 8.678/2021, art. 2 III - Decreto 12.304/2024", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação
    story.append(Paragraph("Identificação do Licitante", _ESTILO_H2))
    linhas_id = [
        ["Razão Social",            html.escape(str(dados.get("razao_social") or "-"))],
        ["CNPJ",                    _fmt_cnpj(cnpj)],
        ["Situação Cadastral",      html.escape(str(dados.get("situacao") or "-"))],
        ["Porte",                   html.escape(str(dados.get("porte") or "-"))],
        ["CNAE Principal",          html.escape(str(dados.get("cnae") or "-"))],
        ["Data de Abertura",        html.escape(str(dados.get("data_abertura") or "-"))],
        ["Valor do Contrato",       _fmt_brl_opcional(valor_contrato)],
        ["Grande Vulto (> R$ 239M)", _BOOL_PT.get(dados.get("grande_vulto"), "-")],
    ]
    t = Table(linhas_id, colWidths=[5*cm, 12*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4*cm))

    # Sócios
    socios = dados.get("socios") or []
    if socios:
        story.append(Paragraph("Quadro Societário", _ESTILO_H2))
        for s in socios:
            if not s:
                continue
            story.append(Paragraph(f"- {html.escape(str(s.get('nome') or '-'))} -- {html.escape(str(s.get('cargo') or '-'))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Índice de risco
    risco_display = str(parecer.get("risco_geral") or "SEM RISCO IDENTIFICADO").strip().upper()
    risco_key = {"MÉDIO": "MEDIO"}.get(risco_display, risco_display)
    cor_risco = _COR_RISCO.get(risco_key, colors.grey)
    story.append(Paragraph("Índice de Risco Geral", _ESTILO_H2))
    t_risco = Table(
        [[Paragraph(f"<b>{html.escape(risco_display)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm]
    )
    t_risco.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_risco),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_risco)
    story.append(Spacer(1, 0.4*cm))
    _aviso_risco_pdf = parecer.get("_aviso_risco")
    if _aviso_risco_pdf is not None:
        _sem_risco_pdf = "SEM RISCO IDENTIFICADO"
        if risco_display != _sem_risco_pdf:
            _aviso_risco_txt = (
                f"⚠ Valor de risco_geral não reconhecido: '{html.escape(str(_aviso_risco_pdf))}'"
                f" — mapeado para {_sem_risco_pdf}; elevado para {html.escape(risco_display)}"
                " por piso mínimo de risco (ocorrência ativa nos cadastros CEIS/CNEP). Verifique manualmente."
            )
        else:
            _aviso_risco_txt = (
                f"⚠ Valor de risco_geral não reconhecido: '{html.escape(str(_aviso_risco_pdf))}'"
                f" — registrado como {_sem_risco_pdf}. Verifique manualmente."
            )
        story.append(Paragraph(_aviso_risco_txt, _ESTILO_CORPO))
        story.append(Spacer(1, 0.2*cm))
    _aviso_piso_pdf = parecer.get("_aviso_piso")
    if _aviso_risco_pdf is None and _aviso_piso_pdf is not None:
        story.append(Paragraph(
            f"ℹ A IA avaliou o risco como {html.escape(str(_aviso_piso_pdf))}; elevado para"
            f" {html.escape(risco_display)} por piso mínimo de risco em razão de ocorrência"
            " ativa nos cadastros (CEIS/CNEP). Verifique manualmente.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2*cm))

    # Risco por dimensão
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    dims = parecer.get("dimensoes") or {}
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave) or {}
        status = (dim.get("status") or "ok").lower()
        cor = html.escape(_COR_STATUS.get(status, "#000000"))
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor}'><b>[{icone}] {html.escape(label)}</b></font>: {html.escape(str(dim.get('descricao') or '-'))}",
            _ESTILO_CORPO
        ))
        for achado in (dim.get("achados") or []):
            if not achado:
                continue
            story.append(Paragraph(
                f"  -> <b>{html.escape(str(achado.get('fonte') or ''))}</b>: "
                f"{html.escape(str(achado.get('descricao') or ''))} "
                f"(gravidade: {html.escape(str(achado.get('gravidade') or ''))})",
                _ESTILO_CORPO
            ))
    story.append(Spacer(1, 0.3*cm))

    # FID
    story.append(Paragraph("Formulário de Integridade e Diligência (FID)", _ESTILO_H2))
    linhas_fid = [["Critério", "Resposta"]] + [
        [html.escape(str(_PERGUNTAS_FID.get(k, k))), html.escape(str(v or "-"))]
        for k, v in fid.items()
    ]
    t_fid = Table(linhas_fid, colWidths=[12*cm, 5*cm])
    t_fid.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_fid)
    story.append(Spacer(1, 0.3*cm))

    # Programa de Integridade
    pi_dim = dims.get("programa_integridade") or {}
    story.append(Paragraph("Programa de Integridade", _ESTILO_H2))
    story.append(Paragraph(
        "Empresa Pro-Etica (CGU): " + _BOOL_PT.get(pi_dim.get("pro_etica"), "-"),
        _ESTILO_CORPO
    ))
    story.append(Paragraph(
        "PI obrigatorio (Decreto 12.304/2024 - Grande Vulto): "
        + _BOOL_PT.get(pi_dim.get("obrigatorio"), "-"),
        _ESTILO_CORPO
    ))
    story.append(Spacer(1, 0.3*cm))

    # Parecer
    story.append(Paragraph("Parecer de Integridade", _ESTILO_H2))
    story.append(Paragraph(html.escape(str(parecer.get("resumo") or "-")), _ESTILO_CORPO))
    story.append(Spacer(1, 0.2*cm))
    for bl in (parecer.get("base_legal") or []):
        if bl:
            story.append(Paragraph(f"- {html.escape(str(bl))}", _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Recomendação
    story.append(Paragraph("Recomendação ao Gestor", _ESTILO_H2))
    story.append(Paragraph(html.escape(str(parecer.get("recomendacao") or "-")), _ESTILO_CORPO))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(f"Validade do FID: {html.escape(str(parecer.get('validade_fid') or '12 meses'))}", _ESTILO_PEQUENO))
    story.append(Paragraph(
        "Gerado por IA-Licita - RM Vértice Digital. Sujeito a verificação humana. "
        "Não substitui parecer jurídico.",
        _ESTILO_PEQUENO
    ))

    doc.build(story, onFirstPage=_rodape_todas_paginas, onLaterPages=_rodape_todas_paginas)
    return buf.getvalue()
