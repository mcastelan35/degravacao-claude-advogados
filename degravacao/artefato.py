"""Gera uma página para publicar como artefato no claude.ai (vídeo + transcrição + estrutura).

O artefato aceita arquivos de até 15 MB, então a mídia é recomprimida para caber:
vídeo quando sobra taxa suficiente, só o áudio em gravações longas e, no limite,
apenas a transcrição. Com `sem_video`, nenhuma mídia sai do computador: a página leva só
o texto. A publicação em si é feita pelo Claude (ferramenta de artefatos).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .midia import ErroMidia, examinar, obter_ffmpeg, toca_no_navegador

LIMITE_MB = 14.0              # margem sob o teto de 15 MB por arquivo do artefato
VIDEO_MIN_KBPS = 180          # abaixo disso o vídeo fica ruim demais: publica só o áudio
AUDIO_MIN_KBPS = 24
# A cópia publicada nunca leva os metadados do original (localização GPS do celular, título, aparelho).
SEM_METADADOS = ["-map_metadata", "-1", "-map_chapters", "-1"]

# motivo de a página sair sem o vídeo (ou sem mídia nenhuma): vai para a ficha e para o aviso do player
MOTIVOS = {"": "", "sem_video": "sem_video", "ausente": "ausente", "ilegivel": "ilegivel", "tamanho": "tamanho"}


def _par(n: float) -> int:
    return max(2, int(round(n / 2)) * 2)


def _roda(cmd: list[str], saida: Path, limite_mb: float) -> bool:
    ok = subprocess.call(cmd) == 0 and saida.exists() and saida.stat().st_size <= limite_mb * 1e6
    if not ok:
        saida.unlink(missing_ok=True)
    return ok


def preparar_midia(origem: Path, destino: Path, duracao: float, sem_video: bool = False,
                   limite_mb: float = LIMITE_MB) -> tuple[Path | None, str, str]:
    """Prepara a mídia que cabe no limite. Devolve (arquivo, tipo, motivo).

    tipo: "video" | "audio" | "nenhuma". motivo: "" | "sem_video" (escolha de quem publica) |
    "ausente" | "ilegivel" | "tamanho" (o vídeo, ou a mídia toda, não coube no limite).
    """
    destino.mkdir(parents=True, exist_ok=True)
    for antigo in destino.glob("midia.*"):
        antigo.unlink()
    if sem_video:                      # só a transcrição: a gravação não sai do computador
        return None, "nenhuma", "sem_video"
    if not origem.exists():
        return None, "nenhuma", "ausente"
    try:
        info = examinar(origem)
    except (ErroMidia, Exception):     # noqa: BLE001 — qualquer falha de leitura: a página sai só com o texto
        return None, "nenhuma", "ilegivel"
    if not info.audio:
        return None, "nenhuma", "ilegivel"

    ffmpeg = obter_ffmpeg()
    segundos = max(duracao, 1)
    orcamento = limite_mb * 8000 / segundos                      # kbit/s para a mídia inteira
    taxa_original = origem.stat().st_size * 8 / 1000 / segundos  # kbit/s do arquivo de origem

    # Já cabe e toca em qualquer navegador (inclusive no celular): só troca o contêiner, sem recodificar,
    # descartando metadados, legendas e dados embutidos.
    if toca_no_navegador(info, origem.suffix.lower(), universal=True) and origem.stat().st_size <= limite_mb * 1e6:
        sufixo = ".mp4" if info.video else {"mp3": ".mp3", "wav": ".wav", "flac": ".flac"}.get(info.formato, ".m4a")
        copia = destino / f"midia{sufixo}"
        mp4 = ["-movflags", "+faststart"] if sufixo in (".mp4", ".m4a") else []
        if info.video:
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem), *SEM_METADADOS,
                   "-map", "0:v:0", "-map", "0:a:0", "-sn", "-dn", "-c", "copy", *mp4, str(copia)]
        else:
            cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem), *SEM_METADADOS,
                   "-vn", "-map", "0:a:0", "-sn", "-dn", "-c", "copy", *mp4, str(copia)]
        if _roda(cmd, copia, limite_mb):
            return copia, info.tipo, "copia"

    if info.video:
        # Nunca gastar mais que o original; o lado menor vira 720/480/360 sem ampliar. A escala é relativa
        # (iw/ih já vêm com a rotação aplicada), então vídeos em pé do celular saem na proporção certa.
        orcamento_video = min(orcamento, taxa_original * 1.05)
        if orcamento_video >= VIDEO_MIN_KBPS:
            audio_k = 64
            video_k = int(orcamento_video * 0.9) - audio_k
            lado = 720 if video_k >= 1000 else 480 if video_k >= 450 else 360
            escala = (f"scale='if(gt(iw,ih),-2,trunc(min({lado},iw)/2)*2)':"
                      f"'if(gt(iw,ih),trunc(min({lado},ih)/2)*2,-2)',setsar=1")
            saida = destino / "midia.mp4"
            for tentativa in (1.0, 0.8):
                vk = int(video_k * tentativa)
                cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem), *SEM_METADADOS,
                       "-map", "0:v:0", "-map", "0:a:0", "-sn", "-dn", "-vf", escala, "-pix_fmt", "yuv420p",
                       "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{vk}k",
                       "-maxrate", f"{int(vk * 1.3)}k", "-bufsize", f"{vk * 2}k",
                       "-c:a", "aac", "-b:a", f"{audio_k}k", "-ac", "1", "-movflags", "+faststart", str(saida)]
                if _roda(cmd, saida, limite_mb):
                    return saida, "video", ""

    # Só o áudio: a taxa do original limita a qualidade, mas nunca abaixo do mínimo audível (notas de voz
    # do WhatsApp a 16 kbps e AMR a 12 kbps cabem com folga e saem a 24 kbps).
    ak = int(min(96, orcamento * 0.9, max(AUDIO_MIN_KBPS, taxa_original * 1.05)))
    if ak >= AUDIO_MIN_KBPS:
        saida = destino / "midia.m4a"
        cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(origem), *SEM_METADADOS, "-vn", "-map", "0:a:0",
               "-c:a", "aac", "-b:a", f"{ak}k", "-ac", "1", "-movflags", "+faststart", str(saida)]
        if _roda(cmd, saida, limite_mb):
            return saida, "audio", "tamanho" if info.video else ""
    return None, "nenhuma", "tamanho"


# ---------------------------------------------------------------- página

def descrever_midia(dados: dict, tipo: str, motivo: str) -> str:
    """Texto da ficha "Mídia nesta página": diz a verdade sobre o que foi publicado e por quê."""
    so_audio = dados.get("tipo_midia") == "audio"   # a gravação já era só áudio
    copia = motivo == "copia"                        # o original já cabia: foi só copiado, sem os metadados
    if tipo == "video":
        return "vídeo (cópia do original, sem metadados)" if copia else "vídeo recomprimido para o limite de 15 MB do artefato"
    if tipo == "audio":
        if so_audio:
            return "áudio (cópia do original, sem metadados)" if copia else "áudio"
        return "só o áudio (o vídeo não cabe no limite de 15 MB do artefato)"
    return {"sem_video": "sem a gravação, por escolha de quem publicou (só a transcrição)",
            "ausente": "sem a gravação (o arquivo original não foi encontrado)",
            "ilegivel": "sem a gravação (não foi possível ler o arquivo original)",
            "tamanho": "sem a gravação (longa demais para o limite de 15 MB do artefato)"}.get(motivo, "sem a gravação")


def gerar_pagina(dados: dict, md_doc: str, titulo: str, midia: Path | None, tipo: str, motivo: str = "") -> str:
    """Mesma página do player local (player.py), no modo artefato."""
    from .player import gerar_html

    return gerar_html(dados, md_doc, titulo, f"midia/{midia.name}" if midia else "", tipo, "artefato",
                      ficha_extra=[["Mídia nesta página", descrever_midia(dados, tipo, motivo)]], motivo=motivo)
