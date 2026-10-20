"""Exame e preparo da mídia: qualquer formato que o FFmpeg lê vira algo que o navegador toca.

A decisão é pelo conteúdo (contêiner, codecs, formato de pixel), não pela extensão: um .mov do
iPhone (HEVC) precisa ser convertido, um .mkv com H.264 só troca de contêiner, um .webm sem
imagem é tratado como áudio. O original nunca é alterado.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CONTEINER_MP4 = "mov,mp4,m4a,3gp,3g2,mj2"     # nome do demuxer ISO BMFF no FFmpeg (.mp4, .mov, .m4a, .3gp…)
PIXEL_WEB = {"yuv420p", "yuvj420p"}            # H.264 10 bits ou 4:2:2 (câmeras) não toca no navegador
ALTURA_MAX = 720                               # cópia de reprodução: o original continua intacto
# Nomes curtos e fixos para a cópia que o player toca: pasta de saída + nome original passam fácil
# dos 260 caracteres que o Windows (e o Chrome) aceitam num caminho.
NOME_VIDEO, NOME_AUDIO = "video.mp4", "audio.m4a"


class ErroMidia(Exception):
    """`definitivo`: o arquivo nunca vai dar certo (sem áudio, codec sem decodificador) — não adianta tentar de novo."""

    def __init__(self, mensagem: str, definitivo: bool = False):
        super().__init__(mensagem)
        self.definitivo = definitivo


@dataclass
class Info:
    formato: str               # contêiner, como o FFmpeg o nomeia
    video: str | None          # codec do vídeo; None = só áudio (capa de álbum não conta como vídeo)
    audio: str | None
    pixel: str | None = None
    largura: int = 0
    altura: int = 0
    duracao: float = 0.0

    @property
    def tipo(self) -> str:
        return "video" if self.video else "audio"

    def descricao(self) -> str:
        return " + ".join(c for c in (self.video, self.audio) if c).upper().replace("_", "-")


def _capa(s) -> bool:
    try:
        import av
        return bool(s.disposition & av.stream.Disposition.attached_pic)
    except AttributeError:   # PyAV antigo: capa é uma imagem parada
        return s.codec_context is not None and s.codec_context.name in {"png", "mjpeg", "bmp", "gif"}


def _codec(s) -> str | None:
    if s is None or s.codec_context is None:   # sem decodificador para o stream: o PyAV deixa None
        return None
    return getattr(s.codec_context.codec, "canonical_name", None) or s.codec_context.name


def examinar(caminho: Path) -> Info:
    try:
        with _abrir(caminho) as c:
            videos = [s for s in c.streams.video if s.codec_context is not None and not _capa(s)]
            audios = [s for s in c.streams.audio if s.codec_context is not None]
            if not audios and len(c.streams.audio):
                raise ErroMidia(f"a trilha de áudio de {caminho.name} usa um codec que o FFmpeg embutido não "
                                "decodifica. Converta o arquivo para MP4 ou MP3 e tente de novo.", definitivo=True)
            v, a = (videos[0] if videos else None), (audios[0] if audios else None)
            return Info(
                formato=c.format.name,
                video=_codec(v),
                audio=_codec(a),
                pixel=getattr(v.codec_context, "pix_fmt", None) if v else None,
                largura=v.codec_context.width if v else 0,
                altura=v.codec_context.height if v else 0,
                duracao=float(c.duration or 0) / 1_000_000,
            )
    except ErroMidia:
        raise
    except Exception as e:  # noqa: BLE001 — av.FFmpegError e qualquer outra falha de leitura
        raise ErroMidia(f"não consegui ler {caminho.name} como vídeo ou áudio ({e}). "
                        "O arquivo pode estar incompleto ou corrompido.") from e


def _abrir(caminho: Path):
    import av
    return av.open(str(caminho))


def toca_no_navegador(info: Info, sufixo: str, universal: bool = False) -> bool:
    """Se a mídia toca como está. `universal`: também no Safari e em celulares (artefato);
    sem ele, basta tocar nos navegadores de computador (player local)."""
    mp4 = info.formato == CONTEINER_MP4
    if info.video:
        if mp4 and info.video == "h264" and info.pixel in PIXEL_WEB and info.audio in (None, "aac", "mp3"):
            return True
        return (not universal and sufixo == ".webm" and info.video in {"vp8", "vp9"}
                and info.audio in (None, "opus", "vorbis"))
    # Só áudio: converter é rápido, então só fica como está o que toca em qualquer navegador.
    return ((info.formato == "mp3" and info.audio == "mp3")
            or (mp4 and info.audio in {"aac", "mp3"})
            or (info.formato == "wav" and info.audio == "pcm_s16le")
            or (info.formato == "flac" and info.audio == "flac"))


def obter_ffmpeg() -> str:
    """ffmpeg do sistema ou o que vem no pacote imageio-ffmpeg (instalado com a ferramenta)."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _rodar(cmd: list[str]) -> bool:
    return subprocess.run(cmd, capture_output=True).returncode == 0


