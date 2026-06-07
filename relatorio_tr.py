# relatorio_tr.py
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

_LABEL_DIMENSAO_SERVICO = {
    "descricao_objeto":         "Descrição do Objeto",
    "fundamentacao":            "Fundamentação da Necessidade",
    "requisitos_tecnicos":      "Requisitos Técnicos",
    "modelo_execucao":          "Modelo de Execução",
    "modelo_gestao":            "Modelo de Gestão",
    "criterio_medicao":         "Critério de Medição e Pagamento",
    "criterio_julgamento":      "Critério de Julgamento",
    "estimativa_preco":         "Estimativa de Preços",
    "qualificacao_habilitacao": "Qualificação e Habilitação",
}

_LABEL_DIMENSAO_BEM = {
    "especificacao_tecnica":    "Especificação Técnica",
    "justificativa_quantidade": "Justificativa de Quantidade",
    "qualificacao_tecnica":     "Qualificação Técnica",
    "garantia_assistencia":     "Garantia e Assistência Técnica",
    "condicoes_entrega":        "Condições de Entrega",
    "criterio_julgamento":      "Critério de Julgamento",
    "estimativa_preco":         "Estimativa de Preços",
    "sustentabilidade":         "Sustentabilidade",
}

_LABEL_DIMENSAO_TIC = {
    "alinhamento_pdtic":    "Alinhamento ao PDTIC",
    "analise_viabilidade":  "Análise de Viabilidade (AVC)",
    "solucao_ti":           "Solução de TI",
    "criterios_aceite_ans": "Critérios de Aceite e ANS/SLA",
    "equipe_tecnica":       "Equipe Técnica (INTECTI)",
    "seguranca_lgpd":       "Segurança da Informação e LGPD",
    "modelo_execucao":      "Modelo de Execução",
    "transicao_contratual": "Transição Contratual",
    "estimativa_preco":     "Estimativa de Preços",
}

_LABEL_DIMENSAO_POR_TIPO = {
    "servico": _LABEL_DIMENSAO_SERVICO,
    "bem":     _LABEL_DIMENSAO_BEM,
    "tic":     _LABEL_DIMENSAO_TIC,
}

_TIPO_LABEL = {
    "servico": "Serviço",
    "bem":     "Bem / Material",
    "tic":     "Serviço de TIC",
}

_estilos_base   = getSampleStyleSheet()
_ESTILO_TITULO  = ParagraphStyle("tr_titulo", parent=_estilos_base["Title"],   fontSize=16, spaceAfter=4)
_ESTILO_H1      = ParagraphStyle("tr_h1",     parent=_estilos_base["Heading1"])
_ESTILO_H2      = ParagraphStyle("tr_h2",     parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO   = ParagraphStyle("tr_corpo",  parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQUENO = ParagraphStyle("tr_peq",    parent=_estilos_base["Normal"],   fontSize=8, textColor=colors.grey)
_ESTILO_BADGE   = ParagraphStyle("tr_badge",  parent=_estilos_base["Normal"],   fontSize=14, textColor=colors.white, alignment=1)


def gerar_pdf(
    nome_objeto: str,
    tipo_objeto: str,
    parecer: dict,
) -> bytes:
    """Gera PDF do parecer de Termo de Referência. Retorna bytes do PDF."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm,
    )
    story = []
    tipo_label = _TIPO_LABEL.get(tipo_objeto, tipo_objeto)

    # Cabeçalho
    story.append(Paragraph("IA-Licita — RM Vértice Digital", _ESTILO_TITULO))
    story.append(Paragraph("Auditoria de Termo de Referência", _ESTILO_H1))
    story.append(Paragraph("IN SEGES/MGI 81/2022 · Lei 14.133/2021, art. 6º, XXIII", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Tipo de objeto: {html.escape(tipo_label)}", _ESTILO_PEQUENO))
    story.append(Paragraph(f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _ESTILO_PEQUENO))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Objeto analisado
    story.append(Paragraph("Objeto Analisado", _ESTILO_H2))
    story.append(Paragraph(html.escape(str(nome_objeto)), _ESTILO_CORPO))
    story.append(Spacer(1, 0.3*cm))

    # Adequação geral — badge colorido
    adequacao = str(parecer.get("adequacao_geral") or "INADEQUADO").strip().upper()
    cor = _COR_ADEQUACAO.get(adequacao, colors.grey)
    story.append(Paragraph("Adequação Geral", _ESTILO_H2))
    t_adeq = Table(
        [[Paragraph(f"<b>{html.escape(adequacao)}</b>", _ESTILO_BADGE)]],
        colWidths=[17*cm],
    )
    t_adeq.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 10),
    ]))
    story.append(t_adeq)
    story.append(Spacer(1, 0.4*cm))

    # Análise por dimensão
    story.append(Paragraph("Análise por Dimensão", _ESTILO_H2))
    label_map = _LABEL_DIMENSAO_POR_TIPO.get(tipo_objeto, {})
    dims = parecer.get("dimensoes") or {}
    for chave, label in label_map.items():
        dim = dims.get(chave) or {}
        status = (dim.get("status") or "ok").lower()
        cor_s = _COR_STATUS.get(status, "#000000")
        icone = {"ok": "OK", "alerta": "ALERTA", "critico": "CRITICO"}.get(status, "-")
        story.append(Paragraph(
            f"<font color='{cor_s}'><b>[{icone}] {html.escape(label)}</b></font>: "
            f"{html.escape(str(dim.get('descricao') or '-'))}",
            _ESTILO_CORPO,
        ))
    story.append(Spacer(1, 0.3*cm))

    # Pontos críticos
    criticos = parecer.get("pontos_criticos") or []
    if criticos:
        story.append(Paragraph("Pontos Críticos", _ESTILO_H2))
        for i, ponto in enumerate(criticos, 1):
            story.append(Paragraph(f"{i}. {html.escape(str(ponto or ''))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3*cm))

    # Recomendações
    recs = parecer.get("recomendacoes") or []
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
        "Gerado por IA-Licita — RM Vértice Digital. Sujeito a verificação humana. "
        "Não substitui parecer jurídico.",
        _ESTILO_PEQUENO,
    ))

    doc.build(story)
    return buf.getvalue()
