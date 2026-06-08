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
from ia_integridade import COR_MATURIDADE_HEX as _COR_MATURIDADE_HEX
from ia_pi_empresas import DIMENSOES_PI, HIPOTESES_POR_TIPO, QUESTOES_PI, TIPOS_ENTIDADE

_COR_MATURIDADE = {k: colors.HexColor(v) for k, v in _COR_MATURIDADE_HEX.items()}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("pi_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1      = ParagraphStyle("pi_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2      = ParagraphStyle("pi_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("pi_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("pi_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE   = ParagraphStyle("pi_badge",   parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def gerar_pdf(
    cnpj: str,
    razao_social: str,
    hipotese: str,
    parecer: dict,
    tipo_entidade: str = "empresa_privada",
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Avaliação do Programa de Integridade (PI)", _ESTILO_H1))
    story.append(Paragraph("Decreto 12.304/2024 · Lei 14.133/2021 · Lei 12.846/2013", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação
    story.append(Paragraph("Identificação da Empresa", _ESTILO_H2))
    _label_tipo = TIPOS_ENTIDADE.get(tipo_entidade, tipo_entidade)
    _label_hip  = (HIPOTESES_POR_TIPO.get(tipo_entidade) or {}).get(hipotese, hipotese)
    linhas_id = [
        ["Razão Social",     html.escape(str(razao_social or "-"))],
        ["CNPJ",             _fmt_cnpj(cnpj)],
        ["Tipo de Entidade", html.escape(_label_tipo)],
        ["Hipótese Avaliada", html.escape(str(_label_hip))],
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

    # Score geral + nível de maturidade
    scores = parecer.get("scores") or {}
    score_geral = scores.get("geral", 0.0)
    nivel = str(scores.get("nivel") or "INEXISTENTE").strip().upper()
    cor_nivel = _COR_MATURIDADE.get(nivel, colors.grey)

    story.append(Paragraph("Score Geral de Aderência", _ESTILO_H2))
    t_badge = Table(
        [[Paragraph(
            f"<b>{html.escape(nivel)} — {score_geral:.0f}/100</b>",
            _ESTILO_BADGE,
        )]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_nivel),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.4*cm))

    # Score por dimensão
    story.append(Paragraph("Score por Dimensão", _ESTILO_H2))
    por_dimensao = scores.get("por_dimensao") or {}
    linhas_dim = [["Dimensão", "Score"]]
    for dim_key, (dim_label, _) in DIMENSOES_PI.items():
        s = por_dimensao.get(dim_key, 0.0)
        linhas_dim.append([html.escape(dim_label), f"{s:.0f}/100"])
    t_dim = Table(linhas_dim, colWidths=[13*cm, 4*cm])
    t_dim.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
    ]))
    story.append(t_dim)
    story.append(Spacer(1, 0.4*cm))

    # Conclusão para a hipótese
    conclusao = str(parecer.get("conclusao_hipotese") or "-")
    story.append(Paragraph("Conclusão para a Hipótese", _ESTILO_H2))
    story.append(Paragraph(html.escape(conclusao), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos") or []
    if criticos:
        story.append(Paragraph("Pontos Críticos", _ESTILO_H2))
        for i, ponto in enumerate(criticos, 1):
            if ponto:
                story.append(Paragraph(f"{i}. {html.escape(str(ponto))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Análise por dimensão (achados e recomendações)
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    dims_qualitativo = parecer.get("dimensoes") or {}
    for dim_key, (dim_label, params) in DIMENSOES_PI.items():
        dim = dims_qualitativo.get(dim_key) or {}
        sintese = str(dim.get("sintese") or "-")
        score_d = por_dimensao.get(dim_key, 0.0)
        story.append(Paragraph(
            f"<b>{html.escape(dim_label)} ({score_d:.0f}/100):</b> {html.escape(sintese)}",
            _ESTILO_CORPO,
        ))
        params_qualit = dim.get("parametros") or {}
        for p in params:
            p_data = params_qualit.get(p) or {}
            rotulo = QUESTOES_PI.get(p, p)
            for achado in (p_data.get("achados") or []):
                if achado:
                    story.append(Paragraph(
                        f"  • {html.escape(rotulo)}: {html.escape(str(achado))}",
                        _ESTILO_CORPO,
                    ))
            for rec in (p_data.get("recomendacoes") or []):
                if rec:
                    story.append(Paragraph(
                        f"  → Recomendação: {html.escape(str(rec))}",
                        _ESTILO_CORPO,
                    ))
    story.append(Spacer(1, 0.3*cm))

    # Recomendações gerais
    recs = parecer.get("recomendacoes") or []
    if recs:
        story.append(Paragraph("Recomendações ao Gestor", _ESTILO_H2))
        for i, rec in enumerate(recs, 1):
            if rec:
                story.append(Paragraph(f"{i}. {html.escape(str(rec))}", _ESTILO_CORPO))
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
