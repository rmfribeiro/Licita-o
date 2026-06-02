# -*- coding: utf-8 -*-
"""Timbre configuravel para os pareceres. Edite branding.json com os dados da
sua empresa (nome, contato, cor e, opcionalmente, o caminho de um logo PNG)."""
import json, os, re
from docx.shared import Pt, RGBColor, Mm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

_AQUI = os.path.dirname(os.path.abspath(__file__))
_PADRAO = {"empresa": "[SUA EMPRESA]", "tagline": "[SLOGAN DA EMPRESA]",
           "referencia_legal": "Auditoria de Editais — Lei 14.133/2021",
           "contato": "", "cor_primaria": "1F4E79", "logo": ""}

def carregar():
    p = os.path.join(_AQUI, "branding.json")
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            # Normaliza None para o padrão; valida cor_primaria como hex de 6 dígitos
            data = {k: (v if v is not None else _PADRAO.get(k, "")) for k, v in data.items()}
            cor = str(data.get("cor_primaria", "")).lstrip("#")
            data["cor_primaria"] = cor if re.fullmatch(r"[0-9A-Fa-f]{6}", cor) else _PADRAO["cor_primaria"]
            return {**_PADRAO, **data}
        except Exception:
            pass
    return dict(_PADRAO)

def add_banner(doc):
    """Insere o timbre (logo opcional + nome da empresa + tagline) no topo."""
    b = carregar()
    cor = RGBColor.from_string(b["cor_primaria"])
    if b.get("logo") and os.path.isfile(os.path.join(_AQUI, b["logo"])):
        try:
            pic = doc.add_paragraph(); pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
            pic.add_run().add_picture(os.path.join(_AQUI, b["logo"]), height=Mm(14))
            pic.paragraph_format.space_after = Pt(2)
        except Exception:
            pass
    p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run(b["empresa"]); r.bold = True; r.font.size = Pt(12); r.font.color.rgb = cor
    p2 = doc.add_paragraph(); p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_after = Pt(8)
    r2 = p2.add_run(b["referencia_legal"]); r2.font.size = Pt(8.5); r2.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
    pPr = p2._p.get_or_add_pPr(); pb = OxmlElement("w:pBdr"); bt = OxmlElement("w:bottom")
    bt.set(qn("w:val"), "single"); bt.set(qn("w:sz"), "4"); bt.set(qn("w:space"), "4"); bt.set(qn("w:color"), b["cor_primaria"])
    pb.append(bt); pPr.append(pb)
    return b

def add_contato_footer(sec):
    """Escreve a linha de contato no rodape, preservando paragrafos com numeracao de pagina."""
    b = carregar()
    if not b.get("contato"):
        return
    footer = sec.footer
    # Reutiliza o ultimo paragrafo sem campo de pagina; senao adiciona novo
    p = None
    for para in reversed(footer.paragraphs):
        if not para._p.findall(".//" + qn("w:fldChar")):
            p = para
            break
    if p is None:
        p = footer.add_paragraph()
    for r in list(p._p.findall(".//" + qn("w:r"))):
        r.getparent().remove(r)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(b["empresa"] + "   ·   " + b["contato"])
    r.font.size = Pt(7.5); r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
