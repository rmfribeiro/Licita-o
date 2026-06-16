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
from ia_utils import (
    COR_STATUS_HEX as _COR_STATUS,
    as_list as _as_list,
    fmt_brl as _fmt_brl,
    safe_float as _safe_float,
    fmt_brl_opcional as _fmt_brl_opcional,
)
from ia_sancoes import LABEL_SANCAO as _LABEL_SANCAO
import disclaimers  # >>> DISCLAIMER (1/3): importa os textos centralizados

_COR_SANCAO = {
    "advertencia":  colors.HexColor("#F39C12"),
    "multa":        colors.HexColor("#E67E22"),
    "impedimento":  colors.HexColor(_COR_STATUS["critico"]),
    "inidoneidade": colors.HexColor("#8E44AD"),
}

_COR_GRAVIDADE = {
    "LEVE":  colors.HexColor(_COR_STATUS["ok"]),
    "MÉDIO": colors.HexColor("#F39C12"),
    "GRAVE": colors.HexColor(_COR_STATUS["critico"]),
}

_estilos_base    = getSampleStyleSheet()
_ESTILO_TITULO   = ParagraphStyle("sanc_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1       = ParagraphStyle("sanc_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2       = ParagraphStyle("sanc_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO    = ParagraphStyle("sanc_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO  = ParagraphStyle("sanc_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE    = ParagraphStyle("sanc_badge",   parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_ESTILO_ALERTA   = ParagraphStyle("sanc_alerta",  parent=_estilos_base["Normal"],   fontSize=10, textColor=colors.HexColor(_COR_STATUS["critico"]))
_ESTILO_MINUTA   = ParagraphStyle(
    "sanc_minuta",
    parent=_estilos_base["Normal"],
    fontSize=10,
    spaceAfter=4,
    backColor=colors.HexColor("#F5F5F5"),
    leftIndent=12,
    rightIndent=12,
)

# >>> DISCLAIMER (2/3): estilo do rodapé fixo e função que o desenha em CADA página.
_ESTILO_RODAPE = ParagraphStyle(
    "sanc_rodape",
    parent=_estilos_base["Normal"],
    fontSize=7,
    leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)

_ESTILO_AVISO_MINUTA = ParagraphStyle(
    "sanc_aviso_minuta",
    parent=_estilos_base["Normal"],
    fontSize=9,
    leading=11,
    textColor=colors.white,
    backColor=colors.HexColor("#C0392B"),
    borderPadding=6,
    spaceBefore=4,
    spaceAfter=8,
)


def _rodape_todas_paginas(canvas, doc):
    """Desenha o disclaimer de minuta no rodapé de TODAS as páginas.

    Chamado automaticamente pelo reportlab em cada página, via os
    parâmetros onFirstPage / onLaterPages do doc.build().
    """
    canvas.saveState()
    largura, _altura = A4
    # Paragraph permite quebra de linha automática dentro da largura da página
    p = Paragraph(disclaimers.TEXTO_PDF_MINUTA, _ESTILO_RODAPE)
    largura_util = largura - 4 * cm  # respeita as margens de 2cm de cada lado
    p.wrap(largura_util, 2 * cm)
    p.drawOn(canvas, 2 * cm, 1.0 * cm)  # desenha a ~1cm da borda inferior
    # número da página, à direita
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(largura - 2 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _fmt_cnpj(cnpj: str) -> str:
    d = "".join(c for c in str(cnpj) if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return cnpj


def gerar_pdf(dados_formulario: dict, parecer: dict, minuta: str) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,  # >>> DISCLAIMER: +0.5cm p/ caber o rodapé
    )
    story = []

    # ── Cabeçalho ────────────────────────────────────────────────────────────
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Dosimetria de Sanções Administrativas", _ESTILO_H1))
    story.append(Paragraph(
        "Arts. 156-159 e 178 — Lei 14.133/2021",
        _ESTILO_PEQUENO,
    ))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}",
        _ESTILO_PEQUENO,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # ── Identificação ────────────────────────────────────────────────────────
    story.append(Paragraph("Identificação", _ESTILO_H2))
    linhas_id = [
        ["CNPJ do Fornecedor",     html.escape(_fmt_cnpj(str(dados_formulario.get("cnpj") or "-")))],
        ["Número do Contrato",     html.escape(str(dados_formulario.get("numero_contrato") or "-"))],
        ["Valor do Contrato",      _fmt_brl_opcional(dados_formulario.get("valor_contrato"))],
        ["Reincidência",           html.escape(str(dados_formulario.get("reincidencia") or "-"))],
        ["Órgão/Entidade",         html.escape(str(dados_formulario.get("orgao") or "-"))],
        ["Autoridade Competente",  html.escape(str(dados_formulario.get("autoridade") or "-"))],
    ]
    t_id = Table(linhas_id, colWidths=[5 * cm, 12 * cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_id)
    story.append(Spacer(1, 0.4 * cm))

    # ── Badge da sanção ───────────────────────────────────────────────────────
    enq = parecer.get("enquadramento") or {}
    tipo = str(enq.get("tipo_sancao") or "multa").lower()
    label_sancao = _LABEL_SANCAO.get(tipo, tipo.title())
    cor_badge = _COR_SANCAO.get(tipo, colors.grey)

    story.append(Paragraph("Sanção Sugerida", _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(label_sancao.upper())}</b>", _ESTILO_BADGE)]],
        colWidths=[17 * cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"<b>Artigo:</b> {html.escape(str(enq.get('artigo') or '-'))}",
        _ESTILO_CORPO,
    ))
    story.append(Paragraph(
        f"<b>Justificativa:</b> {html.escape(str(enq.get('justificativa') or '-'))}",
        _ESTILO_CORPO,
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Fatos apurados ────────────────────────────────────────────────────────
    fatos = str(parecer.get("fatos_apurados") or "-")
    story.append(Paragraph("Fatos Apurados", _ESTILO_H2))
    story.append(Paragraph(html.escape(fatos), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3 * cm))

    # ── Condutas identificadas ────────────────────────────────────────────────
    condutas = _as_list(parecer.get("condutas_identificadas"))
    if condutas:
        story.append(Paragraph("Condutas Identificadas", _ESTILO_H2))
        for c in condutas:
            if c:
                story.append(Paragraph(f"• {html.escape(str(c))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    # ── Tabela de dosimetria ──────────────────────────────────────────────────
    dos = parecer.get("dosimetria") or {}
    nivel = str(dos.get("nivel_gravidade") or "MÉDIO").strip().upper()
    cor_nivel = _COR_GRAVIDADE.get(nivel, colors.grey)
    agravantes = "; ".join(str(a) for a in _as_list(dos.get("agravantes")) if a) or "—"
    atenuantes = "; ".join(str(a) for a in _as_list(dos.get("atenuantes")) if a) or "—"

    story.append(Paragraph("Dosimetria", _ESTILO_H2))
    linhas_dos = [
        ["Nível de Gravidade", Paragraph(f"<b>{html.escape(nivel)}</b>",
                                         ParagraphStyle("nv", parent=_ESTILO_CORPO,
                                                        textColor=cor_nivel))],
        ["Agravantes",  html.escape(agravantes)],
        ["Atenuantes",  html.escape(atenuantes)],
    ]
    if tipo == "multa":
        pct = _safe_float(dos.get("percentual_multa"))
        val = _safe_float(dos.get("valor_multa_estimado"))
        linhas_dos.append(["% da Multa", f"{pct:.1f}%"])
        if val > 0:
            linhas_dos.append(["Valor Estimado", _fmt_brl(val)])
    elif tipo in ("impedimento", "inidoneidade"):
        prazo = dos.get("prazo_sancao")
        linhas_dos.append(["Prazo da Sanção", f"{prazo} ano(s)" if prazo else "—"])

    t_dos = Table(linhas_dos, colWidths=[5 * cm, 12 * cm])
    t_dos.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t_dos)
    story.append(Spacer(1, 0.4 * cm))

    # ── Alerta criminal ───────────────────────────────────────────────────────
    alerta = parecer.get("alerta_criminal") or {}
    if alerta.get("configura_crime"):
        story.append(Paragraph("⚠ ALERTA — Possível Crime (Art. 178, Lei 14.133/2021)", _ESTILO_ALERTA))
        if alerta.get("artigo_178"):
            story.append(Paragraph(
                f"<b>Artigo:</b> {html.escape(str(alerta['artigo_178']))}",
                _ESTILO_ALERTA,
            ))
        if alerta.get("descricao_conduta"):
            story.append(Paragraph(
                f"<b>Conduta:</b> {html.escape(str(alerta['descricao_conduta']))}",
                _ESTILO_ALERTA,
            ))
        if alerta.get("recomendacao"):
            story.append(Paragraph(
                f"<b>Recomendação:</b> {html.escape(str(alerta['recomendacao']))}",
                _ESTILO_ALERTA,
            ))
        story.append(Spacer(1, 0.3 * cm))

    # ── Base legal ────────────────────────────────────────────────────────────
    base_legal = _as_list(parecer.get("base_legal"))
    if base_legal:
        story.append(Paragraph("Base Legal", _ESTILO_H2))
        for bl in base_legal:
            if bl:
                story.append(Paragraph(f"• {html.escape(str(bl))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.4 * cm))

    # ── Seção 2: Minuta ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#2C3E50"), spaceAfter=6))
    story.append(Paragraph(
        "MINUTA — Para revisão e assinatura",
        ParagraphStyle("sanc_minuta_titulo", parent=_ESTILO_H1,
                       textColor=colors.HexColor("#2C3E50")),
    ))

    # >>> DISCLAIMER (3/3): aviso forte e destacado logo abaixo do título da minuta,
    #     dentro do corpo do documento (além do rodapé fixo de todas as páginas).
    story.append(Paragraph(disclaimers.TEXTO_PDF_MINUTA, _ESTILO_AVISO_MINUTA))
    story.append(Spacer(1, 0.2 * cm))

    if minuta:
        for linha in minuta.split("\n"):
            story.append(Paragraph(html.escape(linha) if linha.strip() else " ", _ESTILO_MINUTA))
    else:
        story.append(Paragraph(
            "(Minuta não disponível — a 2ª chamada de IA não retornou resultado.)",
            _ESTILO_PEQUENO,
        ))

    story.append(Spacer(1, 0.4 * cm))

    # ── Rodapé final (texto adicional no fim do conteúdo) ─────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por IA-Licita — RM Vértice Digital.",
        _ESTILO_PEQUENO,
    ))

    # >>> DISCLAIMER: registra a função de rodapé fixo em todas as páginas
    doc.build(
        story,
        onFirstPage=_rodape_todas_paginas,
        onLaterPages=_rodape_todas_paginas,
    )
    return buf.getvalue()
