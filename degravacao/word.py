"""Degravação em Word (.docx): A4, margens ABNT, numeração de páginas, sem dependências.

O .docx é um ZIP de XML; aqui ele é montado à mão, com estilos de título que aparecem no
painel de navegação do Word e o mesmo sublinhado ondulado do player nos trechos a conferir.
"""

from __future__ import annotations

import html
import io
import re
import zipfile
from datetime import datetime, timezone

from .documento import (CATEGORIAS, blocos, eh_item_lista, marcacoes_validas, marcas_falante, paragrafos,
                        resumo_revisao, secao_estruturada, trechos_conferencia)
from .falantes import nome as nome_falante
from .util import duracao_por_extenso, minutagem

_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
_R = 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
# O que o XML 1.0 não aceita: controles (fora \t \n \r), substitutos soltos e os dois não caracteres.
_PROIBIDO = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")
_INLINE_MD = re.compile(r"(\*\*.+?\*\*|\[\[\d{2}:\d{2}:\d{2}\]\]\(player\.html#t=\d+\)|`[^`]+`|(?<![\w*])_.+?_(?![\w*]))")
AZUL, CINZA, OURO = "2B4E86", "595959", "B7791F"
RODAPE_RPR = '<w:rPr><w:color w:val="7F7F7F"/><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>'


def _x(txt: str) -> str:
    return html.escape(_PROIBIDO.sub("", txt), quote=False)


def _run(txt: str, b: bool = False, i: bool = False, cor: str | None = None, mono: bool = False,
         tam: int | None = None, onda: bool = False) -> str:
    rpr = ""
    if mono:
        rpr += '<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" w:cs="Consolas"/>'
    if b:
        rpr += "<w:b/>"
    if i:
        rpr += "<w:i/>"
    if cor:
        rpr += f'<w:color w:val="{cor}"/>'
    if tam:
        rpr += f'<w:sz w:val="{tam}"/><w:szCs w:val="{tam}"/>'
    if onda:   # trecho de baixa confiança
        rpr += f'<w:u w:val="wave" w:color="{OURO}"/>'
    partes = []
    for pedaco in re.split(r"([\t\n])", txt.replace("\r\n", "\n").replace("\r", "\n")):
        if pedaco == "\t":
            partes.append("<w:tab/>")
        elif pedaco == "\n":
            partes.append("<w:br/>")
        elif pedaco:
            partes.append(f'<w:t xml:space="preserve">{_x(pedaco)}</w:t>')
    return f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}{"".join(partes)}</w:r>'


def _par(runs: str, estilo: str | None = None, recuo: int = 0, apos: int | None = None, esquerda: bool = False) -> str:
    ppr = f'<w:pStyle w:val="{estilo}"/>' if estilo else ""
    if apos is not None:
        ppr += f'<w:spacing w:after="{apos}"/>'
    if recuo:
        ppr += f'<w:ind w:left="{recuo}" w:hanging="240"/>'
    if esquerda:   # células de tabela: o justificado do corpo espaçaria demais as palavras
        ppr += '<w:jc w:val="left"/>'
    return f'<w:p>{f"<w:pPr>{ppr}</w:pPr>" if ppr else ""}{runs}</w:p>'


def _minutagem(t: float) -> str:
    return _run(f"[{minutagem(t)}] ", mono=True, cor=AZUL, tam=20)


def _runs_md(txt: str) -> str:
    """Negrito, itálico, código e minutagens do Markdown da seção estruturada."""
    saida = []
    for parte in _INLINE_MD.split(txt):
        if not parte:
            continue
        if parte.startswith("**") and parte.endswith("**"):
            saida.append(_run(parte[2:-2], b=True))
        elif parte.startswith("[["):
            saida.append(_run(f"[{parte[2:10]}]", mono=True, cor=AZUL, tam=20))
        elif parte.startswith("`"):
            saida.append(_run(parte[1:-1], mono=True))
        elif parte.startswith("_") and parte.endswith("_") and len(parte) > 2:
            saida.append(_run(parte[1:-1], i=True))
        else:
            saida.append(_run(parte))
    return "".join(saida)


