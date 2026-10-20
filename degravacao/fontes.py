"""Resolve as entradas: link do Google Drive, arquivo local ou pasta."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

# O que vale é o conteúdo (midia.examinar); a extensão só decide o que entra na varredura de pastas.
EXT_VIDEO = {".mp4", ".m4v", ".mov", ".qt", ".mkv", ".webm", ".avi", ".divx", ".wmv", ".asf", ".flv", ".f4v",
             ".mpg", ".mpeg", ".vob", ".ts", ".mts", ".m2ts", ".m2t", ".mod", ".tod", ".3gp", ".3g2",
             ".ogv", ".mxf", ".dv", ".rm", ".rmvb", ".dav"}
EXT_AUDIO = {".mp3", ".m4a", ".m4b", ".wav", ".aiff", ".aif", ".ogg", ".oga", ".opus", ".weba", ".aac", ".ac3",
             ".flac", ".wma", ".amr", ".3ga", ".mka", ".mp2", ".caf"}
EXT_MIDIA = EXT_VIDEO | EXT_AUDIO
# Arquivos comuns numa pasta de trabalho que não são gravações: a varredura os ignora em silêncio.
EXT_DOCUMENTOS = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".xls", ".xlsx", ".csv", ".ppt", ".pptx", ".txt", ".md",
                  ".json", ".xml", ".html", ".htm", ".srt", ".vtt", ".zip", ".rar", ".7z", ".jpg", ".jpeg", ".png",
                  ".gif", ".heic", ".webp", ".bmp", ".svg", ".ini", ".lnk", ".url", ".db", ".ds_store", ".log", ".bak"}

# Gravações em formato fechado, que nenhum programa aberto lê: só o aplicativo de origem converte.
PROPRIETARIOS = {
    ".arf": "gravação do Webex: abra no Webex Network Recording Player e exporte para MP4",
    ".wrf": "gravação do Webex: abra no Webex Network Recording Player e exporte para MP4",
    ".zoom": "gravação do Zoom ainda não convertida: abra o Zoom no computador que gravou para gerar o MP4",
}

_RE_ARQUIVO = [
    re.compile(r"drive\.google\.com/file/d/([\w-]{10,})"),
    re.compile(r"drive\.google\.com/(?:open|uc)\?(?:.*&)?id=([\w-]{10,})"),
    re.compile(r"docs\.google\.com/\w+/d/([\w-]{10,})"),
]
_RE_PASTA = re.compile(r"drive\.google\.com/drive/(?:u/\d+/)?folders/([\w-]{10,})")


class ErroEntrada(Exception):
    pass


@dataclass
class Midia:
    caminho: Path
    origem: str            # "Google Drive" | "Arquivo local"
    chave: str             # identificador estável para evitar reprocessar
    url: str | None = None
    mover: bool = False    # True = arquivo vai para a pasta de saída após processar


def eh_link_drive(texto: str) -> bool:
    return "drive.google.com" in texto or "docs.google.com" in texto


def id_drive(url: str) -> tuple[str, str]:
    """Retorna ("arquivo" | "pasta", id) a partir de um link do Drive."""
    m = _RE_PASTA.search(url)
    if m:
        return "pasta", m.group(1)
    for rx in _RE_ARQUIVO:
        m = rx.search(url)
        if m:
            return "arquivo", m.group(1)
    raise ErroEntrada(f"Não reconheci o link do Google Drive: {url}")


_MSG_DRIVE = (
    "Falha ao baixar do Google Drive ({erro}).\n"
    "  • Confira se o compartilhamento está como \"Qualquer pessoa com o link\" (leitor).\n"
    "  • Para arquivos que não podem ser compartilhados, use o Google Drive para computador\n"
    "    e informe o caminho da pasta sincronizada (ex.: \"G:\\Meu Drive\\Audiências\")."
)


def baixar_drive(url: str, destino: Path, ja_processados: set[str]) -> list[Midia]:
    import gdown  # import tardio: só necessário para links

    tipo, ident = id_drive(url)
    destino.mkdir(parents=True, exist_ok=True)

    if tipo == "arquivo":
        itens = [(ident, None)]
    else:
        try:
            lista = gdown.download_folder(id=ident, output=str(destino), skip_download=True, quiet=True)
        except Exception as e:  # noqa: BLE001 — gdown lança vários tipos
            raise ErroEntrada(_MSG_DRIVE.format(erro=e)) from e
        itens = [(f.id, Path(f.path).name) for f in lista or [] if Path(f.path).suffix.lower() in EXT_MIDIA]
        if not itens:
            raise ErroEntrada("A pasta do Drive não contém vídeos ou áudios reconhecidos.")

    midias: list[Midia] = []
    for fid, nome in itens:
        chave = f"drive:{fid}"
        if chave in ja_processados:
            print(f"  ↷ já degravado anteriormente: {nome or fid} (use --refazer para repetir)")
            continue
        print(f"  ↓ baixando do Drive: {nome or fid}")
        # Cada item numa subpasta própria (o id): dois arquivos com o mesmo nome, em links ou subpastas
        # diferentes do Drive, nunca gravam um por cima do outro.
        pasta_item = destino / fid
        pasta_item.mkdir(parents=True, exist_ok=True)
        saida = str(pasta_item / nome) if nome else str(pasta_item) + "/"
        try:
            # Barra de progresso só no terminal; em arquivo (Claude em segundo plano) ela vira uma linha gigante.
            caminho = gdown.download(id=fid, output=saida, quiet=not sys.stdout.isatty())
        except Exception as e:  # noqa: BLE001
            raise ErroEntrada(_MSG_DRIVE.format(erro=e)) from e
        if not caminho:
            raise ErroEntrada(_MSG_DRIVE.format(erro="download não retornou arquivo"))
        caminho = Path(caminho)
        if caminho.suffix.lower() not in EXT_MIDIA:
            print(f"  ⚠ extensão não reconhecida ({caminho.suffix}); tentando mesmo assim.")
        midias.append(Midia(caminho, "Google Drive", chave, url=url, mover=True))
    return midias


def _visivel(p: Path) -> bool:
    return not p.name.startswith((".", "~$"))


def listar_pasta(pasta: Path) -> list[Path]:
    return sorted(
        p for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in EXT_MIDIA and _visivel(p)
    )


def avisos_da_pasta(pasta: Path, ignorar: Path | None = None) -> list[str]:
    """O que a varredura deixou de fora e o usuário pode não perceber: gravações em formato fechado,
    arquivos que não parecem mídia e subpastas com vídeos (a varredura não desce nelas)."""
    avisos: list[str] = []
    subpastas: list[str] = []
    for f in sorted(pasta.iterdir()):
        if not _visivel(f):
            continue
        if f.is_dir():
            if ignorar and f.resolve() == ignorar.resolve():
                continue
            try:
                n = sum(1 for x in f.iterdir() if x.is_file() and x.suffix.lower() in EXT_MIDIA and _visivel(x))
            except OSError:
                n = 0
            if n:
                subpastas.append(f"{f.name} ({n})")
            continue
        suf = f.suffix.lower()
        if suf in PROPRIETARIOS:
            avisos.append(f"↷ {f.name} pulado — {PROPRIETARIOS[suf]}.")
        elif suf not in EXT_MIDIA and suf not in EXT_DOCUMENTOS:
            avisos.append(f"↷ {f.name} ignorado: não parece vídeo nem áudio (para tentar mesmo assim, informe o caminho do arquivo).")
    if subpastas:
        avisos.append("↷ há vídeos ou áudios em subpastas, que a varredura não lê: " + ", ".join(subpastas)
                      + ". Informe a subpasta ou mova os arquivos para a pasta principal.")
    return avisos


def resolver(entradas: list[str], caixa_entrada: Path, downloads: Path, ja_processados: set[str],
             mover_caixa: bool = True, erros: list[str] | None = None, ignorar_pasta: Path | None = None) -> list[Midia]:
    """Transforma os argumentos do usuário em uma lista de mídias a degravar.

    Sem argumentos, processa a pasta de entrada. Com `mover_caixa`, os arquivos dela são
    movidos para a saída depois de degravados; sem, ficam onde estão e são pulados na próxima vez.
    Uma entrada inválida não derruba as outras: a mensagem vai para `erros` (ou, sem a lista, levanta
    ErroEntrada quando nada sobrou).
    """
    if not entradas:
        entradas = [str(caixa_entrada)]

    midias: list[Midia] = []
    problemas: list[str] = []
    for item in entradas:
        item = item.strip().strip('"').strip("'")
        try:
            if eh_link_drive(item):
                midias += baixar_drive(item, downloads, ja_processados)
                continue

            p = Path(item).expanduser()
            if not p.exists():
                raise ErroEntrada(f"Arquivo ou pasta não encontrado: {p}")
            if p.suffix.lower() in PROPRIETARIOS:
                raise ErroEntrada(f"{p.name}: {PROPRIETARIOS[p.suffix.lower()]}.")
        except ErroEntrada as e:
            problemas.append(str(e))
            continue
        mover = mover_caixa and (p.resolve() == caixa_entrada.resolve() or caixa_entrada.resolve() in p.resolve().parents)
        if p.is_dir():
            for aviso in avisos_da_pasta(p, ignorar_pasta):
                print(f"  {aviso}")
        arquivos = listar_pasta(p) if p.is_dir() else [p]
        for a in arquivos:
            chave = f"arquivo:{a.resolve()}"
            if not mover and chave in ja_processados:
                print(f"  ↷ já degravado anteriormente: {a.name} (use --refazer para repetir)")
                continue
            midias.append(Midia(a, "Arquivo local", chave, mover=mover))
    if problemas:
        if erros is not None:
            erros.extend(problemas)
        elif not midias:
            raise ErroEntrada("\n".join(problemas))
        else:
            for p in problemas:
                print(f"  ✗ {p}")
    return midias
