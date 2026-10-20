"""Funções auxiliares: minutagem, slugs e caminhos."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote


def minutagem(segundos: float, milis: bool = False, sep: str = ".") -> str:
    """Converte segundos em HH:MM:SS (ou HH:MM:SS.mmm)."""
    try:
        segundos = min(max(0.0, float(segundos)), 99 * 3600 + 59 * 60 + 59)   # dado estranho nunca derruba um documento
    except (TypeError, ValueError):
        segundos = 0.0
    total_ms = int(round(segundos * 1000))
    h, resto = divmod(total_ms, 3_600_000)
    m, resto = divmod(resto, 60_000)
    s, ms = divmod(resto, 1000)
    base = f"{h:02d}:{m:02d}:{s:02d}"
    return f"{base}{sep}{ms:03d}" if milis else base


def duracao_por_extenso(segundos: float) -> str:
    h, resto = divmod(int(round(segundos)), 3600)
    m, s = divmod(resto, 60)
    partes = []
    if h:
        partes.append(f"{h} h")
    if m:
        partes.append(f"{m} min")
    if s or not partes:
        partes.append(f"{s} s")
    return " ".join(partes)


def slugify(texto: str, limite: int = 60) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return (texto[:limite].rstrip("-")) or "midia"


def src_relativo(arquivo: Path, pasta_base: Path) -> str:
    """Caminho do vídeo para usar no player.html (relativo quando possível)."""
    try:
        rel = os.path.relpath(arquivo.resolve(), pasta_base.resolve())
        return "/".join(quote(p) for p in Path(rel).parts)
    except ValueError:  # Windows: unidades diferentes (C:\ x D:\)
        return arquivo.resolve().as_uri()
