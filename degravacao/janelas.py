"""Janelas do sistema para escolher pastas e arquivos (Windows, Mac e Linux).

Ordem de tentativa: no Mac, o diálogo nativo via osascript (o Python do Homebrew não traz
tkinter); nos demais, tkinter e, no Windows, PowerShell como reserva. Sem nenhuma interface
gráfica, pergunta no terminal — e, sem terminal (Claude Code), devolve nada.

Títulos e caminhos nunca entram no texto dos scripts: no PowerShell vão por variáveis de ambiente
e no AppleScript são escapados — um nome de pasta com aspas ou apóstrofos não vira comando.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from .fontes import EXT_MIDIA

_INDISPONIVEL = object()   # a janela não pôde ser aberta (≠ usuário cancelou)
_ESPERA = 30 * 60          # segundos até desistir de uma janela esquecida aberta


def _tk(funcao: str, **kw):
    try:
        import tkinter as tk
        from tkinter import filedialog
        raiz = tk.Tk()
    except Exception:  # noqa: BLE001 — sem tkinter ou sem tela
        return _INDISPONIVEL
    try:
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        r = getattr(filedialog, funcao)(parent=raiz, **kw)
        return "\n".join(r) if isinstance(r, tuple) else (r or "")
    except Exception:  # noqa: BLE001
        return _INDISPONIVEL
    finally:
        raiz.destroy()


def _osascript(script: str):
    cmd = ["osascript"]
    # "activate" traz o osascript para a frente: sem isso a janela pode abrir atrás das outras.
    for linha in ["activate", *script.splitlines()]:
        cmd += ["-e", linha]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=_ESPERA)
    except (OSError, subprocess.TimeoutExpired):
        return _INDISPONIVEL
    if r.returncode != 0:
        return "" if "-128" in r.stderr else _INDISPONIVEL   # -128 = o usuário cancelou
    return r.stdout


def _powershell(script: str, **dados: str):
    """Roda o script com `dados` em variáveis de ambiente DEG_<NOME> (o script lê $env:DEG_<NOME>)."""
    prefixo = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Add-Type -AssemblyName System.Windows.Forms; "
    ambiente = {**os.environ, **{f"DEG_{k.upper()}": v for k, v in dados.items()}}
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", prefixo + script],
                           capture_output=True, text=True, encoding="utf-8", timeout=_ESPERA, env=ambiente)
    except (OSError, subprocess.TimeoutExpired):
        return _INDISPONIVEL
    return r.stdout if r.returncode == 0 else _INDISPONIVEL


def _as(s: str) -> str:
    """Escapa para dentro de uma string AppleScript; cada linha do script vira um -e, então quebras de linha saem."""
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return "".join(" " if c in "\n\r\x0b\x0c\x85  " else c for c in s)


def _terminal(pergunta: str):
    if not sys.stdin.isatty():
        return ""
    return input(f"{pergunta}\nCole o caminho e tecle Enter: ").strip().strip('"')


def _primeira(tentativas) -> str:
    for t in tentativas:
        r = t()
        if r is not _INDISPONIVEL:
            return r
    return ""


def escolher_pasta(titulo: str, inicial: Path) -> Path | None:
    inicial = inicial if inicial.is_dir() else Path.home()
    tentativas = [lambda: _tk("askdirectory", title=titulo, initialdir=str(inicial), mustexist=True)]
    if sys.platform == "darwin":
        tentativas.insert(0, lambda: _osascript(
            f'POSIX path of (choose folder with prompt "{_as(titulo)}" default location (POSIX file "{_as(str(inicial))}"))'))
    elif os.name == "nt":
        tentativas.append(lambda: _powershell(
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog; $d.Description = $env:DEG_TITULO; "
            "$d.SelectedPath = $env:DEG_INICIO; "
            "if ($d.ShowDialog((New-Object System.Windows.Forms.Form -Property @{TopMost = $true})) -eq 'OK') { $d.SelectedPath }",
            titulo=titulo, inicio=str(inicial)))
    tentativas.append(lambda: _terminal(titulo))
    r = _primeira(tentativas).strip()
    return Path(r).expanduser() if r else None


def escolher_arquivos(titulo: str, inicial: Path) -> list[Path]:
    inicial = inicial if inicial.is_dir() else Path.home()
    padroes = " ".join(f"*{e}" for e in sorted(EXT_MIDIA))
    tentativas = [lambda: _tk("askopenfilenames", title=titulo, initialdir=str(inicial),
                              filetypes=[("Vídeos e áudios", padroes), ("Todos os arquivos", "*.*")])]
    if sys.platform == "darwin":
        tentativas.insert(0, lambda: _osascript(
            f'set fs to choose file with prompt "{_as(titulo)}" default location (POSIX file "{_as(str(inicial))}") '
            'with multiple selections allowed\n'
            'set out to ""\nrepeat with f in fs\nset out to out & POSIX path of f & linefeed\nend repeat\nreturn out'))
    elif os.name == "nt":
        filtro = "Vídeos e áudios|" + ";".join(f"*{e}" for e in sorted(EXT_MIDIA)) + "|Todos os arquivos|*.*"
        tentativas.append(lambda: _powershell(
            "$d = New-Object System.Windows.Forms.OpenFileDialog; $d.Title = $env:DEG_TITULO; $d.Multiselect = $true; "
            "$d.Filter = $env:DEG_FILTRO; $d.InitialDirectory = $env:DEG_INICIO; "
            "if ($d.ShowDialog((New-Object System.Windows.Forms.Form -Property @{TopMost = $true})) -eq 'OK') { $d.FileNames -join \"`n\" }",
            titulo=titulo, inicio=str(inicial), filtro=filtro))
    tentativas.append(lambda: _terminal(titulo))
    return [Path(linha.strip()).expanduser() for linha in _primeira(tentativas).splitlines() if linha.strip()]
