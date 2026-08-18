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
import ia_utils
import ia_fid
import branding
from ia_fid import FASES_PROCESSO, RESULTADO_NAO_AVALIADO
import disclaimers  # >>> DISCLAIMER (1/3): importa os textos centralizados

_estilos_base  = getSampleStyleSheet()
_ESTILO_TITULO = ParagraphStyle("fid_titulo",  parent=_estilos_base["Title"],    fontSize=16, spaceAfter=4)
_ESTILO_H1     = ParagraphStyle("fid_h1",      parent=_estilos_base["Heading1"])
_ESTILO_H2     = ParagraphStyle("fid_h2",      parent=_estilos_base["Heading2"], fontSize=12, spaceAfter=3)
_ESTILO_CORPO  = ParagraphStyle("fid_corpo",   parent=_estilos_base["Normal"],   fontSize=10, spaceAfter=3)
_ESTILO_PEQNO  = ParagraphStyle("fid_peq",     parent=_estilos_base["Normal"],   fontSize=8,  textColor=colors.grey)
_ESTILO_BADGE  = ParagraphStyle("fid_badge",   parent=_estilos_base["Normal"],   fontSize=13, textColor=colors.white, alignment=1)
_ESTILO_OFICIO = ParagraphStyle("fid_oficio",  parent=_estilos_base["Normal"],   fontSize=9,  spaceAfter=4, leading=14)
_ESTILO_CELULA = ParagraphStyle("fid_celula",  parent=_estilos_base["Normal"],   fontSize=8,  leading=9.5, spaceAfter=0)
_ESTILO_CEL_CAB = ParagraphStyle("fid_cel_cab", parent=_ESTILO_CELULA, textColor=colors.white)
_ESTILO_ID     = ParagraphStyle("fid_id",      parent=_estilos_base["Normal"],   fontSize=9,  leading=10.5, spaceAfter=0)
_ESTILO_RESSALVA = ParagraphStyle(
    "fid_ressalva", parent=_estilos_base["Normal"], fontSize=9, leading=11,
    textColor=colors.HexColor("#7B241C"), backColor=colors.HexColor("#FDEDEC"),
    borderColor=colors.HexColor("#C0392B"), borderWidth=0.7, borderPadding=5,
    spaceBefore=2, spaceAfter=2)

# >>> DISCLAIMER (2/3): estilo do rodapé fixo + função que o desenha em CADA página.
_ESTILO_RODAPE = ParagraphStyle(
    "fid_rodape",
    parent=_estilos_base["Normal"],
    fontSize=7,
    leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)


def _rodape_todas_paginas(canvas, doc):
    """Desenha o disclaimer de minuta no rodapé de TODAS as páginas."""
    canvas.saveState()
    largura, _altura = A4
    p = Paragraph(disclaimers.TEXTO_PDF_MINUTA, _ESTILO_RODAPE)
    largura_util = largura - 4 * cm
    p.wrap(largura_util, 2 * cm)
    p.drawOn(canvas, 2 * cm, 1.0 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.grey)
    canvas.drawRightString(largura - 2 * cm, 0.7 * cm, f"Página {doc.page}")
    canvas.restoreState()


_COR_RESULTADO = {
    "SIM":                  colors.HexColor("#C0392B"),
    "PARCIALMENTE":         colors.HexColor("#F39C12"),
    "NÃO":                  colors.HexColor("#27AE60"),
    RESULTADO_NAO_AVALIADO: colors.HexColor("#808080"),
}
_LABEL_RESULTADO = {
    "SIM":                  "DILIGÊNCIA NECESSÁRIA",
    "NÃO":                  "DILIGÊNCIA DESNECESSÁRIA",
    "PARCIALMENTE":         "DILIGÊNCIA PARCIALMENTE NECESSÁRIA",
    RESULTADO_NAO_AVALIADO: "NÃO AVALIADO",
}

