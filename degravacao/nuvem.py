"""Pastas sincronizadas com a nuvem (Google Drive, OneDrive/SharePoint, Dropbox, iCloud) e as pastas
Documentos e Downloads do usuário.

Só biblioteca padrão: é usado pelo diagnóstico antes de a ferramenta estar instalada.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def pasta_documentos() -> Path:
    """Documentos do usuário. No Windows com "backup de pastas" do OneDrive, e no Mac com "Mesa e Documentos
    no iCloud", essa pasta fica DENTRO da nuvem: quem precisa de pasta local confere com servico_nuvem()."""
    if os.name == "nt":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:   # CSIDL_PERSONAL
                return Path(buf.value)
        except Exception:  # noqa: BLE001
            pass
    return Path.home() / "Documents"


def pasta_downloads() -> Path:
    """Downloads do usuário (no Windows, a pasta conhecida, que pode ter sido movida de unidade)."""
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                            ("Data4", wintypes.BYTE * 8)]

            downloads = GUID(0x374DE290, 0x123F, 0x4565, (wintypes.BYTE * 8)(0x91, 0x64, 0x39, 0xC4, 0x92, 0x5E, 0x46, 0x7B))
            ponteiro = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(downloads), 0, None, ctypes.byref(ponteiro)) == 0 and ponteiro.value:
                caminho = Path(ponteiro.value)
                ctypes.windll.ole32.CoTaskMemFree(ponteiro)
                return caminho
        except Exception:  # noqa: BLE001
            pass
    return Path.home() / "Downloads"


def _unidades_windows() -> list[str]:
    if hasattr(os, "listdrives"):   # Python 3.12+
        try:
            return [d.rstrip("\\/") for d in os.listdrives()]
        except OSError:
            pass
    return [f"{letra}:" for letra in "DEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{letra}:\\")]


def _onedrive_windows() -> list[Path]:
    """Pastas do OneDrive: a pessoal/corporativa (variáveis de ambiente) e cada biblioteca sincronizada
    (SharePoint, Teams), registradas pelo cliente com o ponto de montagem."""
    pastas = [Path(os.environ[v]) for v in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive") if os.environ.get(v)]
    try:
        import winreg
    except ImportError:
        return pastas

    def subchaves(raiz: str):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, raiz) as k:
                n = 0
                while True:
                    try:
                        nome = winreg.EnumKey(k, n)
                    except OSError:
                        return
                    n += 1
                    yield raiz + "\\" + nome
        except OSError:
            return

    def valor(chave: str, nome: str) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, chave) as k:
                v, _ = winreg.QueryValueEx(k, nome)
                return v if isinstance(v, str) and v else None
        except OSError:
            return None

    for chave in subchaves(r"Software\SyncEngines\Providers\OneDrive"):
        ponto = valor(chave, "MountPoint")
        if ponto:
            pastas.append(Path(ponto))
    for conta in subchaves(r"Software\Microsoft\OneDrive\Accounts"):
        raiz = valor(conta, "UserFolder")
        if raiz:
            pastas.append(Path(raiz))
    return pastas


def _finder_diz(chave: str) -> bool:
    """Preferência do Finder no macOS (1 = ligada), ex.: FXICloudDriveDocuments."""
    import subprocess
    try:
        r = subprocess.run(["defaults", "read", "com.apple.finder", chave], capture_output=True, text=True, timeout=10)
        return r.returncode == 0 and r.stdout.strip() == "1"
    except (OSError, subprocess.TimeoutExpired):
        return False


def pastas_nuvem() -> list[tuple[str, Path]]:
    """(serviço, pasta) das nuvens sincronizadas encontradas neste computador."""
    casa, achadas = Path.home(), []

    def add(nome: str, p: Path) -> None:
        try:
            if p.is_dir():
                achadas.append((nome, p))
        except OSError:
            pass

    if os.name == "nt":
        for unidade in _unidades_windows():   # Google Drive para computador: unidade virtual inteira (G:, H:…)
            if any(Path(f"{unidade}\\{nome}").is_dir() for nome in ("Meu Drive", "My Drive")):
                add("Google Drive", Path(f"{unidade}\\"))   # inclui "Drives compartilhados" e "Outros computadores"
        for nome in ("Meu Drive", "My Drive", "Google Drive"):
            add("Google Drive", casa / nome)
        for p in _onedrive_windows():
            add("OneDrive", p)
        add("iCloud Drive", casa / "iCloudDrive")
    elif sys.platform == "darwin":
        nuvem = casa / "Library" / "CloudStorage"
        for conta in sorted(nuvem.glob("GoogleDrive-*")) if nuvem.is_dir() else []:
            add("Google Drive", conta)                      # a conta inteira, com os drives compartilhados
        for conta in sorted(nuvem.glob("OneDrive*")) if nuvem.is_dir() else []:
            add("OneDrive", conta)
        for conta in sorted(nuvem.glob("Dropbox*")) if nuvem.is_dir() else []:
            add("Dropbox", conta)
        add("iCloud Drive", casa / "Library" / "Mobile Documents" / "com~apple~CloudDocs")
        # "Mesa e Documentos no iCloud": as pastas continuam em ~/Documents e ~/Desktop, sincronizadas no lugar.
        for pasta, chave in (("Documents", "FXICloudDriveDocuments"), ("Desktop", "FXICloudDriveDesktop")):
            if _finder_diz(chave):
                add("iCloud Drive", casa / pasta)
    infos = [casa / ".dropbox" / "info.json"]   # o Dropbox registra onde está cada conta (pessoal, empresa)
    infos += [Path(os.environ[v]) / "Dropbox" / "info.json" for v in ("APPDATA", "LOCALAPPDATA") if os.environ.get(v)]
    for info in infos:
        try:
            for conta in json.loads(info.read_text(encoding="utf-8")).values():
                add("Dropbox", Path(conta["path"]))
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    add("Dropbox", casa / "Dropbox")

    vistas, unicas = set(), []
    for nome, p in achadas:
        try:
            chave = os.path.normcase(str(p.resolve()))
        except OSError:
            continue
        if chave not in vistas:
            vistas.add(chave)
            unicas.append((nome, p))
    return unicas


def servico_nuvem(caminho: Path, pastas: list[tuple[str, Path]] | None = None) -> str | None:
    """Nome do serviço de nuvem que sincroniza `caminho`, ou None se a pasta é só local.

    Resolve atalhos e redirecionamentos: a pasta Documentos movida para o OneDrive ou para o iCloud
    conta como nuvem."""
    try:
        alvo = caminho.resolve()
    except OSError:
        return None
    for nome, raiz in pastas if pastas is not None else pastas_nuvem():
        try:
            raiz = raiz.resolve()
        except OSError:
            continue
        if alvo == raiz or raiz in alvo.parents:
            return nome
    return None
