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

from ia_reabilitacao import TIPOS_SANCAO as _LABEL_SANCAO
import disclaimers  # >>> DISCLAIMER (1/4): importa os textos centralizados

_COR_PARECER = {
    "ELEGÍVEL":               colors.HexColor(_COR_STATUS["ok"]),
    "ELEGÍVEL COM RESSALVAS": colors.HexColor(_COR_STATUS["alerta"]),
    "INELEGÍVEL":             colors.HexColor(_COR_STATUS["critico"]),
}

_estilos    = getSampleStyleSheet()
_TITULO     = ParagraphStyle("reab_titulo", parent=_estilos["Title"],   fontSize=16, spaceAfter=4)
_H1         = ParagraphStyle("reab_h1",     parent=_estilos["Heading1"])
_H2         = ParagraphStyle("reab_h2",     parent=_estilos["Heading2"], fontSize=12, spaceAfter=3)
_CORPO      = ParagraphStyle("reab_corpo",  parent=_estilos["Normal"],   fontSize=10, spaceAfter=3)
_PEQUENO    = ParagraphStyle("reab_peq",    parent=_estilos["Normal"],   fontSize=8,  textColor=colors.grey)
_BADGE      = ParagraphStyle("reab_badge",  parent=_estilos["Normal"],   fontSize=14, textColor=colors.white, alignment=1)
_TITULO_REQ = ParagraphStyle("reab_req_t",  parent=_estilos["Title"],    fontSize=14, alignment=1, spaceAfter=6)
_SECAO      = ParagraphStyle("reab_secao",  parent=_estilos["Heading2"], fontSize=11, spaceAfter=4)
_CORPO_REQ  = ParagraphStyle("reab_corpo_r", parent=_estilos["Normal"],  fontSize=10, spaceAfter=6, leading=14)

# >>> DISCLAIMER (2/4): estilo do rodapé fixo + funções que o desenham em CADA página.
_ESTILO_RODAPE = ParagraphStyle(
    "reab_rodape",
    parent=_estilos["Normal"],
    fontSize=7,
    leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)


def _desenhar_rodape(canvas, doc, texto: str):
    """Desenha um disclaimer no rodapé de TODAS as páginas."""
    canvas.saveState()
    largura, _altura = A4
    p = Paragraph(texto, _ESTILO_RODAPE)
    # margem lateral varia entre as duas funções (2cm no técnico, 3cm na minuta);
    # usamos 2cm como base segura — o texto centraliza e cabe nos dois casos.
    largura_util = largura - 4 * cm
    p.wrap(largura_util, 2 * cm)
    p.drawOn(canvas, 2 * cm, 1.0 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(largura - 2 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


def _rodape_tecnico(canvas, doc):
    _desenhar_rodape(canvas, doc, disclaimers.TEXTO_PDF)


def _rodape_minuta(canvas, doc):
    _desenhar_rodape(canvas, doc, disclaimers.TEXTO_PDF_MINUTA)


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
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm,  # >>> DISCLAIMER
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
    _tipo_label = _LABEL_SANCAO.get(_tipo_key, _tipo_key)
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
    _aviso_par_reab = parecer.get("_aviso_parecer")
    if _aviso_par_reab is not None:
        story.append(Paragraph(
            f"⚠ Valor de parecer não reconhecido: '{html.escape(str(_aviso_par_reab))}'"
            " — registrado como INELEGÍVEL. Verifique manualmente.",
            _CORPO,
        ))
        story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Condições Art. 163, Par. Único (5 condições cumulativas)", _H2))
    for cond in (parecer.get("condicoes_avaliadas") or []):
        if not cond:
            continue
        _st = str(cond.get("status") or "AUSENTE").strip().upper()
        _ic = _st
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
        "Gerado por IA-Licita - RM Vertice Digital.",
        _PEQUENO,
    ))

    doc.build(story, onFirstPage=_rodape_tecnico, onLaterPages=_rodape_tecnico)
    return buf.getvalue()


