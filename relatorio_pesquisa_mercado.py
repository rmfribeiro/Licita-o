from __future__ import annotations
import html
import io
import unicodedata
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from ia_utils import COR_STATUS_HEX as _COR_STATUS, fmt_brl_opcional as _fmt_brl_opcional
import disclaimers  # >>> DISCLAIMER (1/4): importa os textos centralizados

def _norm(s: str) -> str:
    """Normaliza para comparação: minúsculas, sem acentos, sem espaços extras."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().strip().casefold()


_COR_PESQUISA = {
    "VÁLIDA":        colors.HexColor(_COR_STATUS["ok"]),
    "COM RESSALVAS": colors.HexColor(_COR_STATUS["alerta"]),
    "INVÁLIDA":      colors.HexColor(_COR_STATUS["critico"]),
}

_estilos = getSampleStyleSheet()
_TITULO  = ParagraphStyle("pm_titulo", parent=_estilos["Title"],   fontSize=16, spaceAfter=4)
_H1      = ParagraphStyle("pm_h1",     parent=_estilos["Heading1"])
_H2      = ParagraphStyle("pm_h2",     parent=_estilos["Heading2"], fontSize=12, spaceAfter=3)
_CORPO   = ParagraphStyle("pm_corpo",  parent=_estilos["Normal"],   fontSize=10, spaceAfter=3)
_PEQUENO = ParagraphStyle("pm_peq",    parent=_estilos["Normal"],   fontSize=8,  textColor=colors.grey)
_BADGE   = ParagraphStyle("pm_badge",  parent=_estilos["Normal"],   fontSize=14, textColor=colors.white, alignment=1)

# >>> DISCLAIMER (2/4): estilo do rodapé fixo + função que o desenha em CADA página.
#     Aqui usamos TEXTO_PDF (aviso brando), pois estas funções NÃO geram minuta —
#     produzem mapa de preços e relatório de pesquisa (apoio à decisão).
_ESTILO_RODAPE = ParagraphStyle(
    "pm_rodape",
    parent=_estilos["Normal"],
    fontSize=7,
    leading=8.5,
    textColor=colors.HexColor("#C0392B"),
    alignment=1,
)


def _rodape_todas_paginas(canvas, doc):
    """Desenha o disclaimer de apoio no rodapé de TODAS as páginas."""
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


def gerar_mapa_precos(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    valor_total_estimado: float | None,
) -> bytes:
    buf = io.BytesIO()
    # Com muitas fontes consultadas (típico da busca no PNCP), a tabela não
    # cabe em retrato: vira paisagem para as colunas continuarem legíveis.
    _muitos = len(fornecedores) > 4
    _pagina = landscape(A4) if _muitos else A4
    doc = SimpleDocTemplate(
        buf, pagesize=_pagina,
        leftMargin=1.5*cm, rightMargin=1.5*cm, topMargin=2*cm, bottomMargin=2.5*cm,
    )
    story: list = []

    story.append(Paragraph("RM Lisura — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Mapa de Preços", _H1))
    story.append(Paragraph(html.escape(objeto), _H2))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    # Células em Paragraph para o texto QUEBRAR dentro da coluna; como string
    # pura o ReportLab não quebra linha e os nomes se sobrepõem.
    _cel_cab = ParagraphStyle("cel_cab", fontName="Helvetica-Bold", fontSize=7,
                              leading=8, textColor=colors.white)
    _cel = ParagraphStyle("cel", fontName="Helvetica", fontSize=7, leading=8)

    nomes_forn = [
        Paragraph(html.escape(f.get("nome") or f"Fornecedor {i + 1}"), _cel_cab)
        for i, f in enumerate(fornecedores)
    ]
    header = ([Paragraph(t, _cel_cab) for t in ("#", "Descrição", "Un", "Qtd")]
              + nomes_forn
              + [Paragraph(t, _cel_cab) for t in ("Ref (mediana)", "Subtotal")])
    linhas: list[list] = [header]
    notas: list[str] = []
    nota_num = 1
    _total_exibidos = 0   # quantos preços realmente aparecem na tabela

    for item in itens_avaliados:
        cots_dict: dict = {}
        for _c in (item.get("cotacoes_detalhadas") or []):
            _k = _norm(_c.get("fornecedor") or "")
            _p = _c.get("preco_unitario")
            if _k not in cots_dict:
                cots_dict[_k] = _p
            elif _p is not None:
                if cots_dict[_k] is None:
                    cots_dict[_k] = _p
                else:
                    try:
                        _p_f = float(_p)
                        try:
                            if _p_f < float(cots_dict[_k]):
                                cots_dict[_k] = _p
                        except (ValueError, TypeError, OverflowError):
                            cots_dict[_k] = _p  # existing is non-numeric, new is numeric
                    except (ValueError, TypeError, OverflowError):
                        pass  # new is non-numeric, keep existing
        excluidas_precos: set = {
            e["preco"] for e in (item.get("cotacoes_excluidas") or [])
            if e.get("preco") is not None
        }
        excluidas_motivos: dict = {
            e["preco"]: e.get("motivo", "excluída")
            for e in (item.get("cotacoes_excluidas") or [])
            if e.get("preco") is not None
        }

        celulas_forn: list[str] = []
        _precos_exibidos = 0
        for forn in fornecedores:
            nome = forn.get("nome") or ""
            preco = cots_dict.get(_norm(nome))
            if preco is None:
                celulas_forn.append("—")
            elif preco in excluidas_precos:
                tag = f"[{nota_num}]"
                notas.append(
                    f"[{nota_num}] {html.escape(excluidas_motivos.get(preco, 'excluída'))}"
                )
                nota_num += 1
                celulas_forn.append(f"EXC.{tag}")
            else:
                celulas_forn.append(_fmt_brl_opcional(preco))
                _precos_exibidos += 1

        _total_exibidos += _precos_exibidos
        ref_str = _fmt_brl_opcional(item.get("preco_referencia"), default="INSUF.")
        sub_str = _fmt_brl_opcional(item.get("subtotal_estimado"), default="—")
        _qtd = item.get("quantidade_estimada")
        qtd_str = "—" if _qtd is None else str(_qtd)

        linhas.append([
            Paragraph(str(item["item_id"]), _cel),
            Paragraph(html.escape(str(item.get("descricao") or "")), _cel),
            Paragraph(html.escape(str(item.get("unidade") or "un")), _cel),
            Paragraph(qtd_str, _cel),
        ] + [Paragraph(c, _cel) for c in celulas_forn]
          + [Paragraph(ref_str, _cel), Paragraph(sub_str, _cel)])

    total_str = _fmt_brl_opcional(valor_total_estimado, default="—")
    linhas.append(
        ["", Paragraph("VALOR TOTAL ESTIMADO", _cel), "", ""]
        + [""] * len(fornecedores) + ["", Paragraph(total_str, _cel)]
    )

    # Larguras SEMPRE dentro da página: as colunas fixas encolhem quando há
    # muitas fontes, e o que sobra é dividido igualmente entre elas.
    _usable = _pagina[0] - 3 * cm            # margens de 1,5 cm de cada lado
    _n = max(len(fornecedores), 1)
    _desc_w = 4.5*cm if _n <= 4 else 3.2*cm
    _ref_w  = 2.6*cm if _n <= 4 else 2.2*cm
    _sub_w  = 2.4*cm if _n <= 4 else 2.0*cm
    _fixed  = 0.7*cm + _desc_w + 0.9*cm + 1.1*cm + _ref_w + _sub_w
    _forn_w = max(1.2*cm, (_usable - _fixed) / _n)
    # Se ainda assim estourar (muitíssimas fontes), reparte o disponível.
    if _fixed + _forn_w * _n > _usable:
        _forn_w = (_usable - _fixed) / _n
    col_w = ([0.7*cm, _desc_w, 0.9*cm, 1.1*cm]
             + [_forn_w] * _n + [_ref_w, _sub_w])

    t = Table(linhas, colWidths=col_w)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTSIZE",   (0, 0), (-1, -1), 8),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING",    (0, 0), (-1, -1), 3),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F2F2F2")),
        ("FONTNAME",   (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t)

    # Quando a mesma fonte tem várias cotações (comum no PNCP), o mapa mostra
    # a menor delas — sem esta nota o leitor estranha o total do relatório.
    _n_validas = sum(len(i.get("cotacoes_validas") or []) for i in itens_avaliados)
    if _n_validas > _total_exibidos:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(
            f"Nota: cada coluna apresenta a menor cotação válida da fonte. "
            f"O total de {_n_validas} cotações válidas que compõem a mediana "
            f"está detalhado no Relatório de Pesquisa de Preços.", _PEQUENO
        ))

    if notas:
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph("Notas (cotações excluídas):", _H2))
        for nota in notas:
            story.append(Paragraph(nota, _PEQUENO))

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))

    doc.build(story, onFirstPage=_rodape_todas_paginas, onLaterPages=_rodape_todas_paginas)
    return buf.getvalue()


def gerar_relatorio_pesquisa(
    objeto: str,
    itens_avaliados: list[dict],
    fornecedores: list[dict],
    parecer_narrativo: str,
    status_geral: str,
    valor_total_estimado: float | None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2.5*cm,  # >>> DISCLAIMER
    )
    story: list = []

    story.append(Paragraph("RM Lisura — RM Vértice Digital", _TITULO))
    story.append(Paragraph("Relatório de Pesquisa de Preços de Mercado", _H1))
    story.append(Paragraph("Art. 23, Lei 14.133/2021 + IN SEGES/MGI 65/2021", _PEQUENO))
    story.append(Paragraph(
        f"Gerado em: {datetime.now().strftime('%d/%m/%Y às %H:%M')}", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.grey, spaceAfter=8))

    story.append(Paragraph("1. Identificação do Objeto", _H2))
    story.append(Paragraph(html.escape(objeto), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("2. Metodologia", _H2))
    story.append(Paragraph(
        "A pesquisa de preços foi realizada em conformidade com o Art. 23 da Lei n.º 14.133/2021 "
        "e a IN SEGES/MGI 65/2021. O preço de referência por item foi calculado como a mediana "
        "das cotações válidas. Cotações com valor superior a 50% acima da mediana provisória "
        "foram excluídas por configurarem preço inexequível ou especulativo.",
        _CORPO,
    ))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("3. Fornecedores Consultados", _H2))
    for forn in fornecedores:
        nome = html.escape(str(forn.get("nome") or "não identificado"))
        cnpj = html.escape(str(forn.get("cnpj") or "não informado"))
        story.append(Paragraph(f"- {nome} — CNPJ: {cnpj}", _CORPO))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("4. Análise por Item", _H2))
    for item in itens_avaliados:
        desc = html.escape(str(item.get("descricao") or ""))
        un   = html.escape(str(item.get("unidade") or "un"))
        story.append(Paragraph(f"<b>Item {item['item_id']}: {desc}</b> ({un})", _CORPO))
        if item.get("preco_referencia") is not None:
            story.append(Paragraph(
                f"Preço de referência: {_fmt_brl_opcional(item['preco_referencia'])}/{un} — "
                f"{len(item.get('cotacoes_validas', []))} cotação(ões) válida(s)",
                _CORPO,
            ))
        else:
            story.append(Paragraph(
                f"Status: INSUFICIENTE — apenas {len(item.get('cotacoes_validas', []))} "
                f"cotação(ões) válida(s) (mínimo: 3)",
                _CORPO,
            ))
        for exc in (item.get("cotacoes_excluidas") or []):
            story.append(Paragraph(
                f"  Excluída: {html.escape(str(exc.get('motivo', '')))}",
                _PEQUENO,
            ))
    story.append(Spacer(1, 0.3*cm))

    _cor_badge = _COR_PESQUISA.get(status_geral, colors.grey)
    t_badge = Table(
        [[Paragraph(f"<b>{html.escape(status_geral)}</b>", _BADGE)]],
        colWidths=[17*cm],
    )
    t_badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _cor_badge),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("PADDING",    (0, 0), (-1, -1), 8),
    ]))
    story.append(t_badge)
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("5. Parecer", _H2))
    story.append(Paragraph(html.escape(parecer_narrativo or "-"), _CORPO))
    story.append(Spacer(1, 0.3*cm))

    if valor_total_estimado is not None:
        story.append(Paragraph("6. Valor Total Estimado", _H2))
        story.append(Paragraph(f"<b>{_fmt_brl_opcional(valor_total_estimado)}</b>", _CORPO))
        story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph(
        "Base Legal: Art. 23, Lei n.º 14.133/2021 — IN SEGES/MGI 65/2021", _PEQUENO
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Paragraph(
        "Gerado por RM Lisura - RM Vertice Digital. Revisar antes de anexar ao processo.",
        _PEQUENO,
    ))

    # >>> DISCLAIMER (4/4): rodapé fixo em todas as páginas
    doc.build(story, onFirstPage=_rodape_todas_paginas, onLaterPages=_rodape_todas_paginas)
    return buf.getvalue()