def _tabela(linhas: list[list[str]], larguras: list[int], cabecalho: bool = True, md: bool = True) -> str:
    """Tabela com bordas finas. `md`: as células passam pelo Markdown (só na seção do Claude; a ficha
    técnica é texto literal, para não perder sublinhados de nomes de arquivo e links)."""
    borda = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="D9D9D9"/>'
    bordas = "".join(borda.format(b) for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    xml = [f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{bordas}</w:tblBorders>'
           '<w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
           '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="100" w:type="dxa"/></w:tblCellMar></w:tblPr><w:tblGrid>']
    xml += [f'<w:gridCol w:w="{w}"/>' for w in larguras]
    xml.append("</w:tblGrid>")
    for n, linha in enumerate(linhas):
        xml.append("<w:tr>")
        for c, texto in enumerate(linha):
            topo = cabecalho and n == 0
            sombra = '<w:shd w:val="clear" w:color="auto" w:fill="F2F2F2"/>' if topo else ""
            runs = _run(texto, b=True) if topo else (_runs_md(texto) if md else _run(texto))
            xml.append(f'<w:tc><w:tcPr><w:tcW w:w="{larguras[min(c, len(larguras) - 1)]}" w:type="dxa"/>{sombra}</w:tcPr>'
                       f'{_par(runs, apos=0, esquerda=True)}</w:tc>')
        xml.append("</w:tr>")
    xml.append("</w:tbl>")
    return "".join(xml) + _par("", apos=0)


def _md_para_docx(md: str) -> str:
    """Seção estruturada pelo Claude (títulos, listas, tabelas, parágrafos)."""
    saida, linhas, i = [], [ln.strip() for ln in md.splitlines()], 0
    while i < len(linhas):
        ln = linhas[i]
        if not ln or ln.startswith("<!--"):
            i += 1
        elif ln.startswith("#"):
            saida.append(_par(_runs_md(ln.lstrip("#").strip()), "Heading2"))
            i += 1
        elif eh_item_lista(ln):
            texto = ln[2:].strip()
            if texto:
                saida.append(_par(_run("•\t") + _runs_md(texto), recuo=360, apos=60))
            i += 1
        elif ln.startswith("|"):
            bloco = []
            while i < len(linhas) and linhas[i].startswith("|"):
                cel = [c.strip() for c in linhas[i].strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cel):
                    bloco.append(cel)
                i += 1
            if not any(c for r in bloco for c in r):   # tabela só com separador ou "|" solto
                continue
            n = max(len(r) for r in bloco)
            saida.append(_tabela([r + [""] * (n - len(r)) for r in bloco], [9000 // n] * n))
        else:
            saida.append(_par(_runs_md(ln)))
            i += 1
    return "".join(saida)


def _campo(nome: str, rpr: str = "") -> str:
    """Campo de página (PAGE/NUMPAGES); `rpr` vai em todos os runs, senão o número sai no estilo Normal."""
    return (f'<w:r>{rpr}<w:fldChar w:fldCharType="begin"/></w:r>'
            f'<w:r>{rpr}<w:instrText xml:space="preserve"> {nome} </w:instrText></w:r>'
            f'<w:r>{rpr}<w:fldChar w:fldCharType="separate"/></w:r><w:r>{rpr}<w:t>1</w:t></w:r>'
            f'<w:r>{rpr}<w:fldChar w:fldCharType="end"/></w:r>')


ESTILOS = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}>'
           '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" '
           'w:cs="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="pt-BR"/></w:rPr></w:rPrDefault>'
           '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="300" w:lineRule="auto"/><w:jc w:val="both"/>'
           '</w:pPr></w:pPrDefault></w:docDefaults>'
           '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/></w:style>'
           '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/>'
           '<w:next w:val="Normal"/><w:qFormat/><w:pPr><w:spacing w:after="120"/><w:jc w:val="left"/></w:pPr>'
           '<w:rPr><w:b/><w:sz w:val="34"/><w:szCs w:val="34"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/>'
           '<w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/>'
           '<w:spacing w:before="360" w:after="120"/><w:jc w:val="left"/><w:outlineLvl w:val="0"/></w:pPr>'
           f'<w:rPr><w:b/><w:color w:val="{AZUL}"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/>'
           '<w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/>'
           '<w:spacing w:before="240" w:after="80"/><w:jc w:val="left"/><w:outlineLvl w:val="1"/></w:pPr>'
           '<w:rPr><w:b/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr></w:style>'
           '<w:style w:type="paragraph" w:customStyle="1" w:styleId="Aviso"><w:name w:val="Aviso"/>'
           f'<w:basedOn w:val="Normal"/><w:rPr><w:i/><w:color w:val="{CINZA}"/><w:sz w:val="20"/>'
           '<w:szCs w:val="20"/></w:rPr></w:style></w:styles>')

# Sem o modo de compatibilidade 15, o Word abre o arquivo como "documento do Word 2007".
CONFIGURACOES = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:settings {_W}><w:compat>'
                 '<w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>'
                 '</w:compat></w:settings>')

TIPOS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
         '<Override PartName="/word/styles.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
         '<Override PartName="/word/settings.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
         '<Override PartName="/word/footer1.xml" '
         'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
         '<Override PartName="/docProps/core.xml" '
         'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/></Types>')

