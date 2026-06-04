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

_COR_RISCO = {
    "ALTO": colors.HexColor("#C0392B"),
    "MÉDIO": colors.HexColor("#E67E22"),
    "BAIXO": colors.HexColor("#F39C12"),
    "SEM RISCO IDENTIFICADO": colors.HexColor("#27AE60"),
}
_COR_STATUS = {"ok": "#27AE60", "alerta": "#E67E22", "critico": "#C0392B"}
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


def _fmt_cnpj(cnpj: str) -> str:
    c = cnpj.replace(".", "").replace("/", "").replace("-", "")
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" if len(c) == 14 else cnpj


def _fmt_brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(cnpj: str, valor_contrato: float, dados: dict, fid: dict, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=estilos["Title"], fontSize=16, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=estilos["Heading2"], fontSize=12, spaceAfter=3)
    corpo = ParagraphStyle("corpo", parent=estilos["Normal"], fontSize=10, spaceAfter=3)
    pequeno = ParagraphStyle("peq", parent=estilos["Normal"], fontSize=8, textColor=colors.grey)

    story = []

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", titulo))
    story.append(Paragraph("Due Diligence de Integridade (DDI)", estilos["Heading1"]))
    story.append(Paragraph("Portaria SEGES/ME 8.678/2021, art. 2 III - Decreto 12.304/2024", pequeno))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y as %H:%M')}", pequeno))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Identificação
    story.append(Paragraph("Identificação do Licitante", h2))
    linhas_id = [
        ["Razão Social", dados.get("razao_social", "-")],
        ["CNPJ", _fmt_cnpj(cnpj)],
        ["Situação Cadastral", dados.get("situacao", "-")],
        ["Porte", dados.get("porte", "-")],
        ["CNAE Principal", dados.get("cnae", "-")],
        ["Data de Abertura", dados.get("data_abertura", "-")],
        ["Valor do Contrato", _fmt_brl(valor_contrato)],
        ["Grande Vulto (> R$ 239M)", "Sim" if dados.get("grande_vulto") else "Não"],
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
    socios = dados.get("socios", [])
    if socios:
        story.append(Paragraph("Quadro Societário", h2))
        for s in socios:
            story.append(Paragraph(f"- {html.escape(str(s.get('nome', '-')))} -- {html.escape(str(s.get('cargo', '-')))}", corpo))
        story.append(Spacer(1, 0.3*cm))

    # Índice de risco
    risco = str(parecer.get("risco_geral") or "SEM RISCO IDENTIFICADO").strip()
    cor_risco = _COR_RISCO.get(risco, colors.grey)
    story.append(Paragraph("Índice de Risco Geral", h2))
    t_risco = Table(
        [[Paragraph(f"<b>{html.escape(str(risco))}</b>",
                    ParagraphStyle("r", fontSize=14, textColor=colors.white, alignment=1))]],
        colWidths=[17*cm]
    )
    t_risco.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_risco),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(t_risco)
    story.append(Spacer(1, 0.4*cm))

    # Risco por dimensão
    story.append(Paragraph("Análise por Dimensão", h2))
    dims = parecer.get("dimensoes", {})
    for chave, label in _LABEL_DIMENSAO.items():
        dim = dims.get(chave, {})
        status = dim.get("status", "ok")
        cor = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor}'><b>[{icone}] {html.escape(label)}</b></font>: {html.escape(str(dim.get('descricao', '-')))}",
            corpo
        ))
        for achado in dim.get("achados", []):
            story.append(Paragraph(
                f"  -> <b>{html.escape(str(achado.get('fonte', '')))}</b>: "
                f"{html.escape(str(achado.get('descricao', '')))} "
                f"(gravidade: {html.escape(str(achado.get('gravidade', '')))})",
                corpo
            ))
    story.append(Spacer(1, 0.3*cm))

    # FID
    story.append(Paragraph("Formulário de Integridade e Diligência (FID)", h2))
    linhas_fid = [["Critério", "Resposta"]] + [
        [_PERGUNTAS_FID.get(k, k), v] for k, v in fid.items()
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
    pi_dim = dims.get("programa_integridade", {})
    story.append(Paragraph("Programa de Integridade", h2))
    story.append(Paragraph(
        f"Empresa Pro-Etica (CGU): {'Sim' if pi_dim.get('pro_etica') else 'Não'}",
        corpo
    ))
    story.append(Paragraph(
        f"PI obrigatorio (Decreto 12.304/2024 - Grande Vulto): "
        f"{'Sim' if pi_dim.get('obrigatorio') else 'Não'}",
        corpo
    ))
    story.append(Spacer(1, 0.3*cm))

    # Parecer
    story.append(Paragraph("Parecer de Integridade", h2))
    story.append(Paragraph(html.escape(str(parecer.get("resumo", "-"))), corpo))
    story.append(Spacer(1, 0.2*cm))
    for bl in parecer.get("base_legal", []):
        story.append(Paragraph(f"- {html.escape(str(bl))}", corpo))
    story.append(Spacer(1, 0.3*cm))

    # Recomendação
    story.append(Paragraph("Recomendação ao Gestor", h2))
    story.append(Paragraph(html.escape(str(parecer.get("recomendacao", "-"))), corpo))
    story.append(Spacer(1, 0.4*cm))

    # Rodapé
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(f"Validade do FID: {html.escape(str(parecer.get('validade_fid', '12 meses')))}", pequeno))
    story.append(Paragraph(
        "Gerado por IA-Licita - RM Vértice Digital. Sujeito a verificação humana. "
        "Não substitui parecer jurídico.",
        pequeno
    ))

    doc.build(story)
    return buf.getvalue()