_TEXTO_NAO_AVALIADO = (
    "Este relatório NÃO conclui pela necessidade nem pela desnecessidade de diligência. "
    "A análise não produziu base suficiente para qualquer das duas conclusões — não há, "
    "aqui, juízo favorável ou desfavorável ao licitante. Refaça a análise descrevendo a "
    "situação com mais precisão e anexando os documentos pertinentes."
)


def _fmt_prazo(v) -> str:
    """Prazo ausente e ausente. Nao vira 5."""
    return f"{v} dias" if isinstance(v, int) else "a fixar"


def _rotulo_situacao(d: dict) -> str:
    """Quando a situacao so existe por declaracao, o rotulo diz isso na celula.

    Nao basta trocar 'vencido' por 'pendente': quem le a tabela precisa saber
    POR QUE esta pendente, senao parece hesitacao da analise e nao ausencia de
    prova. Mas a explicacao inteira dentro da celula esticava a linha e deixava
    a coluna ilegivel — a frase completa vai na nota abaixo da tabela.
    """
    sit = html.escape(str(d.get("situacao") or "-"))
    declarada = d.get("_situacao_declarada")
    if not declarada:
        return sit
    return f"{sit} *<br/>(declarado: {html.escape(str(declarada))})"


NOTA_DECLARADO = (
    "* Situação registrada como <b>pendente</b> porque o vício indicado foi apenas "
    "DECLARADO no formulário, sem comprovação documental anexada. O sistema não "
    "constatou o vício: apenas registra o que lhe foi informado."
)

# A conclusao acima e texto livre do modelo e costuma afirmar os vicios como
# constatados. Estas frases sao escritas pelo codigo, nao pelo modelo, e so
# aparecem quando nao houve documento anexado.
#
# SAO DUAS, e a distincao veio de um defeito real (3o teste, versao b): a
# ressalva unica falava de "vicios relatados" e foi colada embaixo de um parecer
# que concluia NAO HAVER vicio nenhum. Aviso que dispara fora de contexto e da
# mesma familia do falso positivo da data — desmoraliza os avisos verdadeiros.
RESSALVA_CONCLUSAO_AFIRMATIVA = (
    "<b>RESSALVA OBRIGATÓRIA À CONCLUSÃO ACIMA:</b> nenhum documento foi anexado a esta "
    "análise. Onde a conclusão diz que um vício foi <i>identificado</i>, <i>constatado</i> "
    "ou <i>verificado</i>, leia-se <b>declarado no formulário e não conferido</b>. O sistema "
    "não teve acesso a documento algum do licitante e não afirma que os vícios existam — "
    "apenas registra que foram relatados. Confira os documentos antes de expedir a diligência."
)

# Esta e a mais importante das duas. O selo verde e a conclusao perigosa deste
# modulo: e a que pode ser usada para seguir em frente. Dizer "nao ha o que
# diligenciar" sem ter aberto documento algum nao e um atestado de regularidade.
RESSALVA_CONCLUSAO_NEGATIVA = (
    "<b>RESSALVA OBRIGATÓRIA À CONCLUSÃO ACIMA:</b> esta conclusão foi formada <b>sem o "
    "exame de documento algum</b> — nenhum foi anexado à análise. Ela significa apenas que "
    "a situação descrita no formulário não apontou vício a diligenciar; <b>NÃO significa que "
    "a documentação do licitante esteja regular, completa ou válida</b>, o que não foi "
    "verificado. Este relatório não autoriza, por si, o prosseguimento do processo."
)


def _ressalva_da_conclusao(resultado: str) -> str:
    """A ressalva tem de dizer respeito ao que a conclusao afirma."""
    if resultado in ("SIM", "PARCIALMENTE"):
        return RESSALVA_CONCLUSAO_AFIRMATIVA
    return RESSALVA_CONCLUSAO_NEGATIVA