def gerar_minuta_requerimento(
    cnpj: str,
    dados_empresa: dict,
    dados_sancao: dict,
    parecer: dict,  # accepted for API symmetry with gerar_relatorio_tecnico; not used
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=3*cm, rightMargin=3*cm, topMargin=3*cm, bottomMargin=2.5*cm,
    )
    story = []

    _tipo_key   = str(dados_sancao.get("tipo_sancao") or "")
    _tipo_label = _LABEL_SANCAO.get(_tipo_key, _tipo_key)
    _razao      = html.escape(str(dados_empresa.get("razao_social") or "REQUERENTE"))
    _cnpj_fmt   = _fmt_cnpj(cnpj)
    _orgao      = html.escape(str(dados_sancao.get("orgao") or "não identificado"))
    _data_apl   = html.escape(str(dados_sancao.get("data_aplicacao") or "não informada"))

    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph("<b>REQUERIMENTO DE REABILITAÇÃO</b>", _TITULO_REQ))
    story.append(Paragraph(
        "Fundamento: Art. 163, Parágrafo Único, Lei 14.133/2021", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey, spaceAfter=12))

    story.append(Paragraph(
        f"<b>{_razao}</b>, pessoa jurídica de direito privado, inscrita no CNPJ sob "
        f"n.º {_cnpj_fmt}, vem respeitosamente à presença de Vossa Senhoria, autoridade "
        "competente do órgão abaixo identificado, com fundamento no Art. 163, Parágrafo "
        "Único, da Lei n.º 14.133/2021, requerer sua <b>REABILITAÇÃO</b>.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>I — DOS FATOS</b>", _SECAO))
    story.append(Paragraph(
        f"A requerente foi objeto de sanção de <b>{html.escape(_tipo_label)}</b>, "
        f"aplicada pelo órgão/entidade <b>{_orgao}</b>, em {_data_apl}.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>II — DO DIREITO</b>", _SECAO))
    story.append(Paragraph(
        "O Art. 163, Parágrafo Único, da Lei n.º 14.133/2021, autoriza a reabilitação "
        "do fornecedor sancionado mediante o cumprimento cumulativo das seguintes condições:",
        _CORPO_REQ,
    ))
    _conds_legais = [
        ("I",   "Reparação integral do dano causado à Administração Pública;"),
        ("II",  "Pagamento de multa eventualmente aplicada;"),
        ("III", "Transcurso do prazo mínimo de 1 (um) ano, no caso do Art. 156, III, "
                "ou de 3 (três) anos, no caso do Art. 156, IV;"),
        ("IV",  "Cumprimento das condições de reabilitação definidas no ato punitivo;"),
        ("V",   "Análise jurídica prévia, com posicionamento conclusivo quanto ao "
                "cumprimento dos requisitos."),
    ]
    for _n, _desc in _conds_legais:
        story.append(Paragraph(f"{_n}. {html.escape(_desc)}", _CORPO_REQ))

    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "A requerente demonstra o cumprimento das condições acima, conforme documentação "
        "comprobatória anexa e Relatório Técnico de Elegibilidade.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("<b>III — DO PEDIDO</b>", _SECAO))
    story.append(Paragraph(
        f"Ante o exposto, requer seja deferida sua <b>REABILITAÇÃO</b> nos termos do "
        "Art. 163, Parágrafo Único, da Lei n.º 14.133/2021, com o consequente "
        "levantamento da restrição imposta.",
        _CORPO_REQ,
    ))
    story.append(Spacer(1, 1*cm))

    story.append(Paragraph(
        "_________________, _____ de _________________ de _______.", _CORPO_REQ
    ))
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("________________________________________", _CORPO_REQ))
    story.append(Paragraph(f"{_razao}", _CORPO_REQ))
    story.append(Paragraph(f"CNPJ: {_cnpj_fmt}", _CORPO_REQ))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Minuta gerada por IA-Licita - RM Vertice Digital.",
        _PEQUENO,
    ))

    # >>> DISCLAIMER (4/4): rodapé fixo de minuta em todas as páginas
    doc.build(story, onFirstPage=_rodape_minuta, onLaterPages=_rodape_minuta)
    return buf.getvalue()