_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
RELS = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f'<Relationship Id="rId1" Type="{_REL}/officeDocument" Target="word/document.xml"/>'
        '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" '
        'Target="docProps/core.xml"/></Relationships>')
RELS_DOC = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'<Relationship Id="rId1" Type="{_REL}/styles" Target="styles.xml"/>'
            f'<Relationship Id="rId2" Type="{_REL}/footer" Target="footer1.xml"/>'
            f'<Relationship Id="rId3" Type="{_REL}/settings" Target="settings.xml"/></Relationships>')


def _instante_utc(iso: str) -> str:
    """gerado_em é hora local sem fuso; o core.xml pede W3CDTF em UTC."""
    try:
        momento = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        momento = datetime.now()
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _contagem_conferir(segs: list[dict], pars: list[dict]) -> str:
    """Mesma conta da ficha do .md: frases de baixa confiança e, quando diferem, os trechos em que se agrupam."""
    frases = sum(1 for s in segs if s.get("baixa_confianca"))
    trechos = len(trechos_conferencia(pars, segs))
    return f"{frases} frase{'s' if frases != 1 else ''}" + (f" em {trechos} trechos" if trechos != frases else "")


def gerar_docx(dados: dict, titulo: str, md_doc: str = "") -> bytes:
    segs = dados["segmentos"]
    pars = paragrafos(segs)
    aviso = ("Transcrição automática integral, gerada localmente com Whisper. Antes de usar em peça ou "
             "juntar aos autos, confira na mídia original os trechos sublinhados em ondulado.")
    if dados.get("falantes"):
        aviso += " Falantes atribuídos pela voz (aproximado): (?) = a conferir; ✎ = atribuição revista."
    corpo = [_par(_run(f"Degravação — {titulo}"), "Title"), _par(_run(aviso), "Aviso")]

    corpo.append(_par(_run("Ficha técnica"), "Heading1"))
    ficha = [["Arquivo", dados["arquivo"] + (f" ({dados['formato']})" if dados.get("formato") else "")],
             ["Origem", dados["origem"] + (f" — {dados['url']}" if dados.get("url") else "")],
             ["Duração", f"{minutagem(dados['duracao'])} ({duracao_por_extenso(dados['duracao'])})"],
             ["Transcrição", f"Whisper {dados['modelo']}, local · idioma {dados['idioma']}"],
             ["Trechos para conferência", _contagem_conferir(segs, pars)],
             ["Degravado em", datetime.fromisoformat(dados["gerado_em"]).strftime("%d/%m/%Y %H:%M")]]
    if dados.get("falantes"):
        incertas = sum(1 for s in segs if s.get("falante_incerto"))
        ficha.insert(4, ["Falantes", "; ".join(f"{nome_falante(dados, r)} ({minutagem(i['tempo'])})"
                                               for r, i in dados["falantes"].items())
                         + f" · {incertas} frase{'s' if incertas != 1 else ''} com falante a conferir (?)"])
    if dados.get("revisoes"):
        ficha.append(["Revisão", resumo_revisao(dados)])
    corpo.append(_tabela(ficha, [2600, 6400], cabecalho=False, md=False))

    estrutura = secao_estruturada(md_doc) if md_doc else None
    if estrutura:
        corpo.append(_par(_run("Resumo e estrutura"), "Heading1"))
        corpo.append(_md_para_docx(estrutura))

    marcacoes = marcacoes_validas(dados)
    if marcacoes:
        corpo.append(_par(_run("Marcações"), "Heading1"))
        for m in marcacoes:
            quem = nome_falante(dados, segs[m["de"]].get("falante"))
            runs = (_minutagem(m["ini"]) + _run(CATEGORIAS[m["cat"]] + " — ", b=True)
                    + _run(f"{quem + ': ' if quem else ''}“{m['texto']}”"))
            if m["nota"]:
                runs += _run(f" — {m['nota']}", i=True)
            corpo.append(_par(runs, recuo=360))

    corpo.append(_par(_run("Transcrição integral"), "Heading1"))
    for n, g in enumerate(blocos(pars, dados["duracao"]), 1):
        corpo.append(_par(_run(f"Bloco {n} — {minutagem(g[0]['ini'])} a {minutagem(g[-1]['fim'])}"), "Heading2"))
        for p in g:
            runs = _run(f"[{minutagem(p['ini'])}] ", mono=True, cor=CINZA, tam=20)
            if p.get("falante"):
                runs += _run(nome_falante(dados, p["falante"]), b=True)
                marcas = marcas_falante(p, segs)
                if marcas:   # (?) e ✎ como no .md e no player
                    runs += _run(marcas, cor=OURO, tam=18)
                runs += _run(": ", b=True)
            runs += "".join(_run(segs[i]["txt"].strip() + " ", onda=bool(segs[i].get("baixa_confianca"))) for i in p["segs"])
            corpo.append(_par(runs))

    # A4, margens ABNT (superior e esquerda 3 cm; inferior e direita 2 cm).
    secao = ('<w:sectPr><w:footerReference w:type="default" r:id="rId2"/><w:pgSz w:w="11906" w:h="16838"/>'
             '<w:pgMar w:top="1701" w:right="1134" w:bottom="1134" w:left="1701" w:header="709" w:footer="567" '
             'w:gutter="0"/></w:sectPr>')
    documento = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W} {_R}><w:body>'
                 + "".join(corpo) + secao + "</w:body></w:document>")
    rodape = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr {_W}><w:p><w:pPr><w:jc w:val="center"/>'
              '</w:pPr>' + _run(f"Degravação — {titulo} · página ", cor="7F7F7F", tam=16) + _campo("PAGE", RODAPE_RPR)
              + _run(" de ", cor="7F7F7F", tam=16) + _campo("NUMPAGES", RODAPE_RPR) + "</w:p></w:ftr>")
    criado = _instante_utc(dados["gerado_em"])
    modificado = _instante_utc(dados.get("revisao_em") or dados["gerado_em"])
    nucleo = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
              'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
              'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
              'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
              f"<dc:title>{_x('Degravação — ' + titulo)}</dc:title><dc:creator>degravacao-claude-advogados</dc:creator>"
              f'<dcterms:created xsi:type="dcterms:W3CDTF">{criado}</dcterms:created>'
              f'<dcterms:modified xsi:type="dcterms:W3CDTF">{modificado}</dcterms:modified></cp:coreProperties>')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TIPOS)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", RELS_DOC)
        z.writestr("word/document.xml", documento)
        z.writestr("word/styles.xml", ESTILOS)
        z.writestr("word/settings.xml", CONFIGURACOES)
        z.writestr("word/footer1.xml", rodape)
        z.writestr("docProps/core.xml", nucleo)
    return buf.getvalue()
