"""Resolve as entradas: link do Google Drive, arquivo local ou pasta."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

EXT_VIDEO = {".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp", ".ts"}
EXT_AUDIO = {".mp3", ".m4a", ".wav", ".ogg", ".opus", ".aac", ".flac", ".wma", ".amr"}
EXT_MIDIA = EXT_VIDEO | EXT_AUDIO

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
        saida = str(destino / nome) if nome else str(destino) + "/"
        try:
            caminho = gdown.download(id=fid, output=saida, quiet=False)
        except Exception as e:  # noqa: BLE001
            raise ErroEntrada(_MSG_DRIVE.format(erro=e)) from e
        if not caminho:
            raise ErroEntrada(_MSG_DRIVE.format(erro="download não retornou arquivo"))
        caminho = Path(caminho)
        if caminho.suffix.lower() not in EXT_MIDIA:
            print(f"  ⚠ extensão não reconhecida ({caminho.suffix}); tentando mesmo assim.")
        midias.append(Midia(caminho, "Google Drive", chave, url=url, mover=True))
    return midias


def listar_pasta(pasta: Path) -> list[Path]:
    return sorted(
        p for p in pasta.iterdir()
        if p.is_file() and p.suffix.lower() in EXT_MIDIA and not p.name.startswith(".")
    )


def resolver(entradas: list[str], caixa_entrada: Path, downloads: Path, ja_processados: set[str],
             mover_caixa: bool = True) -> list[Midia]:
    """Transforma os argumentos do usuário em uma lista de mídias a degravar.

    Sem argumentos, processa a pasta de entrada. Com `mover_caixa`, os arquivos dela são
    movidos para a saída depois de degravados; sem, ficam onde estão e são pulados na próxima vez.
    """
    if not entradas:
        entradas = [str(caixa_entrada)]

    midias: list[Midia] = []
    for item in entradas:
        item = item.strip().strip('"').strip("'")
        if eh_link_drive(item):
            midias += baixar_drive(item, downloads, ja_processados)
            continue

        p = Path(item).expanduser()
        if not p.exists():
            raise ErroEntrada(f"Arquivo ou pasta não encontrado: {p}")
        mover = mover_caixa and (p.resolve() == caixa_entrada.resolve() or caixa_entrada.resolve() in p.resolve().parents)
        arquivos = listar_pasta(p) if p.is_dir() else [p]
        for a in arquivos:
            chave = f"arquivo:{a.resolve()}"
            if not mover and chave in ja_processados:
                print(f"  ↷ já degravado anteriormente: {a.name} (use --refazer para repetir)")
                continue
            midias.append(Midia(a, "Arquivo local", chave, mover=mover))
    return midias