def converter(origem: Path, destino: Path, info: Info) -> bool:
    """Gera `destino` (.mp4 com H.264 + AAC, ou .m4a) a partir de qualquer mídia que o FFmpeg leia."""
    ffmpeg = obter_ffmpeg()
    base = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem)]
    fim = ["-movflags", "+faststart", str(destino)]
    if not info.video:
        return _rodar([*base, "-vn", "-map", "0:a:0", "-c:a", "aac", "-b:a", "128k", *fim])
    audio = ["-c:a", "copy"] if info.audio in {"aac", "mp3"} else ["-c:a", "aac", "-b:a", "128k"]
    mapa = ["-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn"]
    if info.video == "h264" and info.pixel in PIXEL_WEB:   # só troca o contêiner: segundos, sem perda
        if _rodar([*base, *mapa, "-c:v", "copy", *audio, *fim]):
            return True
    # O lado MENOR fica em até 720 (iw/ih já vêm com a rotação aplicada): vídeo de celular em pé não perde metade da resolução.
    escala = ["-vf", f"scale='if(gt(iw,ih),-2,trunc(min({ALTURA_MAX},iw)/2)*2)':'if(gt(iw,ih),trunc(min({ALTURA_MAX},ih)/2)*2,-2)'",
              "-pix_fmt", "yuv420p"]
    for codificador in (["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23"],      # placa NVIDIA, se houver
                        ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]):
        if _rodar([*base, *mapa, *escala, *codificador, *audio, *fim]):
            return True
    return False


def _mesmo_arquivo(a: Path, b: Path) -> bool:
    # Pelo nome, sem distinguir maiúsculas: no Windows e no APFS do Mac, X.MP4 e x.mp4 são o mesmo arquivo.
    try:
        return str(a.resolve()).casefold() == str(b.resolve()).casefold()
    except OSError:
        return str(a).casefold() == str(b).casefold()


def preparar_para_navegador(origem: Path, pasta: Path, info: Info, ocupado: Path | None = None) -> Path:
    """Devolve a mídia que o player vai tocar: o original, se o navegador já toca, ou uma cópia convertida.

    `ocupado`: onde o original vai morar depois (quando é movido para a pasta da degravação).
    """
    if toca_no_navegador(info, origem.suffix.lower()):
        return origem
    destino = pasta / (NOME_VIDEO if info.video else NOME_AUDIO)
    if any(_mesmo_arquivo(destino, outro) for outro in (origem, ocupado or origem)):
        destino = destino.with_stem(destino.stem + "-navegador")
    if info.video == "h264" and info.pixel in PIXEL_WEB and info.formato == CONTEINER_MP4:
        print(f"  ⚙ convertendo a trilha de áudio ({(info.audio or '').upper()}) para AAC, que o navegador toca; o vídeo é mantido…")
    elif info.video == "h264" and info.pixel in PIXEL_WEB:
        print(f"  ⚙ trocando o contêiner para {destino.suffix} (o navegador não abre {origem.suffix}); leva segundos…")
    elif info.video:
        print(f"  ⚙ convertendo o vídeo ({info.descricao()}) para MP4, que o navegador toca; pode levar alguns minutos…")
    else:
        print(f"  ⚙ convertendo o áudio ({info.descricao()}) para M4A, que o navegador toca…")
    if converter(origem, destino, info):
        return destino
    destino.unlink(missing_ok=True)
    print("  ⚠ conversão falhou; o player usará o arquivo original.")
    return origem