def gerar_pdf(dados_licitante: dict, fase: str, parecer: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2.5 * cm,  # >>> DISCLAIMER
    )
    story: list = []

    story.extend(branding.cabecalho_pdf(_ESTILO_TITULO))
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
    # Mesma correcao da tabela de documentos, aplicada aqui depois do 3o teste:
    # string crua nao quebra linha. O objeto de uma licitacao real tem duas ou
    # tres linhas ("Registro de precos para eventual aquisicao de material de
    # expediente, papelaria, suprimentos de informatica...") e vazava para fora
    # da margem da pagina. Nos testes o objeto era curto e o defeito nao
    # aparecia — o campo mais comprido do formulario era o menos testado.
    _id = lambda t: Paragraph(html.escape(str(t)), _ESTILO_ID)
    linhas_id = [
        [_id("Licitante"),          _id(dados_licitante.get("razao_social") or "-")],
        [_id("CNPJ"),               _id(dados_licitante.get("cnpj") or "-")],
        [_id("Nº Edital/Processo"), _id(dados_licitante.get("numero_edital") or "-")],
        [_id("Objeto"),             _id(dados_licitante.get("objeto") or "-")],
        [_id("Órgão"),              _id(dados_licitante.get("orgao") or "-")],
        [_id("Fase"),               _id(fase_label)],
    ]
    t_id = Table(linhas_id, colWidths=[4.5 * cm, 12.5 * cm])
    t_id.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F2F2F2")),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 4),
        ("VALIGN",     (0, 0), (-1, -1), "TOP"),
    ]))
    t_id.hAlign = "LEFT"
    story.append(t_id)
    story.append(Spacer(1, 0.4 * cm))

    _res = str(parecer.get("necessita_diligencia") or RESULTADO_NAO_AVALIADO).strip().upper()
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

    if _res == RESULTADO_NAO_AVALIADO:
        story.append(Paragraph(f"<b>{html.escape(_TEXTO_NAO_AVALIADO)}</b>", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    _aviso_nd = parecer.get("_aviso_nd")
    if _aviso_nd is not None:
        story.append(Paragraph(
            f"⚠ Valor original não reconhecido no retorno da IA: "
            f"'{html.escape(str(_aviso_nd))}'. O resultado acima foi derivado pelo sistema.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2 * cm))

    _div = parecer.get("_divergencia_ia")
    if _div:
        story.append(Paragraph(
            f"⚠ A IA havia concluído '{html.escape(str(_div))}'. O sistema registrou "
            f"'{html.escape(_label_badge)}' por coerência com a lista de documentos a "
            "solicitar. Divergência entre as duas leituras — confira antes de decidir.",
            _ESTILO_CORPO,
        ))
        story.append(Spacer(1, 0.2 * cm))

    _conf = _as_list(parecer.get("_conferencia_oficio"))
    if _conf:
        story.append(Paragraph("Conferência automática da minuta", _ESTILO_H2))
        for _c in _conf:
            if str(_c).strip():
                story.append(Paragraph(f"⚠ {html.escape(str(_c))}", _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    docs = _as_list(parecer.get("documentos_solicitados"))
    if docs:
        story.append(Paragraph("Documentos / Informações a Solicitar", _ESTILO_H2))
        # DEFEITO REAL, pego no 1o teste (17/08/2026): as celulas iam como string
        # crua. String crua no ReportLab NAO quebra linha — transborda e escreve
        # por cima da coluna vizinha. No PDF entregue, "Certidao de Regularidade
        # com o FGTS com validade vigente" atropelou a coluna Situacao e saiu
        # "com vavleidnacdideo vigente". A tabela inteira ficou ilegivel.
        # Paragraph quebra linha dentro da celula.
        _cel = lambda t: Paragraph(html.escape(str(t)), _ESTILO_CELULA)
        linhas_docs: list[list] = [[
            Paragraph("<b>#</b>", _ESTILO_CEL_CAB),
            Paragraph("<b>Documento / Informação</b>", _ESTILO_CEL_CAB),
            Paragraph("<b>Situação</b>", _ESTILO_CEL_CAB),
            Paragraph("<b>Fundamento Legal</b>", _ESTILO_CEL_CAB),
            Paragraph("<b>Prazo</b>", _ESTILO_CEL_CAB),
        ]]
        for i, d in enumerate(docs, 1):
            if not isinstance(d, dict):
                continue
            linhas_docs.append([
                _cel(i),
                _cel(d.get("documento") or "-"),
                # ja vem escapado por _rotulo_situacao, que precisa do <br/>
                Paragraph(_rotulo_situacao(d), _ESTILO_CELULA),
                _cel(d.get("fundamento_legal") or "-"),
                _cel(_fmt_prazo(d.get("prazo_dias"))),
            ])
        t_docs = Table(linhas_docs, colWidths=[0.7 * cm, 5.4 * cm, 3.3 * cm, 5.0 * cm, 1.6 * cm])
        t_docs.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING",    (0, 0), (-1, -1), 3),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
        ]))
        t_docs.hAlign = "LEFT"
        story.append(t_docs)
        if any(isinstance(d, dict) and d.get("_situacao_declarada") for d in docs):
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(NOTA_DECLARADO, _ESTILO_PEQNO))
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
        # DEFEITO REAL, pego no 3o teste (17/08/2026): a tabela ja saia
        # "pendente — declarado", e a conclusao logo abaixo afirmava os MESMOS
        # vicios como constatados ("vicios identificados", "certidao vencida").
        # O campo estruturado obedeceu a regra do lastro; o texto livre nao — e
        # e a conclusao que a pessoa le e para. O aviso em maiusculas existe,
        # mas fica na ultima pagina, longe daqui. Frase escrita por codigo,
        # colada onde o olho esta: nao depende de o modelo lembrar.
        if ia_utils.sem_lastro_documental(parecer):
            story.append(Spacer(1, 0.15 * cm))
            story.append(Paragraph(_ressalva_da_conclusao(_res), _ESTILO_RESSALVA))
        story.append(Spacer(1, 0.3 * cm))

    _prazo_geral = parecer.get("prazo_resposta_sugerido")
    story.append(Paragraph("Prazo de Resposta", _ESTILO_H2))
    if isinstance(_prazo_geral, int):
        story.append(Paragraph(
            f"Prazo indicado pela análise: <b>{_prazo_geral} dias</b>. Este número foi "
            "extraído dos documentos anexados pela leitura automática, que não valida a "
            "sua origem: confirme na fonte, inclusive se os dias são úteis ou corridos, "
            "antes de expedir o ofício.",
            _ESTILO_CORPO,
        ))
    else:
        story.append(Paragraph(
            "<b>Nenhum prazo foi localizado no edital ou nos documentos anexados.</b> "
            "A Lei 14.133/2021 não fixa prazo geral de resposta à diligência: cabe à "
            "autoridade fixá-lo de forma expressa e motivada, indicando se os dias são "
            "úteis ou corridos. Este sistema não arbitra esse prazo.",
            _ESTILO_CORPO,
        ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("Documentos Analisados", _ESTILO_H2))
    _docs_lidos = _as_list(parecer.get("_documentos_analisados"))
    if _docs_lidos:
        for _l in ia_utils.linhas_manifesto(_docs_lidos):
            story.append(Paragraph(f"- {html.escape(_l)}", _ESTILO_CORPO))
    else:
        story.append(Paragraph(
            f"<b>{html.escape(ia_utils.AVISO_SEM_LASTRO)}</b>", _ESTILO_CORPO))
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
        "Gerado por RM Lisura — RM Vértice Digital.",
        _ESTILO_PEQNO,
    ))

    # >>> DISCLAIMER (3/3): rodapé fixo de minuta em todas as páginas
    doc.build(story, onFirstPage=_rodape_todas_paginas, onLaterPages=_rodape_todas_paginas)
    return buf.getvalue()
