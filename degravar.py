#!/usr/bin/env python3
"""Degravação de vídeos e áudios para advogados — ponto de entrada único.

Uso rápido:
    python degravar.py instalar                     # 1ª vez: cria .venv e instala dependências
    python degravar.py configurar                   # escolhe (numa janela) a pasta dos vídeos
    python degravar.py "https://drive.google.com/file/d/…/view"
    python degravar.py "C:\\Audiencias\\audiencia.mp4"
    python degravar.py                              # degrava o que houver de novo na pasta escolhida
    python degravar.py audiencia.mp4 --num-falantes 3   # também separa quem fala
    python degravar.py transcrever --monitorar      # vigia entrada/ e degrava o que chegar
    python degravar.py assistir                     # abre o player da última degravação
    python degravar.py listar
    python degravar.py artefato <nome>              # prepara página + mídia para publicar no claude.ai
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def _raiz_em_plugins() -> bool:
    """O código mora na pasta de plugins do Claude Code (a padrão, ou a indicada por variável de ambiente)?"""
    try:
        raiz = RAIZ.resolve()
    except OSError:
        raiz = RAIZ
    bases = [Path.home() / ".claude" / "plugins"]
    for var in ("CLAUDE_CODE_PLUGIN_CACHE_DIR", "CLAUDE_CODE_PLUGIN_SEED_DIR"):
        if os.environ.get(var):
            bases.append(Path(os.environ[var]))
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        bases.append(Path(os.environ["CLAUDE_CONFIG_DIR"]) / "plugins")
    for base in bases:
        try:
            base = base.resolve()
        except OSError:
            continue
        if raiz == base or base in raiz.parents:
            return True
    nomes = [p.name.lower() for p in raiz.parents]
    return any(p.name == "plugins" and p.parent.name == ".claude" for p in raiz.parents) or (
        "plugins" in nomes and ("cache" in nomes or "marketplaces" in nomes))


# Instalado como plugin do Claude Code, o código é trocado a cada versão: ambiente, preferências, modelos e
# degravações ficam em pastas do usuário. A skill do plugin chama o script com `--plugin`, o sinal explícito;
# a localização do código é a reserva. No repositório, tudo fica nele mesmo.
MODO_PLUGIN = "--plugin" in sys.argv[1:] or os.environ.get("DEGRAVAR_PLUGIN") == "1" or _raiz_em_plugins()


def _pasta_dados() -> Path:
    if os.environ.get("DEGRAVAR_DADOS"):
        return Path(os.environ["DEGRAVAR_DADOS"]).expanduser()
    if not MODO_PLUGIN:
        return RAIZ
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Degravacao"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Degravacao"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "degravacao"


DADOS = _pasta_dados()
VENV = DADOS / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
INSTALADO = VENV / ".instalado"        # gravado só no fim de uma instalação completa
PYTHON_RECOMENDADO = "3.12"

# Acentos e símbolos no terminal do Windows; saída linha a linha também quando vai para um arquivo ou
# para o Claude Code em segundo plano (senão o progresso só aparece quando o buffer enche).
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", line_buffering=True)
    except Exception:  # noqa: BLE001
        pass


def passo(sub: str) -> str:
    """Como pedir um comando da ferramenta, conforme o modo: no repositório, a linha a digitar;
    no plugin, não há terminal nem atalho — é o Claude quem roda."""
    if MODO_PLUGIN:
        return f"peça ao Claude para rodar o comando `{sub}` da Degravação"
    return f"rode  python degravar.py {sub}"


def _dentro_da_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def _venv_funciona() -> bool:
    """A .venv pode ter perdido o Python base (desinstalado, ou a pasta foi movida)."""
    try:
        return subprocess.run([str(VENV_PY), "-c", "pass"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ambiente_completo() -> bool:
    """As dependências principais importam no Python da .venv (instalação que chegou ao fim)."""
    try:
        return subprocess.run([str(VENV_PY), "-c", "import faster_whisper, sherpa_onnx, imageio_ffmpeg, av"],
                              capture_output=True, timeout=180).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def tem_nvidia() -> bool:
    """Placa NVIDIA com driver instalado (o nvidia-smi vem com o driver)."""
    import shutil
    if not shutil.which("nvidia-smi"):
        return False
    try:
        return subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def achar_uv() -> str | None:
    """O uv (astral.sh/uv) instala Python e dependências sem administrador; o instalador oficial
    o põe em ~/.local/bin, que só entra no PATH de terminais abertos depois."""
    import shutil
    exe = shutil.which("uv")
    if exe:
        return exe
    nome = "uv.exe" if os.name == "nt" else "uv"
    for pasta in (Path.home() / ".local" / "bin", Path.home() / ".cargo" / "bin"):
        if (pasta / nome).exists():
            return str(pasta / nome)
    return None


def _caminhos_longos_liberados() -> bool:
    """Windows com LongPathsEnabled: o limite de 260 caracteres não vale para o Python e o pip."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\FileSystem") as k:
            return winreg.QueryValueEx(k, "LongPathsEnabled")[0] == 1
    except (OSError, ImportError):
        return False


LIMITE_VENV = 120   # o arquivo mais fundo da .venv tem ~120 caracteres: acima disso estoura os 260 do Windows


def caminho_longo_demais() -> bool:
    return os.name == "nt" and len(str(VENV)) > LIMITE_VENV and not _caminhos_longos_liberados()


def _arm64_windows() -> bool:
    import platform
    return os.name == "nt" and platform.machine().upper() in {"ARM64", "AARCH64"}


def instalar(baixar_modelo: str | None, gpu: bool = True) -> int:
    import shutil
    if caminho_longo_demais():
        print(f"✗ O caminho desta pasta é longo demais para o Windows ({len(str(VENV))} caracteres):\n  {VENV}\n"
              "  Mova a pasta da ferramenta para mais perto da raiz (ex.: C:\\Degravacao) e rode de novo.")
        return 1
    uv = achar_uv()
    python_ok = (3, 11) <= sys.version_info[:2] <= (3, 14)
    if not uv and not python_ok:
        print(f"✗ Este Python é o {sys.version.split()[0]}; a ferramenta precisa do Python 3.11 a 3.14.\n"
              "  O jeito mais simples é instalar o uv (sem administrador), que traz o Python certo:\n"
              '    Windows: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"\n'
              "    Mac:     curl -LsSf https://astral.sh/uv/install.sh | sh")
        return 1
    if _arm64_windows() and not uv and "ARM" in __import__("platform").machine().upper():
        import platform
        if platform.architecture()[0] and "ARM" in (sysconfig_plat := __import__("sysconfig").get_platform()).upper():
            print(f"✗ Este Python é nativo ARM64 ({sysconfig_plat}) e as bibliotecas de transcrição só existem para x64.\n"
                  "  Instale o uv (ele baixa um Python x64, que roda emulado neste computador) e rode de novo:\n"
                  '    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"')
            return 1
    DADOS.mkdir(parents=True, exist_ok=True)
    if VENV_PY.exists() and not _dentro_da_venv():   # rodando no próprio ambiente, nunca o apaga: o pip completa o que faltar
        if not _venv_funciona():
            print("• o ambiente não funciona mais (Python removido ou pasta movida): recriando…")
            shutil.rmtree(VENV, ignore_errors=True)
        elif not INSTALADO.exists() and not _ambiente_completo():
            # Instalação interrompida (rede caiu, janela fechada): recomeça do zero. Um ambiente completo de
            # versões anteriores (sem o marcador) é aproveitado como está.
            print("• ambiente incompleto de uma instalação anterior: recriando…")
            shutil.rmtree(VENV, ignore_errors=True)
    if not VENV_PY.exists():
        print(f"• criando o ambiente em {VENV} …")
        if uv:   # baixa um Python 3.12 próprio se preciso: não depende do Python instalado no computador
            # Em Windows ARM64 (Snapdragon), as bibliotecas só têm versão x64, que roda emulada.
            versao = f"cpython-{PYTHON_RECOMENDADO}-windows-x86_64-none" if _arm64_windows() else PYTHON_RECOMENDADO
            subprocess.check_call([uv, "venv", "--python", versao, str(VENV)])
        else:
            subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])

    def pip(*args: str) -> int:
        if uv:
            return subprocess.call([uv, "pip", "install", "--python", str(VENV_PY), *args])
        return subprocess.call([str(VENV_PY), "-m", "pip", "install", *args])

    print("• instalando dependências (faster-whisper, separação de falantes, ffmpeg)…")
    if not uv:
        pip("--upgrade", "pip", "-q")
    if pip("-r", str(RAIZ / "requirements.txt")) != 0:
        print("✗ A instalação das dependências falhou. Copie a mensagem acima e peça ajuda ao Claude.\n"
              "  (Sem rede? Tente de novo quando a conexão voltar: a instalação recomeça sozinha.)")
        return 1
    com_gpu = False
    if gpu and sys.platform != "darwin" and tem_nvidia():
        print("• placa NVIDIA encontrada: instalando as bibliotecas CUDA (~2 GB, só na primeira vez)…")
        com_gpu = pip("-r", str(RAIZ / "requirements-gpu.txt")) == 0
        if not com_gpu:
            print("  ⚠ não foi possível instalar as bibliotecas CUDA; a transcrição roda na CPU.")
    # O marcador diz que a instalação chegou ao fim (e se as bibliotecas da placa ficaram de fora).
    INSTALADO.write_text((RAIZ / "requirements.txt").read_text(encoding="utf-8")
                         + ("" if com_gpu or not gpu else "") + ("\n# sem-gpu\n" if not gpu else ""), encoding="utf-8")
    if baixar_modelo:
        print(f"• baixando modelo Whisper '{baixar_modelo}' (pode levar alguns minutos)…")
        subprocess.check_call([str(VENV_PY), str(RAIZ / "degravar.py"), *(["--plugin"] if MODO_PLUGIN else []),
                               "_baixar_modelo", baixar_modelo])
    print(f"\n✓ Instalação concluída. Próximo passo: configurar as pastas ({passo('configurar')}).")
    return 0


# Se a .venv existe e não estamos nela, reexecuta o script com o Python da .venv.
if __name__ == "__main__" and VENV_PY.exists() and not _dentro_da_venv() and "instalar" not in sys.argv[1:2] + sys.argv[2:3]:
    if _venv_funciona():
        sys.exit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))
    print(f"⚠ O ambiente em {VENV} não funciona mais (Python removido ou pasta movida). Para recriá-lo, {passo('instalar')}.")

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
import webbrowser  # noqa: E402
from datetime import datetime  # noqa: E402

from degravacao import documento, fontes  # noqa: E402
from degravacao.util import minutagem, slugify, src_relativo  # noqa: E402

PREFERENCIAS = DADOS / "config" / "preferencias.json"
IGNORADOS = DADOS / "config" / "ignorados.json"   # mídias que nunca vão dar certo (sem áudio): não são tentadas de novo
MODELOS_FALANTES = DADOS / "modelos"
ENTRADA_PADRAO = DADOS / "entrada"
# No plugin, o vocabulário editável fica com os dados (sobrevive às atualizações); nasce da cópia padrão.
VOCABULARIO = DADOS / "config" / "vocabulario.txt"
if not VOCABULARIO.exists() and (RAIZ / "config" / "vocabulario.txt").exists() and DADOS != RAIZ:
    VOCABULARIO.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RAIZ / "config" / "vocabulario.txt", VOCABULARIO)


def carregar_preferencias() -> dict:
    try:
        return json.loads(PREFERENCIAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar_json(caminho: Path, dados: dict) -> None:
    """Escrita atômica: o arquivo só é trocado depois de todo o conteúdo estar gravado. Um erro no meio
    (texto com caractere inválido, disco cheio) nunca deixa o transcricao.json zerado."""
    texto = json.dumps(dados, ensure_ascii=False, indent=1)
    tmp = caminho.with_suffix(caminho.suffix + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, caminho)


def pasta_local_padrao() -> Path:
    """Pasta de saída fora de qualquer nuvem: Documentos, se não for sincronizada (backup do OneDrive,
    iCloud); senão a pasta do usuário; em último caso, a pasta de dados da ferramenta."""
    from degravacao.nuvem import pasta_documentos, pastas_nuvem, servico_nuvem
    nuvens = pastas_nuvem()
    for base in (pasta_documentos(), Path.home()):
        if not servico_nuvem(base, nuvens):
            return base / "Degravações"
    return DADOS / "Degravações"


PREFS = carregar_preferencias()
ENTRADA = Path(PREFS["pasta_entrada"]) if PREFS.get("pasta_entrada") else ENTRADA_PADRAO
SAIDA_PADRAO = RAIZ / "saida" if DADOS == RAIZ else pasta_local_padrao()
SAIDA = Path(PREFS["pasta_saida"]) if PREFS.get("pasta_saida") else SAIDA_PADRAO
# Só a caixa de entrada interna (entrada/) move os vídeos; numa pasta escolhida pelo usuário
# os originais nunca são movidos nem alterados — o que já foi degravado é apenas pulado.
MOVER_DA_ENTRADA = ENTRADA.resolve() == ENTRADA_PADRAO.resolve()
DOWNLOADS = SAIDA / ".baixando"


# ---------------------------------------------------------------- utilidades

def exibir(caminho: Path) -> str:
    """Caminho curto para mensagens: relativo ao repositório quando estiver dentro dele."""
    try:
        return str(caminho.resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def _ler_json(caminho: Path) -> dict | None:
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return None
    return dados if isinstance(dados, dict) else None


_avisados_ilegiveis: set[Path] = set()


def processados() -> dict[str, Path]:
    """Mapa chave-da-fonte → pasta, a partir das degravações já existentes (na pasta de saída atual e nas
    anteriores, para uma troca de pasta não refazer tudo)."""
    mapa: dict[str, Path] = {}
    pastas = [SAIDA] + [Path(p) for p in PREFS.get("saidas_anteriores", []) if Path(p) != SAIDA]
    for base in pastas:
        try:
            jsons = list(base.glob("*/transcricao.json"))
        except OSError:
            continue
        for j in jsons:
            d = _ler_json(j)
            if d is None:
                if j not in _avisados_ilegiveis:   # uma vez por execução (o monitor repete a varredura)
                    _avisados_ilegiveis.add(j)
                    print(f"  ⚠ {j.parent.name}: transcricao.json ilegível (arquivo danificado ou editado à mão); ignorado.")
                continue
            if d.get("chave") and d["chave"] not in mapa:
                mapa[d["chave"]] = j.parent
    return mapa


def carregar_ignorados() -> dict[str, str]:
    return _ler_json(IGNORADOS) or {}


def registrar_ignorado(chave: str, motivo: str) -> None:
    dados = carregar_ignorados()
    dados[chave] = motivo
    IGNORADOS.parent.mkdir(parents=True, exist_ok=True)
    gravar_json(IGNORADOS, dados)


def pasta_destino(slug: str, chave: str, mapa: dict[str, Path]) -> Path:
    if chave in mapa and mapa[chave].parent == SAIDA:
        return mapa[chave]
    pasta, n = SAIDA / slug, 2
    while pasta.exists():
        pasta, n = SAIDA / f"{slug}-{n}", n + 1
    return pasta


def carregar_vocabulario(extra: str | None) -> str:
    termos: list[str] = []
    if extra:
        termos += [t.strip() for t in extra.split(",") if t.strip()]
    if VOCABULARIO.exists():
        for linha in VOCABULARIO.read_text(encoding="utf-8").splitlines():
            linha = linha.split("#", 1)[0].strip()
            if linha:
                termos += [t.strip() for t in linha.split(",") if t.strip()]
    vistos, unicos = set(), []
    for t in termos:
        if t.lower() not in vistos:
            vistos.add(t.lower())
            unicos.append(t)
    return ", ".join(unicos)


def midia_da_degravacao(pasta: Path, dados: dict) -> tuple[Path, Path]:
    """(original, cópia que o player toca). Se a pasta foi movida ou restaurada de backup, os caminhos
    absolutos gravados não valem mais: procura pelo nome dentro da própria pasta e atualiza o JSON."""
    mudou = False
    caminhos = {}
    for chave in ("caminho_midia", "caminho_video"):
        p = Path(dados.get(chave) or "")
        local = pasta / p.name
        # Numa pasta copiada ou movida, o arquivo que está dentro dela vale mais que o caminho antigo.
        if dados.get(chave) and local.is_file() and (not p.exists() or local.resolve() != p.resolve()):
            p = local.resolve()
            dados[chave] = str(p)
            mudou = True
        caminhos[chave] = p
    if mudou:
        gravar_json(pasta / "transcricao.json", dados)
    return caminhos["caminho_midia"], caminhos["caminho_video"]


def regravar_documentos(pasta: Path, dados: dict) -> tuple[Path, bool | None, bool]:
    """(Re)gera .md, legendas, Word e player preservando a seção já estruturada pelo Claude.

    Devolve (md, preservada, word_ok): preservada é True se havia estrutura e foi mantida, False se o .md
    tinha perdido os marcadores (a seção anterior não pôde ser reaproveitada; avisa), None se ainda não
    havia estrutura. word_ok diz se o .docx foi gravado.
    """
    from degravacao.player import gerar_player

    titulo = dados["titulo"]
    md = pasta / f"{dados['slug']}.md"
    estrutura_antiga, preservada = None, None
    if md.exists():
        atual = md.read_text(encoding="utf-8")
        ini, fim = atual.find(documento.MARCA_CLAUDE_INI), atual.find(documento.MARCA_CLAUDE_FIM)
        if 0 <= ini < fim:
            if documento.secao_estruturada(atual):   # só o que o Claude escreveu; o marcador "Pendente" não conta
                estrutura_antiga, preservada = atual[ini:fim], True
        elif "## Resumo executivo" in atual or "## Estrutura de tópicos" in atual:
            preservada = False
            print(f"  ⚠ os marcadores CLAUDE:ESTRUTURA tinham sumido de {md.name}: a seção estruturada volta ao padrão "
                  "(o texto anterior continua no histórico do arquivo, se houver).")
    md = documento.salvar_tudo(pasta, dados, titulo)
    texto = md.read_text(encoding="utf-8")
    if estrutura_antiga:
        ini, fim = texto.find(documento.MARCA_CLAUDE_INI), texto.find(documento.MARCA_CLAUDE_FIM)
        texto = texto[:ini] + estrutura_antiga + texto[fim:]
        md.write_text(texto, encoding="utf-8")
    _, video = midia_da_degravacao(pasta, dados)
    # O player e o Word levam o resumo e a estrutura do .md: depois de estruturar, `regerar` os atualiza.
    gerar_player(pasta, dados, titulo, src_relativo(video, pasta), texto)
    from degravacao.word import gerar_docx
    word_ok = True
    try:
        (pasta / f"{dados['slug']}.docx").write_bytes(gerar_docx(dados, titulo, texto))
    except PermissionError:
        word_ok = False
        print(f"  ⚠ {dados['slug']}.docx está aberto no Word: feche-o e {passo('regerar ' + dados['slug'])}")
    except Exception as e:  # noqa: BLE001 — o Word não pode derrubar o resto
        word_ok = False
        print(f"  ⚠ não foi possível gerar o Word ({e}).")
    return md, preservada, word_ok


def guardar_copia(pasta: Path, motivo: str) -> Path | None:
    """Cópia datada do transcricao.json antes de uma operação que descarta trabalho manual."""
    anterior = pasta / "transcricao.json"
    if not anterior.exists():
        return None
    base = f"transcricao-antes-{motivo}-{datetime.now():%Y%m%d-%H%M%S}"
    copia, n = pasta / f"{base}.json", 2
    while copia.exists():   # duas operações no mesmo segundo não sobrescrevem a cópia
        copia, n = pasta / f"{base}-{n}.json", n + 1
    shutil.copy2(anterior, copia)
    return copia


CHAVES_DEGRAVACAO = ("segmentos", "slug", "titulo", "duracao", "gerado_em", "arquivo", "origem")


def _ler_degravacao(pasta: Path) -> dict | None:
    """transcricao.json de uma degravação, conferido: ilegível ou incompleto dá mensagem, não traceback."""
    arq = pasta / "transcricao.json"
    dados = _ler_json(arq)
    if dados is None:
        print(f"✗ {arq} está ilegível (danificado ou editado à mão): corrija o JSON ou degrave de novo com --refazer.")
        return None
    faltam = [k for k in CHAVES_DEGRAVACAO if k not in dados] + ([] if isinstance(dados.get("segmentos"), list) else ["segmentos"])
    if faltam:
        print(f"✗ {arq} está incompleto (faltam {', '.join(sorted(set(faltam)))}): degrave de novo com --refazer.")
        return None
    return dados


def _regerados(word_ok: bool) -> str:
    return ".md, Word, legendas e player regerados" if word_ok else ".md, legendas e player regerados (o Word não pôde ser gravado)"


def trabalho_manual(dados: dict) -> list[str]:
    """O que se perde se a transcrição ou os falantes forem refeitos."""
    segs = dados.get("segmentos") or []
    itens = []
    if any(info.get("nome") for info in (dados.get("falantes") or {}).values()):
        itens.append("nomes dos falantes")
    if any(s.get("falante") and s.get("falante") != s.get("falante_acustico") for s in segs):
        itens.append("falantes corrigidos (✎)")
    if any(s.get("corrigido") or s.get("txt_whisper") for s in segs):
        itens.append("correções de texto")
    if dados.get("marcacoes"):
        itens.append(f"{len(dados['marcacoes'])} marcações")
    if dados.get("revisoes") and "correções de texto" not in itens:
        itens.append("revisões")
    return itens


# ---------------------------------------------------------------- falantes

def separar_falantes(midia: Path, dados: dict, num: int | None, audio=None) -> bool:
    from degravacao import falantes
    try:
        turnos = falantes.diarizar(midia, MODELOS_FALANTES, num, audio=audio)
    except Exception as e:  # noqa: BLE001 — a degravação continua sem falantes
        print(f"  ⚠ não foi possível separar os falantes ({e}); seguindo sem essa etapa.")
        return False
    dados["falantes"] = falantes.atribuir(dados["segmentos"], turnos)
    dados["num_falantes_informado"] = num
    return True


def _intervalo(expr: str, total: int) -> range:
    a, _, b = expr.partition("-")
    try:
        ini, fim = int(a), int(b or a)
    except ValueError:
        raise ValueError(f"'{expr}' não é um índice de frase (use 12 ou 40-43)") from None
    if not (0 <= ini <= fim < total):
        raise ValueError(f"frase fora do intervalo 0–{total - 1}: {expr}")
    return range(ini, fim + 1)


def cmd_falantes(args) -> int:
    from degravacao import falantes

    pasta = localizar(args.nome)
    if not pasta:
        return 1
    arq = pasta / "transcricao.json"
    dados = _ler_degravacao(pasta)
    if dados is None:
        return 1
    print(f"Degravação: {pasta.name}")
    segs = dados["segmentos"]
    mudou = False

    if args.separar or args.num_falantes:
        perdas = trabalho_manual(dados)
        perdas = [p for p in perdas if p in ("nomes dos falantes", "falantes corrigidos (✎)")]
        if perdas:
            copia = guardar_copia(pasta, "separar")
            print(f"  ⚠ separar de novo descarta {' e '.join(perdas)}; a versão anterior ficou guardada em {copia.name}.")
        original, _ = midia_da_degravacao(pasta, dados)
        if separar_falantes(original, dados, args.num_falantes):
            mudou = True
        else:
            print("  (os falantes anteriores foram mantidos)")
    if not dados.get("falantes"):
        print(f"Esta degravação não tem falantes separados. Para separar: {passo(f'falantes {pasta.name} --separar [--num-falantes N]')}")
        return 1

    try:
        for item in args.atribuir or []:
            alvo, _, rot = item.partition("=")
            rot = rot.strip().upper()
            if not (rot.startswith("F") and rot[1:].isdigit() and rot[1:].isascii()):
                print(f"✗ rótulo inválido em '{item}' (use F1, F2…)")
                return 1
            for i in _intervalo(alvo.strip(), len(segs)):
                segs[i]["falante"] = rot
                segs[i]["falante_incerto"] = False  # conferido
            mudou = True
    except ValueError as e:
        print(f"✗ --atribuir: {e}")
        return 1
    if args.atribuir:
        dados["falantes"] = falantes.resumo(segs, dados["falantes"])
    for item in args.nomear or []:
        rot, _, nome = item.partition("=")
        rot = rot.strip().upper()
        if rot not in dados["falantes"]:
            print(f"✗ {rot} não existe. Falantes: {', '.join(dados['falantes'])}")
            return 1
        dados["falantes"][rot]["nome"] = nome.strip() or None
        mudou = True

    if mudou:
        gravar_json(arq, dados)
        _, _, word_ok = regravar_documentos(pasta, dados)
        print(f"✓ falantes atualizados; {_regerados(word_ok)}.")

    print("\nFalantes:")
    for rot, info in dados["falantes"].items():
        print(f"  {rot}  {info.get('nome') or '(sem nome)':<30} {minutagem(info['tempo'])} de fala")
    if args.listar:
        print("\nFrases (índice · minutagem · falante · texto; '?' = a conferir, '✎' = revista):")
        for x in segs:
            marca = ("?" if x.get("falante_incerto") else " ") + ("✎" if x.get("falante") != x.get("falante_acustico") else " ")
            print(f"  {x['i']:>4} {minutagem(x['ini'])} {x.get('falante', '--'):<3}{marca} {x['txt']}")
    return 0


# ---------------------------------------------------------------- transcrição

def degravar_uma(midia: fontes.Midia, modelo_ref: dict, args, vocab: str, mapa: dict[str, Path]) -> Path:
    from degravacao import midia as exame
    from degravacao import transcricao

    titulo = midia.caminho.stem
    slug = slugify(titulo)
    pasta = pasta_destino(slug, midia.chave, mapa)
    slug = pasta.name
    print(f"\n■ {midia.caminho.name}  →  {exibir(pasta)}")

    # Antes de carregar o modelo: arquivo ilegível ou sem som falha já, com mensagem clara.
    info = exame.examinar(midia.caminho)
    if not info.audio:
        raise exame.ErroMidia(f"{midia.caminho.name} não tem trilha de áudio: não há fala para degravar.", definitivo=True)
    print(f"  · {info.tipo} {info.descricao()}{f' {info.largura}x{info.altura}' if info.video else ''}")

    if modelo_ref.get("modelo") is None:
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, args.dispositivo)
    audio = transcricao.carregar_audio(midia.caminho)   # uma decodificação só: transcrição, onda e falantes
    try:
        dados = transcricao.transcrever(modelo_ref["modelo"], audio, args.idioma, vocab)
    except RuntimeError as e:
        if getattr(modelo_ref["modelo"], "_degravacao_info", {}).get("dispositivo") != "cuda":
            raise
        print(f"\n  ⚠ falha na GPU ({e}); repetindo na CPU.")
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, "cpu")
        dados = transcricao.transcrever(modelo_ref["modelo"], audio, args.idioma, vocab)

    if (args.falantes or args.num_falantes) and not args.sem_falantes:
        separar_falantes(midia.caminho, dados, args.num_falantes, audio)
    del audio

    pasta.mkdir(parents=True, exist_ok=True)
    # Destino final da mídia; mover/copiar só acontece depois que tudo foi gravado.
    levar = midia.mover or args.copiar_video
    arquivo = pasta / midia.caminho.name if levar else midia.caminho

    chave = midia.chave
    if midia.mover and midia.origem == "Arquivo local":
        chave = f"arquivo:{arquivo.resolve()}"  # o arquivo passa a morar na pasta de saída

    video = (midia.caminho if args.sem_converter
             else exame.preparar_para_navegador(midia.caminho, pasta, info, ocupado=arquivo))
    if video == midia.caminho:
        video = arquivo
    if os.name == "nt" and len(str(video.resolve())) >= 250:
        print(f"  ⚠ o caminho da mídia tem {len(str(video.resolve()))} caracteres: acima de 260 o navegador não abre o "
              "arquivo no Windows. Se o player não tocar, escolha uma pasta de degravações mais curta (ex.: C:\\Degravacoes).")
    dados.update({
        "titulo": titulo,
        "slug": slug,
        "arquivo": midia.caminho.name,
        "tipo_midia": info.tipo,
        "formato": info.descricao(),
        "origem": midia.origem,
        "url": midia.url,
        "chave": chave,
        "caminho_midia": str(arquivo.resolve()),
        "caminho_video": str(video.resolve()),
        "vocabulario": vocab,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    })
    anterior = pasta / "transcricao.json"
    if anterior.exists():   # --refazer: nomes, correções, revisão e marcações feitas sobre o texto antigo não valem para o novo
        velho = _ler_json(anterior) or {}
        copia = guardar_copia(pasta, "refazer")
        perdas = trabalho_manual(velho)
        print(f"  ⚠ a versão anterior ficou guardada em {copia.name}"
              + (f" — ela tinha {', '.join(perdas)}, que a nova transcrição não traz." if perdas else "."))
    md, _, _ = regravar_documentos(pasta, dados)
    # Gravado por último: é ele que marca a mídia como degravada.
    gravar_json(pasta / "transcricao.json", dados)
    if levar and midia.caminho.resolve() != arquivo.resolve():
        (shutil.move if midia.mover else shutil.copy2)(str(midia.caminho), str(arquivo))
    mapa[chave] = pasta

    pars = documento.paragrafos(dados["segmentos"])
    duvidas = sum(1 for s in dados["segmentos"] if s["baixa_confianca"])
    print(f"  ✓ {minutagem(dados['duracao'])} degravados em {dados['tempo_processamento'] / 60:.1f} min "
          f"· {len(pars)} parágrafos · {duvidas} frases para conferência")
    if dados.get("falantes"):
        incertas = sum(1 for x in dados["segmentos"] if x.get("falante_incerto"))
        print(f"  ✓ {len(dados['falantes'])} falantes · {incertas} frases com falante a conferir")
    print(f"  ✓ documento: {exibir(md)}")
    print(f"  ✓ player:    {exibir(pasta / 'player.html')}")
    return pasta


MODELOS = ("large-v3", "turbo", "large-v3-turbo", "medium", "small")


def escolher_modelo(args) -> str:
    """Automático: o modelo grande quando a placa NVIDIA dá conta dele; senão o turbo (também na placa, se houver)."""
    if args.modelo:
        return args.modelo
    if args.dispositivo == "cpu":
        return "turbo"
    from degravacao.transcricao import gpu_para_large_v3
    return "large-v3" if gpu_para_large_v3() else "turbo"


def _entrada_disponivel() -> bool:
    """A pasta configurada pode estar numa unidade que não existe no momento (Google Drive fechado, HD externo)."""
    if MOVER_DA_ENTRADA:
        ENTRADA_PADRAO.mkdir(parents=True, exist_ok=True)
        return True
    if ENTRADA.is_dir():
        return True
    print(f"✗ A pasta dos vídeos não está acessível: {ENTRADA}\n"
          "  O Google Drive/OneDrive está aberto? O HD externo está conectado? "
          f"Para escolher outra pasta, {passo('configurar --entrada')}.")
    return False


def cmd_transcrever(args) -> int:
    args.modelo = escolher_modelo(args)
    try:
        SAIDA.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"✗ Não consigo gravar na pasta das degravações ({SAIDA}): {e}\n  Para escolher outra, {passo('configurar --saida')}.")
        return 1
    if MODO_PLUGIN and not PREFS.get("pasta_entrada") and not args.entradas and not args.escolher:
        # No plugin não há caixa de entrada visível: sem pasta configurada, não há onde procurar vídeos.
        print(f"✗ A pasta dos vídeos ainda não foi escolhida. Primeiro, {passo('configurar --entrada \"PASTA\"')}; "
              "ou informe o arquivo ou link a degravar.")
        return 1
    if args.monitorar and args.entradas:
        print("✗ --monitorar vigia a pasta configurada e não aceita arquivos junto: informe só um dos dois.")
        return 1
    if not args.entradas and not args.escolher and not _entrada_disponivel():
        return 1
    vocab = carregar_vocabulario(args.vocabulario)
    modelo_ref: dict = {}

    if args.monitorar:
        return monitorar(args, vocab, modelo_ref)

    if args.escolher:
        from degravacao.janelas import escolher_arquivos
        print("Escolha, na janela que vai abrir, os vídeos ou áudios para degravar…")
        escolhidos = escolher_arquivos("Vídeos ou áudios para degravar", ENTRADA if ENTRADA.is_dir() else Path.home())
        if not escolhidos:
            print("Nenhum arquivo escolhido.")
            return 1
        args.entradas += [str(a) for a in escolhidos]

    mapa = processados()
    ignorados = {} if args.refazer else carregar_ignorados()
    erros: list[str] = []
    try:
        midias = fontes.resolver(args.entradas, ENTRADA, DOWNLOADS, set() if args.refazer else set(mapa),
                                 mover_caixa=MOVER_DA_ENTRADA, erros=erros, ignorar_pasta=SAIDA)
    except fontes.ErroEntrada as e:
        print(f"✗ {e}")
        return 1
    for e in erros:
        print(f"✗ {e}")
    # Um arquivo pedido pelo nome é sempre tentado, mesmo anotado como ignorado: a varredura da pasta é que o pula.
    explicitos = set()
    for item in args.entradas:
        p = Path(item.strip().strip('"').strip("'")).expanduser()
        if p.is_file():
            explicitos.add(f"arquivo:{p.resolve()}")
    for m in [m for m in midias if m.chave in ignorados and m.chave not in explicitos]:
        print(f"  ↷ {m.caminho.name} ignorado: {ignorados[m.chave]} (retire-o da pasta, ou use --refazer para insistir)")
    midias = [m for m in midias if m.chave not in ignorados or m.chave in explicitos]
    if not midias:
        if not erros:
            print(f"Nada novo para degravar. Coloque vídeos ou áudios em: {ENTRADA}")
            print(f"Degravações prontas ficam em: {SAIDA}")
        return 1 if erros else 0

    print(f"{len(midias)} mídia(s) para degravar · modelo {args.modelo} · idioma {args.idioma or 'automático'}")
    falhas, feitas = len(erros), []
    for m in midias:
        try:
            feitas.append(degravar_uma(m, modelo_ref, args, vocab, mapa))
        except KeyboardInterrupt:
            print("\nInterrompido.")
            return 130
        except Exception as e:  # noqa: BLE001
            print(f"\n  ✗ falha ao degravar {m.caminho.name}: {e}")
            if getattr(e, "definitivo", False) and not m.mover and m.chave not in explicitos:
                # Arquivo sem fala achado na varredura: fica anotado e não conta como erro da execução
                # (senão o atalho de dois cliques terminaria sempre em "algo deu errado").
                registrar_ignorado(m.chave, str(e))
                print("    (este arquivo não será tentado de novo; retire-o da pasta ou use --refazer para insistir)")
            else:
                falhas += 1
    _limpar_downloads()
    if args.abrir and feitas:
        abrir_resultados(feitas)
    return 1 if falhas else 0


def _limpar_downloads() -> None:
    try:
        if not DOWNLOADS.exists():
            return
        for sub in DOWNLOADS.iterdir():
            if sub.is_dir() and not any(sub.iterdir()):
                sub.rmdir()
        if not any(DOWNLOADS.iterdir()):
            DOWNLOADS.rmdir()
    except OSError:
        pass


def abrir_no_sistema(caminho: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.call(["open", str(caminho)])
    else:
        subprocess.call(["xdg-open", str(caminho)])


def abrir_player(pasta: Path, em: int | None = None) -> None:
    """Abre o player no navegador padrão. No Windows, o ShellExecute descarta o #t= da URL, então a
    minutagem vai por uma página de redirecionamento gravada ao lado do player."""
    player = (pasta / "player.html").resolve()
    if em and os.name == "nt":
        atalho = pasta / "abrir.html"
        atalho.write_text('<!doctype html><meta charset="utf-8">'
                          f'<meta http-equiv="refresh" content="0; url=player.html#t={int(em)}">'
                          f'<script>location.replace("player.html#t={int(em)}")</script>', encoding="utf-8")
        webbrowser.open(atalho.resolve().as_uri())
        return
    webbrowser.open(player.as_uri() + (f"#t={int(em)}" if em else ""))


def abrir_resultados(pastas: list[Path]) -> None:
    """Uma degravação: abre o player. Várias: abre a pasta de resultados."""
    try:
        if len(pastas) == 1:
            abrir_player(pastas[0])
        else:
            abrir_no_sistema(SAIDA)
    except Exception as e:  # noqa: BLE001
        print(f"  (não consegui abrir automaticamente: {e})")


def monitorar(args, vocab: str, modelo_ref: dict) -> int:
    print(f"Vigiando {ENTRADA} a cada {args.intervalo}s. Ctrl+C para sair.")
    tamanhos: dict[Path, int] = {}
    falharam: set[Path] = set()
    avisou_ausente = False
    try:
        while True:
            try:
                arquivos = fontes.listar_pasta(ENTRADA)
                avisou_ausente = False
            except OSError as e:   # a nuvem desconectou, o HD saiu: espera voltar
                if not avisou_ausente:
                    print(f"  ⚠ pasta indisponível ({e}); tentando de novo a cada {args.intervalo}s…")
                    avisou_ausente = True
                time.sleep(args.intervalo)
                continue
            feitos = set(processados()) | set(carregar_ignorados())
            for arq in arquivos:
                chave = f"arquivo:{arq.resolve()}"
                if arq in falharam or (not MOVER_DA_ENTRADA and chave in feitos):
                    continue
                try:
                    tam = arq.stat().st_size
                except OSError:
                    continue
                if tamanhos.get(arq) != tam:  # ainda copiando: espera o tamanho estabilizar
                    tamanhos[arq] = tam
                    continue
                midia = fontes.Midia(arq, "Arquivo local", chave, mover=MOVER_DA_ENTRADA)
                try:
                    degravar_uma(midia, modelo_ref, args, vocab, processados())
                except Exception as e:  # noqa: BLE001
                    if MOVER_DA_ENTRADA:
                        print(f"  ✗ falha: {e} — movendo para entrada/_falhas/")
                        (ENTRADA / "_falhas").mkdir(exist_ok=True)
                        shutil.move(str(arq), str(ENTRADA / "_falhas" / arq.name))
                    else:
                        print(f"  ✗ falha: {e} — o arquivo fica na pasta e não será tentado de novo nesta sessão.")
                        falharam.add(arq)
                        if getattr(e, "definitivo", False):
                            registrar_ignorado(chave, str(e))
                tamanhos.pop(arq, None)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")
        return 0


# ---------------------------------------------------------------- configuração

MODELO_AUTOMATICO = "automático (large-v3 com placa NVIDIA que dá conta, turbo sem)"


def saida_padrao_para(entrada: Path | None) -> Path:
    """Degravações ao lado dos vídeos. Se os vídeos estão numa pasta sincronizada com a nuvem, numa pasta
    local de verdade (fora de qualquer nuvem): textos e cópias com dados de clientes só sobem se o usuário escolher."""
    from degravacao.nuvem import servico_nuvem
    if entrada is None:
        return SAIDA_PADRAO
    return pasta_local_padrao() if servico_nuvem(entrada) else entrada / "Degravações"


def descrever_saida(pasta: Path) -> str:
    from degravacao.nuvem import servico_nuvem
    nuvem = servico_nuvem(pasta)
    return f"{pasta}  (pasta sincronizada com o {nuvem}: as degravações sobem para a nuvem)" if nuvem else f"{pasta}  (só neste computador)"


def cmd_configurar(args) -> int:
    from degravacao.janelas import escolher_pasta
    from degravacao.nuvem import pasta_documentos, pastas_nuvem, servico_nuvem

    prefs = carregar_preferencias()
    if args.mostrar:
        print(f"Pasta dos vídeos:      {ENTRADA}{'  (caixa de entrada interna: os vídeos são movidos para a saída)' if MOVER_DA_ENTRADA else ''}")
        print(f"Pasta das degravações: {descrever_saida(SAIDA)}")
        print(f"Modelo:                {prefs.get('modelo') or MODELO_AUTOMATICO}")
        print(f"Separar falantes:      {'sim' if prefs.get('falantes') else 'não'}")
        return 0
    if args.padrao:
        PREFERENCIAS.unlink(missing_ok=True)
        if MODO_PLUGIN:
            print(f"✓ Configuração apagada (pastas, modelo e falantes). Degravações voltam para {SAIDA_PADRAO}; "
                  f"escolha de novo a pasta dos vídeos ({passo('configurar')}).")
        else:
            print("✓ Configuração apagada (pastas, modelo e falantes): voltam a valer entrada/ e saida/ do repositório.")
        return 0

    # --entrada/--saida sem caminho abrem a janela; sem opção nenhuma, abre as duas.
    if args.entrada is None and args.saida is None and not (args.modelo or args.falantes):
        args.entrada = args.saida = ""
    entrada_antiga, saida_antiga = prefs.get("pasta_entrada"), prefs.get("pasta_saida")

    if args.entrada is not None:
        if args.entrada:
            entrada = Path(args.entrada).expanduser()
        else:
            print("Escolha, na janela que vai abrir, a pasta onde você vai colocar os vídeos…")
            nuvens = pastas_nuvem()   # a janela abre no Google Drive/OneDrive, se houver
            inicio = Path(entrada_antiga) if entrada_antiga else (nuvens[0][1] if nuvens else pasta_documentos())
            entrada = escolher_pasta("Pasta dos vídeos para degravar", inicio)
            if entrada is None:
                print(f"Nenhuma pasta escolhida. Para informar direto: {passo('configurar --entrada \"CAMINHO\"')}")
                return 1
        if not entrada.is_dir():
            print(f"✗ Pasta não encontrada: {entrada}")
            return 1
        prefs["pasta_entrada"] = str(entrada.resolve())
        nuvem = servico_nuvem(entrada)
        if nuvem:
            print(f"  Pasta sincronizada com o {nuvem}: vídeos enviados pelo celular ou pelo navegador aparecem aqui sozinhos.")
        # A saída padrão acompanha a pasta dos vídeos, salvo se tiver sido escolhida à parte.
        if not saida_antiga or (entrada_antiga and Path(saida_antiga) == saida_padrao_para(Path(entrada_antiga))):
            prefs["pasta_saida"] = str(saida_padrao_para(entrada.resolve()))

    if args.saida is not None:
        padrao = saida_padrao_para(Path(prefs["pasta_entrada"]) if prefs.get("pasta_entrada") else None)
        if args.saida:
            saida = Path(args.saida).expanduser()
        else:
            if prefs.get("pasta_entrada") and servico_nuvem(Path(prefs["pasta_entrada"])):
                print(f"Os vídeos estão numa pasta da nuvem; por padrão, as degravações ficam só neste computador, em {padrao}. "
                      "Para compartilhá-las com a equipe pela nuvem, escolha uma pasta sincronizada.")
            print(f"Agora escolha onde salvar as degravações. Para usar {padrao}, só confirme na janela (ou cancele).")
            criada = not padrao.exists()
            padrao.mkdir(parents=True, exist_ok=True)
            saida = escolher_pasta(f"Onde salvar as degravações? (confirme para usar {padrao.name})",
                                   Path(prefs.get("pasta_saida") or padrao)) or padrao
            if criada and saida.resolve() != padrao.resolve() and not any(padrao.iterdir()):
                padrao.rmdir()
        try:
            saida.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"✗ Não consigo criar a pasta {saida}: {e}")
            return 1
        prefs["pasta_saida"] = str(saida.resolve())

    if saida_antiga and prefs.get("pasta_saida") != saida_antiga:
        anteriores = [p for p in prefs.get("saidas_anteriores", []) if p != prefs.get("pasta_saida")]
        if saida_antiga not in anteriores:
            anteriores.append(saida_antiga)
        prefs["saidas_anteriores"] = anteriores
        if any(Path(saida_antiga).glob("*/transcricao.json")):
            print(f"  (as degravações já feitas continuam em {saida_antiga} e não serão refeitas)")
    if args.modelo:
        prefs["modelo"] = args.modelo
    if args.falantes:
        prefs["falantes"] = args.falantes == "sim"

    PREFERENCIAS.parent.mkdir(parents=True, exist_ok=True)
    gravar_json(PREFERENCIAS, prefs)
    print("✓ Configuração salva.")
    if prefs.get("pasta_entrada"):
        print(f"  Vídeos:      {prefs['pasta_entrada']}  (os originais nunca são movidos)")
    if prefs.get("pasta_saida"):
        print(f"  Degravações: {descrever_saida(Path(prefs['pasta_saida']))}")
    print(f"  Modelo: {prefs.get('modelo') or MODELO_AUTOMATICO} · separar falantes: {'sim' if prefs.get('falantes') else 'não'}")
    if MODO_PLUGIN:
        print("\nPróximo passo: coloque vídeos na pasta e peça ao Claude: \"degrava os vídeos novos\".")
    else:
        print("\nPróximo passo: coloque vídeos na pasta e rode  python degravar.py  (ou dois cliques em Degravar).")
    return 0


# ---------------------------------------------------------------- outros comandos

def localizar(nome: str | None) -> Path | None:
    """Pasta da degravação pelo nome exato, pelo slug ou por um trecho único do nome. Com mais de uma
    candidata, não escolhe por conta própria: lista as opções."""
    pastas = sorted((j.parent for j in SAIDA.glob("*/transcricao.json")), key=lambda p: p.stat().st_mtime)
    if not nome:
        if pastas:
            return pastas[-1]
        print("Nenhuma degravação ainda.")
        return None
    p = Path(nome)
    if p.is_file():
        p = p.parent
    if (p / "transcricao.json").exists():
        return p
    alvo = slugify(nome)
    for pasta in reversed(pastas):
        if pasta.name == nome or pasta.name == alvo:
            return pasta
    parciais = [pasta for pasta in reversed(pastas) if alvo and alvo in pasta.name]
    if len(parciais) == 1:
        return parciais[0]
    if parciais:
        print(f"✗ Mais de uma degravação corresponde a \"{nome}\"; use o nome completo:")
        for pasta in parciais:
            print(f"    {pasta.name}")
        return None
    print(f"✗ Degravação não encontrada: \"{nome}\". Para ver as existentes, {passo('listar')}.")
    return None


def cmd_assistir(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        return 1
    print(f"Abrindo {pasta / 'player.html'}")
    abrir_player(pasta, args.em)
    return 0


def cmd_listar(_args) -> int:
    pastas = sorted(SAIDA.glob("*/transcricao.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pastas:
        print("Nenhuma degravação ainda.")
        return 0
    for j in pastas:
        d = _ler_json(j)
        if d is None:
            print(f"{j.parent.name:<45} ⚠ transcricao.json ilegível (danificado ou editado à mão)")
            continue
        md = j.parent / f"{d.get('slug', j.parent.name)}.md"
        try:
            estruturado = "estruturado" if documento.secao_estruturada(md.read_text(encoding="utf-8")) else "sem estrutura"
        except OSError:
            estruturado = f"sem o .md ({passo('regerar ' + j.parent.name)})"
        try:
            print(f"{d['slug']:<45} {minutagem(d['duracao'])}  {d['gerado_em'][:10]}  {d['origem']:<14} {estruturado}")
        except (KeyError, TypeError):
            print(f"{j.parent.name:<45} ⚠ transcricao.json incompleto")
    return 0


def cmd_artefato(args) -> int:
    from degravacao import artefato

    pasta = localizar(args.nome)
    if not pasta:
        return 1
    dados = _ler_degravacao(pasta)
    if dados is None:
        return 1
    print(f"Degravação: {pasta.name}")
    arq_md = pasta / f"{dados['slug']}.md"
    if not arq_md.exists():
        print(f"  ⚠ {arq_md.name} não existe; regerando os documentos antes.")
        regravar_documentos(pasta, dados)
    md = arq_md.read_text(encoding="utf-8")
    destino = pasta / "artefato"
    origem, _ = midia_da_degravacao(pasta, dados)
    if args.sem_video:
        print("  • sem mídia, a pedido: a página leva só a transcrição.")
        midia, tipo, motivo = None, "nenhuma", "sem_video"
        destino.joinpath("midia").mkdir(parents=True, exist_ok=True)
        for antigo in (destino / "midia").glob("midia.*"):
            antigo.unlink()
    else:
        if not origem.exists():
            print(f"  ⚠ mídia original não encontrada ({origem}); a página sai só com a transcrição.")
        else:
            print("  ⚙ preparando a mídia para o limite de 15 MB do artefato…")
        midia, tipo, motivo = artefato.preparar_midia(origem, destino / "midia", dados["duracao"])
    if args.sem_marcacoes:
        dados = {**dados, "marcacoes": [], "revisoes": [], "revisao_em": None}
    titulo = args.titulo or dados["titulo"]
    pagina = destino / "index.html"
    pagina.write_text(artefato.gerar_pagina(dados, md, titulo, midia, tipo, motivo), encoding="utf-8")

    print(f"✓ Página pronta para publicar ({artefato.descrever_midia(dados, tipo, motivo)}).")
    print(f"  página: {pagina.resolve()}")
    if midia:
        print(f"  mídia:  {midia.resolve()}  ({midia.stat().st_size / 1e6:.1f} MB) → publicar como \"midia/{midia.name}\"")
    else:
        print("  (nenhum arquivo de mídia para publicar; se o artefato já existia com mídia, remova-a com \"midia/<arquivo>\": null)")
    if dados.get("marcacoes"):
        print(f"  ⚠ a página leva as {len(dados['marcacoes'])} marcações e notas feitas no player (use --sem-marcacoes para deixá-las de fora).")
    if not documento.secao_estruturada(md):
        print("  ⚠ a degravação ainda não foi estruturada: a aba de resumo ficará vazia.")
    return 0


def _achar_revisao(slug: str, pasta: Path) -> Path | None:
    """Arquivo exportado pelo player: na pasta Downloads (ou na da degravação), o mais recente."""
    from degravacao.nuvem import pasta_downloads
    nomes = [f"revisao-{slug}.json", f"revisao-{slug} (*).json", f"revisao-{slug}(*).json"]
    candidatos = [a for base in (pasta_downloads(), pasta) for n in nomes for a in base.glob(n)]
    return max(candidatos, key=lambda a: a.stat().st_mtime) if candidatos else None


def _limpar_texto(valor, limite: int = 4000) -> str:
    """Texto vindo do arquivo de revisão: só string, sem surrogates soltos nem caracteres de controle."""
    texto = "" if valor is None else str(valor)
    texto = texto.encode("utf-8", "replace").decode("utf-8")
    texto = "".join(c for c in texto if c in "\n\t" or (ord(c) >= 32 and c not in "\ufffe\uffff"))
    return texto[:limite]


def _inteiro(valor) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _numero(valor) -> float | None:
    import math
    return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) else None


def cmd_revisao(args) -> int:
    """Aplica a revisão feita no player: correções de texto, falantes, nomes e marcações."""
    from degravacao import falantes

    pasta = localizar(args.nome)
    if not pasta:
        return 1
    arq_json = pasta / "transcricao.json"
    dados = _ler_degravacao(pasta)
    if dados is None:
        return 1
    print(f"Degravação: {pasta.name}")
    if args.arquivo:
        arq = Path(args.arquivo).expanduser()
        if not arq.exists():
            print(f"✗ Arquivo não encontrado: {arq}")
            return 1
    else:
        arq = _achar_revisao(dados["slug"], pasta)
        if not arq:
            print(f"✗ Não achei revisao-{dados['slug']}.json em Downloads nem na pasta da degravação. No player, use "
                  f"Exportar › Exportar revisão e informe o caminho: {passo('revisao <nome> <arquivo>')}")
            return 1
    rev = _ler_json(arq)
    if not isinstance(rev, dict):
        print(f"✗ {arq.name} não é um arquivo de revisão válido (JSON incompleto?). Exporte de novo pelo player.")
        return 1
    if rev.get("tipo") != "degravacao-revisao" or rev.get("slug") != dados["slug"]:
        print(f"✗ {arq.name} não é uma revisão desta degravação ({dados['slug']}).")
        return 1
    exportado_de = str(rev.get("gerado_em") or "")
    if exportado_de and exportado_de != str(dados.get("gerado_em")) and not args.forcar:
        print(f"✗ {arq.name} foi exportado de outra versão desta transcrição (de {exportado_de[:16].replace('T', ' ')}; "
              f"a atual é de {str(dados.get('gerado_em'))[:16].replace('T', ' ')}). Depois de um --refazer, as frases mudam "
              "de lugar e falantes e marcações cairiam em frases erradas.\n"
              "  Abra o player novo, refaça a revisão e exporte; ou, para aplicar mesmo assim, use --forcar.")
        return 1

    segs = dados["segmentos"]
    aplicadas, conflitos, ignoradas = 0, [], []
    for c in rev.get("correcoes") or []:
        if not isinstance(c, dict):
            ignoradas.append("correção malformada")
            continue
        i, texto = _inteiro(c.get("i")), " ".join(_limpar_texto(c.get("texto")).split())
        if i is None or not (0 <= i < len(segs)) or not texto:
            ignoradas.append(f"correção da frase {c.get('i')!r}")
            continue
        s = segs[i]
        if s["txt"] == texto:
            continue                                    # já aplicada antes
        if s["txt"] != c.get("original"):
            conflitos.append(i)                         # o texto mudou desde a revisão: não sobrescreve
            continue
        s.setdefault("txt_whisper", s["txt"])           # o original do Whisper fica guardado
        s["txt"], s["corrigido"] = texto, True
        aplicadas += 1
    trocas = 0
    for f in rev.get("falantes") or []:
        if not isinstance(f, dict):
            ignoradas.append("troca de falante malformada")
            continue
        i, rot = _inteiro(f.get("i")), str(f.get("falante", ""))
        if i is None or not (0 <= i < len(segs)) or not (rot[:1] == "F" and rot[1:].isdigit() and rot[1:].isascii()):
            ignoradas.append(f"falante da frase {f.get('i')!r}")
            continue
        if segs[i].get("falante") != rot:
            segs[i].setdefault("falante_acustico", segs[i].get("falante"))
            segs[i]["falante"], segs[i]["falante_incerto"] = rot, False
            trocas += 1
    nomes_aplicados = 0
    nomes = rev.get("nomes") if isinstance(rev.get("nomes"), dict) else {}
    if trocas or nomes:
        dados["falantes"] = falantes.resumo(segs, dados.get("falantes"))
    for rot, nome in nomes.items():
        if rot in (dados.get("falantes") or {}):
            novo = _limpar_texto(nome, 120).strip() or None
            if dados["falantes"][rot].get("nome") != novo:
                dados["falantes"][rot]["nome"] = novo
                nomes_aplicados += 1
        else:
            ignoradas.append(f"nome para {rot} (falante inexistente)")
    marcacoes_mudaram = False
    if "marcacoes" in rev and not isinstance(rev["marcacoes"], list):
        ignoradas.append("lista de marcações inválida (as atuais foram mantidas)")
    elif "marcacoes" in rev:                            # só substitui quando o arquivo traz a lista
        novas = []
        for m in rev.get("marcacoes") or []:
            if not isinstance(m, dict):
                ignoradas.append("marcação malformada")
                continue
            de, ate = _inteiro(m.get("de")), _inteiro(m.get("ate"))
            if de is None or ate is None or not (0 <= de <= ate < len(segs)):
                ignoradas.append(f"marcação nas frases {m.get('de')!r}–{m.get('ate')!r} (fora do texto atual)")
                continue
            cat = str(m.get("cat") or "relevante")
            if cat not in documento.CATEGORIAS:
                cat = "relevante"
            teto = float(dados.get("duracao") or segs[-1]["fim"]) + 1
            ini, fim = _numero(m.get("ini")), _numero(m.get("fim"))
            if ini is None or not (0 <= ini <= teto):
                ini = segs[de]["ini"]
            if fim is None or not (ini <= fim <= teto):
                fim = max(ini, segs[ate]["fim"])
            novas.append({"id": _limpar_texto(m.get("id"), 64) or f"m{de}-{ate}", "de": de, "ate": ate, "ini": ini, "fim": fim,
                          "cat": cat, "nota": _limpar_texto(m.get("nota"), 2000).strip(),
                          "texto": _limpar_texto(m.get("texto"), 4000).strip()})
        if novas != (dados.get("marcacoes") or []):
            dados["marcacoes"] = novas
            marcacoes_mudaram = True
    mudou = bool(aplicadas or trocas or nomes_aplicados or marcacoes_mudaram)
    if mudou:
        guardar_copia(pasta, "revisao")
        dados["revisao_em"] = datetime.now().isoformat(timespec="seconds")
        dados.setdefault("revisoes", []).append({"em": dados["revisao_em"], "arquivo": arq.name, "correcoes": aplicadas,
                                                 "falantes": trocas, "marcacoes": len(dados.get("marcacoes") or [])})
        gravar_json(arq_json, dados)
        _, _, word_ok = regravar_documentos(pasta, dados)
    n = lambda q, um, varios: f"{q} {um if q == 1 else varios}"  # noqa: E731
    print(f"{'✓ revisão aplicada' if mudou else '• nada novo para aplicar'} ({arq.name}): {n(aplicadas, 'correção', 'correções')} · "
          f"{n(trocas, 'frase com falante trocado', 'frases com falante trocado')} · "
          f"{n(nomes_aplicados, 'nome', 'nomes')} · {n(len(dados.get('marcacoes') or []), 'marcação', 'marcações')}"
          f"{' (alteradas)' if marcacoes_mudaram else ''}")
    if mudou:
        print(f"  {_regerados(word_ok)}; o texto original do Whisper continua guardado no transcricao.json.")
    if conflitos:
        print(f"  ⚠ {len(conflitos)} correções não aplicadas porque a frase mudou depois da revisão: frases {conflitos}")
    for item in ignoradas:
        print(f"  ⚠ ignorado: {item}")
    return 0


def _indice_da_frase(segs: list[dict], ref: str) -> int:
    """Índice de frase: número sozinho = índice (o de `falantes --listar`); minutagem MM:SS / HH:MM:SS,
    ou segundos com "s" (754s), = a frase que começa mais perto daquele instante."""
    ref = ref.strip().lower()
    if ref.isdigit():
        return int(ref)
    partes = ref.split(":")
    try:
        if len(partes) > 1:
            segundos = sum(float(p) * 60 ** k for k, p in enumerate(reversed(partes)))
        elif ref.endswith("s"):
            segundos = float(ref[:-1])
        else:
            segundos = float(ref)       # decimal: segundos
    except ValueError:
        raise ValueError(f"'{ref}' não é um índice (ex.: 12) nem uma minutagem (ex.: 12:31, 00:12:31 ou 751s)") from None
    if not segs:
        raise ValueError("a degravação não tem frases")
    return min(range(len(segs)), key=lambda i: abs(segs[i]["ini"] - segundos))


def cmd_corrigir(args) -> int:
    """Correção pontual de uma frase, guardando o texto original do Whisper (o que o player e o Word mostram)."""
    pasta = localizar(args.nome)
    if not pasta:
        return 1
    arq_json = pasta / "transcricao.json"
    dados = _ler_degravacao(pasta)
    if dados is None:
        return 1
    segs = dados["segmentos"]
    try:
        i = _indice_da_frase(segs, args.frase)
    except ValueError as e:
        print(f"✗ {e}")
        return 1
    if not (0 <= i < len(segs)):
        print(f"✗ frase fora do intervalo 0–{len(segs) - 1}: {i}")
        return 1
    texto = " ".join(_limpar_texto(args.texto).split())
    if not texto:
        print("✗ o texto novo está vazio.")
        return 1
    s = segs[i]
    print(f"Degravação: {pasta.name}\n  frase {i} ({minutagem(s['ini'])}):\n    antes:  {s['txt']}\n    depois: {texto}")
    if s["txt"] == texto:
        print("  (já estava assim)")
        return 0
    s.setdefault("txt_whisper", s["txt"])
    s["txt"], s["corrigido"] = texto, True
    gravar_json(arq_json, dados)
    _, _, word_ok = regravar_documentos(pasta, dados)
    print(f"✓ corrigida; {_regerados(word_ok)} (o texto original do Whisper continua guardado).")
    return 0


def cmd_regerar(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        return 1
    arq_json = pasta / "transcricao.json"
    dados = _ler_degravacao(pasta)
    if dados is None:
        return 1
    midia, _ = midia_da_degravacao(pasta, dados)
    if not dados.get("picos") and midia.is_file():   # degravação antiga: calcula a forma de onda do player
        try:
            from degravacao import transcricao
            audio = transcricao.carregar_audio(midia)
            dados["picos"] = transcricao.picos(audio, int(min(3000, max(400, dados["duracao"] * 4))))
            gravar_json(arq_json, dados)
        except Exception as e:  # noqa: BLE001 — sem forma de onda, o player usa os blocos de fala
            print(f"  ⚠ forma de onda não calculada ({e})")
    md, preservada, word_ok = regravar_documentos(pasta, dados)
    estado = {True: "seção estruturada preservada", None: "ainda sem estrutura",
              False: "seção estruturada voltou ao padrão: os marcadores tinham sumido"}[preservada]
    print(f"✓ regerados: {md.name}, {'Word, ' if word_ok else ''}legendas e player.html ({estado})"
          + ("" if word_ok else " — o Word não pôde ser gravado"))
    return 0


REPOS_MODELO = {"large-v3": "Systran/faster-whisper-large-v3", "turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
                "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo", "medium": "Systran/faster-whisper-medium",
                "small": "Systran/faster-whisper-small"}
TAMANHO_MODELO = {"large-v3": "~3 GB", "turbo": "~1,6 GB", "large-v3-turbo": "~1,6 GB", "medium": "~1,5 GB", "small": "~0,5 GB"}


def _modelo_baixado(nome: str) -> bool:
    repo = REPOS_MODELO.get(nome)
    hf = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface")
    hub = Path(os.environ.get("HF_HUB_CACHE") or hf / "hub")
    return bool(repo) and any((hub / ("models--" + repo.replace("/", "--")) / "snapshots").glob("*/model.bin"))


def _placa_nvidia() -> str | None:
    if not tem_nvidia():
        return None
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=20)
        nome, _, memoria = r.stdout.strip().splitlines()[0].partition(",")
        return f"{nome.strip()} ({round(int(memoria.split()[0]) / 1024)} GB)"
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return "placa NVIDIA"


def cmd_diagnostico(_args) -> int:
    """Checklist do ambiente em linguagem simples, com o próximo passo. Roda mesmo antes de instalar."""
    import importlib.metadata as meta

    from degravacao import __version__, nuvem

    passos: list[str] = []

    def item(ok: bool | None, texto: str, proximo: str | None = None) -> None:
        print(f"  {'✓' if ok else '•' if ok is None else '✗'} {texto}")
        if proximo and not ok:
            passos.append(proximo)

    print(f"Degravação {__version__} — diagnóstico ({'plugin' if MODO_PLUGIN else 'repositório'})")
    print(f"  · código: {RAIZ}\n  · dados:  {DADOS}")

    instalado = VENV_PY.exists() and _dentro_da_venv()
    versoes = {}
    for pacote in ("faster-whisper", "ctranslate2", "sherpa-onnx", "av", "imageio-ffmpeg"):
        try:
            versoes[pacote] = meta.version(pacote)
        except meta.PackageNotFoundError:
            pass
    item(True, f"Python {sys.version.split()[0]}")
    if caminho_longo_demais():
        item(False, f"Caminho longo demais para o Windows ({len(str(VENV))} caracteres)",
             "mover a pasta da ferramenta para mais perto da raiz (ex.: C:\\Degravacao)")
    if instalado and len(versoes) == 5:
        item(True, "Ambiente instalado: " + " · ".join(f"{k} {v}" for k, v in versoes.items() if k != "av"))
    elif VENV_PY.exists() and not _dentro_da_venv():
        item(False, "Ambiente quebrado (o Python que o criou não existe mais, ou a pasta foi movida)",
             "recriar o ambiente: comando `instalar`")
    else:
        uv = achar_uv()
        item(False, "Ambiente ainda não instalado" + ("" if uv or (3, 11) <= sys.version_info[:2] <= (3, 14)
                                                      else " (e falta o uv ou um Python 3.11–3.14)"),
             "instalar o ambiente: comando `instalar` (alguns minutos; com o uv, não precisa de Python)")

    placa = _placa_nvidia()
    gpu = False
    if placa and instalado:
        from degravacao.transcricao import gpu_disponivel, gpu_para_large_v3, motivo_sem_gpu
        gpu = gpu_disponivel()
        sem_gpu_pedido = INSTALADO.exists() and "# sem-gpu" in INSTALADO.read_text(encoding="utf-8", errors="replace")
        if gpu:
            item(True, f"Placa {placa}: transcrição na placa, muitas vezes mais rápida"
                 + ("" if gpu_para_large_v3() else " (modelo turbo: a placa não dá conta do large-v3)"))
        elif sem_gpu_pedido:
            item(None, f"Placa {placa}: bibliotecas CUDA deixadas de fora a pedido (--sem-gpu); a transcrição roda na CPU. "
                 "Para usar a placa, rode `instalar` sem --sem-gpu (~2 GB).")
        else:
            motivo = motivo_sem_gpu() or "indisponível"
            item(False, f"Placa {placa}: {motivo}",
                 "instalar as bibliotecas da placa: comando `instalar` de novo" if "bibliotecas" in motivo
                 else "atualizar o driver da NVIDIA (a transcrição roda na CPU enquanto isso)")
    elif placa:
        item(None, f"Placa {placa}: as bibliotecas CUDA vêm com a instalação")
    else:
        item(None, "Sem placa NVIDIA: a transcrição roda no processador (o modelo turbo é o padrão)")

    modelo = PREFS.get("modelo") or ("large-v3" if gpu else "turbo")
    baixado = _modelo_baixado(modelo)
    item(baixado or None, f"Modelo de transcrição {modelo}: " + ("baixado" if baixado else
         f"baixa sozinho na primeira degravação ({TAMANHO_MODELO.get(modelo, '')}, uma vez só)"))
    falantes_ok = (MODELOS_FALANTES / "wespeaker_en_voxceleb_resnet34.onnx").exists()
    item(falantes_ok or None, "Separação de falantes: " + ("modelos baixados" if falantes_ok else "baixa na primeira vez (~33 MB)"))

    janela = sys.platform == "darwin"
    if not janela:
        try:
            import tkinter  # noqa: F401
            janela = True
        except ImportError:
            janela = os.name == "nt"   # o PowerShell faz as vezes do tkinter
    item(janela or None, "Janelas para escolher pastas e arquivos" + ("" if janela else ": indisponíveis; informe os caminhos"))

    nuvens = nuvem.pastas_nuvem()
    if PREFS.get("pasta_entrada"):
        entrada = Path(PREFS["pasta_entrada"])
        servico = nuvem.servico_nuvem(entrada, nuvens)
        item(entrada.is_dir(), f"Pasta dos vídeos: {entrada}" + (f" ({servico})" if servico else "")
             + ("" if entrada.is_dir() else " — não encontrada (o Google Drive/OneDrive está aberto? o HD está conectado?)"),
             "escolher a pasta dos vídeos: comando `configurar`")
    else:
        item(False, "Pasta dos vídeos ainda não escolhida", "escolher as pastas: comando `configurar`")
    servico_saida = nuvem.servico_nuvem(SAIDA, nuvens)
    item(None if servico_saida else True, f"Degravações em: {SAIDA}"
         + (f" — pasta sincronizada com o {servico_saida}: transcrições com dados de clientes sobem para a nuvem" if servico_saida
            else " (só neste computador)"))
    if os.name == "nt" and len(str(SAIDA)) > 180 and not _caminhos_longos_liberados():
        item(False, f"O caminho das degravações é longo ({len(str(SAIDA))} caracteres): com o nome da pasta de cada "
             "degravação, pode passar dos 260 que o Windows aceita, e o player não abre a mídia",
             "escolher uma pasta de degravações mais curta (ex.: C:\\Degravacoes): comando `configurar --saida`")
    if nuvens:
        item(None, "Nuvem sincronizada neste computador: " + "; ".join(f"{n} ({p})" for n, p in nuvens))
    else:
        item(None, "Nenhuma pasta de nuvem sincronizada (Google Drive, OneDrive, Dropbox) encontrada")

    alvo = DADOS if DADOS.exists() else Path.home()
    livre = shutil.disk_usage(alvo).free / 1e9
    precisa = 2 + (3 if not baixado else 0) + (2 if placa and not gpu else 0)
    item(livre > precisa or None, f"Espaço livre: {livre:.0f} GB" + ("" if livre > precisa else f" (recomendado: {precisa} GB ou mais)"))
    feitas = len(list(SAIDA.glob("*/transcricao.json"))) if SAIDA.exists() else 0
    item(None, f"Degravações já feitas: {feitas}")

    print("\nPróximo passo: " + (passos[0] if passos else
          "tudo pronto. Coloque os vídeos na pasta e peça para degravar (comando sem argumentos ou `--escolher`)."))
    return 0


ROTEIRO_EXEMPLO = [
    (0, "Bom dia. Está aberta a audiência de conciliação do processo fictício número mil e duzentos, de dois mil e "
        "vinte e seis, entre Maria Souza e a Construtora Alfa."),
    (1, "Bom dia, Excelência. A reclamante tem interesse em um acordo."),
    (0, "A reclamada apresenta proposta?"),
    (1, "Sim. A proposta é de quinze mil reais, em três parcelas mensais, a primeira no dia dez de março."),
    (0, "A reclamante aceita os termos?"),
    (1, "Aceita, Excelência."),
    (0, "Homologo o acordo. Nada mais havendo, encerro a audiência. Esta é uma gravação de exemplo, com vozes sintéticas."),
]


def _vozes_sistema(pasta: Path) -> list[Path]:
    """Grava cada fala do roteiro com a voz do sistema (português, se houver; até duas vozes).

    Os textos e o caminho não entram no script: vão por variáveis de ambiente (nada de aspas no meio do comando).
    """
    arquivos = []
    if os.name == "nt":
        ambiente = {**os.environ, "DEG_PASTA": str(pasta),
                    "DEG_QUEM": ",".join(str(q) for q, _ in ROTEIRO_EXEMPLO),
                    "DEG_TEXTOS": "\n".join(t for _, t in ROTEIRO_EXEMPLO)}
        script = ("$ErrorActionPreference = 'Stop'; Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$vozes = @($s.GetInstalledVoices() | ? { $_.Enabled } | % { $_.VoiceInfo }); "
                  "if ($vozes.Count -eq 0) { throw 'nenhuma voz instalada' }; "
                  "$pt = @($vozes | ? { $_.Culture.Name -eq 'pt-BR' }); if ($pt.Count -eq 0) { $pt = $vozes }; "
                  "$quem = $env:DEG_QUEM.Split(','); $textos = $env:DEG_TEXTOS.Split([char]10); $pasta = $env:DEG_PASTA; "
                  "for ($n = 0; $n -lt $textos.Count; $n++) { $s.SelectVoice($pt[[int]$quem[$n] % $pt.Count].Name); "
                  "$s.SetOutputToWaveFile((Join-Path $pasta ('fala' + $n + '.wav'))); $s.Speak($textos[$n]) }; "
                  "$s.SetOutputToNull(); $s.Dispose()")
        subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True, capture_output=True, env=ambiente)
        arquivos = [pasta / f"fala{n}.wav" for n in range(len(ROTEIRO_EXEMPLO))]
    elif sys.platform == "darwin":
        import re
        lista = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout.splitlines()
        # Linha: "Luciana              pt_BR    # Olá, meu nome é Luciana." (vozes novas têm nome composto: "Eddy (Portuguese (Brazil))")
        vozes = []
        for ln in lista:
            m = re.match(r"^(.+?)\s{2,}([a-z]{2}_[A-Z]{2})\s+#", ln)
            if m and m.group(2) == "pt_BR":
                vozes.append(m.group(1).strip())
        vozes.sort(key=lambda v: ("(" in v, v != "Luciana"))   # Luciana e as vozes simples primeiro
        vozes = vozes or ["Samantha"]
        for n, (quem, texto) in enumerate(ROTEIRO_EXEMPLO):
            destino = pasta / f"fala{n}.aiff"
            subprocess.run(["say", "-v", vozes[quem % len(vozes)], "-o", str(destino), texto], check=True)
            arquivos.append(destino)
    else:
        raise RuntimeError("este sistema não tem voz sintética embutida; use um vídeo seu para testar")
    faltando = [a.name for a in arquivos if not a.exists() or a.stat().st_size < 1000]
    if faltando:
        raise RuntimeError(f"a voz do sistema não gravou {', '.join(faltando)}")
    return arquivos


def cmd_exemplo(args) -> int:
    """Degrava uma audiência fictícia de ~40 s gerada com a voz do sistema: o teste do primeiro uso."""
    from degravacao.midia import obter_ffmpeg

    pasta = DADOS / "exemplos"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "Exemplo - audiencia ficticia.wav"
    print("• gravando uma audiência fictícia com a voz do sistema…")
    try:
        falas = _vozes_sistema(pasta)
        entradas = [x for f in falas for x in ("-i", str(f))]
        filtro = "".join(f"[{n}:a]aresample=16000,apad=pad_dur=0.7[a{n}];" for n in range(len(falas)))
        filtro += "".join(f"[a{n}]" for n in range(len(falas))) + f"concat=n={len(falas)}:v=0:a=1"
        subprocess.run([obter_ffmpeg(), "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro, "-ac", "1", str(destino)],
                       check=True)
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print(f"✗ não foi possível gerar o áudio de exemplo ({e}). Teste com um vídeo seu: comando `--escolher`.")
        return 1
    for f in pasta.glob("fala*.*"):
        f.unlink(missing_ok=True)
    print(f"  ✓ {destino}")
    # O turbo basta para um teste de 40 s (e evita baixar 3 GB do large-v3 só para isso).
    return main(["transcrever", str(destino), "--refazer", "--num-falantes", "2", "--modelo", "turbo",
                 *([] if args.sem_abrir else ["--abrir"])])


def _baixar_modelo(nome: str) -> int:
    from degravacao.transcricao import carregar_modelo
    carregar_modelo(nome, "cpu")
    print("✓ modelo disponível.")
    return 0


# ---------------------------------------------------------------- argparse

COMANDOS = {"instalar", "configurar", "transcrever", "artefato", "assistir", "listar", "regerar", "revisao", "falantes",
            "corrigir", "diagnostico", "exemplo", "_baixar_modelo"}


def main(argv: list[str]) -> int:
    argv = [a for a in argv if a != "--plugin"]   # sinal do modo plugin, já lido na importação
    if not argv or (argv[0] not in COMANDOS and argv[0] not in {"-h", "--help"}):
        argv = ["transcrever", *argv]

    ap = argparse.ArgumentParser(prog="degravar", description="Degravação integral de vídeos/áudios.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("configurar", help="escolhe a pasta dos vídeos e preferências (fica salvo)")
    p.add_argument("--entrada", metavar="PASTA", nargs="?", const="",
                   help="pasta dos vídeos (sem caminho, abre a janela para escolher)")
    p.add_argument("--saida", metavar="PASTA", nargs="?", const="",
                   help="onde salvar as degravações (padrão: <pasta dos vídeos>/Degravações, ou uma pasta local se os "
                        "vídeos estão na nuvem; sem caminho, abre a janela)")
    p.add_argument("--modelo", choices=MODELOS, help="modelo padrão: large-v3 (preciso) ou turbo (rápido)")
    p.add_argument("--falantes", choices=["sim", "nao"], help="separar falantes por padrão")
    p.add_argument("--mostrar", action="store_true", help="mostra a configuração atual")
    p.add_argument("--padrao", action="store_true",
                   help="apaga a configuração (pastas, modelo e falantes)" + ("" if MODO_PLUGIN else "; voltam a valer entrada/ e saida/ do repositório"))

    sub.add_parser("diagnostico", help="confere o ambiente e diz o próximo passo (roda antes de instalar)")

    p = sub.add_parser("exemplo", help="degrava uma audiência fictícia de ~40 s, para testar o primeiro uso")
    p.add_argument("--sem-abrir", action="store_true", help="não abre o player ao terminar")

    p = sub.add_parser("instalar", help="cria .venv e instala dependências")
    p.add_argument("--baixar-modelo", metavar="MODELO", help="já baixa o modelo (ex.: large-v3, turbo)")
    p.add_argument("--sem-gpu", action="store_true", help="não instala as bibliotecas da placa NVIDIA (~2 GB)")

    p = sub.add_parser("transcrever", help="degrava links do Drive, arquivos ou pastas (padrão: a pasta configurada)")
    p.add_argument("entradas", nargs="*", help="link do Google Drive, arquivo ou pasta")
    p.add_argument("--escolher", action="store_true", help="abre a janela do sistema para escolher os vídeos/áudios")
    p.add_argument("--modelo", default=os.environ.get("DEGRAVAR_MODELO") or PREFS.get("modelo"), choices=MODELOS,
                   help="large-v3 (mais preciso) · turbo (bem mais rápido) · medium · small; "
                        "padrão: large-v3 com placa NVIDIA que dá conta, turbo sem")
    p.add_argument("--idioma", default="pt", help="código do idioma (padrão pt; use '' para detectar)")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--vocabulario", help="termos extras separados por vírgula (nomes das partes, termos técnicos)")
    p.add_argument("--refazer", action="store_true", help="degrava de novo mesmo se já processado (guarda cópia da versão anterior)")
    p.add_argument("--copiar-video", action="store_true", help="copia o arquivo local para a pasta de saída")
    p.add_argument("--sem-converter", action="store_true", help="não converte formatos que o navegador não abre")
    p.add_argument("--falantes", action="store_true", default=bool(PREFS.get("falantes")),
                   help="separa quem fala, pela voz (aproximado)")
    p.add_argument("--sem-falantes", action="store_true", help="não separa falantes (aula, áudio de uma pessoa só), mesmo que seja o padrão configurado")
    p.add_argument("--num-falantes", type=int, metavar="N", help="número de pessoas que falam (implica --falantes)")
    p.add_argument("--monitorar", action="store_true", help="vigia a pasta dos vídeos continuamente")
    p.add_argument("--abrir", action="store_true", help="ao terminar, abre o player (ou a pasta, se forem vários)")
    p.add_argument("--intervalo", type=int, default=20, help="segundos entre verificações no modo monitor")

    p = sub.add_parser("assistir", help="abre o player com transcrição sincronizada")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("--em", type=int, help="abre já na minutagem (segundos)")

    sub.add_parser("listar", help="lista as degravações feitas")

    p = sub.add_parser("artefato", help="prepara página e mídia (até 15 MB) para publicar como artefato no claude.ai")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("--titulo", help="título da página (padrão: nome do arquivo)")
    p.add_argument("--sem-video", action="store_true", help="publica só a transcrição: nenhuma mídia (nem áudio) sai do computador")
    p.add_argument("--sem-marcacoes", action="store_true", help="deixa de fora as marcações e notas feitas no player")

    p = sub.add_parser("falantes", help="separa, nomeia e corrige falantes de uma degravação")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("--separar", action="store_true",
                   help="roda a separação de falantes nesta degravação (descarta nomes e correções anteriores; guarda cópia)")
    p.add_argument("--num-falantes", type=int, metavar="N", help="número de pessoas que falam (implica --separar)")
    p.add_argument("--nomear", action="append", metavar='F1="Juiz(a)"', help="dá nome a um falante")
    p.add_argument("--atribuir", action="append", metavar="12=F2", help="corrige o falante de frase(s): 12=F2 ou 40-43=F1")
    p.add_argument("--listar", action="store_true", help="mostra todas as frases com o falante atribuído")

    p = sub.add_parser("corrigir", help="corrige o texto de uma frase, guardando o original do Whisper")
    p.add_argument("nome", help="nome/slug da degravação")
    p.add_argument("frase", help="índice da frase (número, ver `falantes --listar`) ou minutagem (12:31, 00:12:31 ou 751s)")
    p.add_argument("texto", help="texto corrigido")

    p = sub.add_parser("regerar", help="regera .md, Word, legendas e player a partir do transcricao.json")
    p.add_argument("nome", nargs="?")

    p = sub.add_parser("revisao", help="aplica a revisão exportada pelo player (correções, falantes, nomes, marcações)")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("arquivo", nargs="?", help="revisao-<nome>.json (padrão: o mais recente em Downloads)")
    p.add_argument("--forcar", action="store_true", help="aplica mesmo uma revisão exportada de outra versão da transcrição")

    p = sub.add_parser("_baixar_modelo")
    p.add_argument("nome")

    args = ap.parse_args(argv)
    if args.comando == "instalar":
        return instalar(args.baixar_modelo, gpu=not args.sem_gpu)
    if args.comando in {"transcrever", "falantes", "artefato", "revisao", "corrigir", "regerar", "exemplo", "_baixar_modelo"}:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            print(f"Dependências ausentes. Primeiro, {passo('instalar')}"
                  + ("" if MODO_PLUGIN else " (ou dê dois cliques em Degravar)") + ".")
            return 1
    if args.comando == "_baixar_modelo":
        return _baixar_modelo(args.nome)
    return {"transcrever": cmd_transcrever, "assistir": cmd_assistir,
            "listar": cmd_listar, "regerar": cmd_regerar, "revisao": cmd_revisao, "falantes": cmd_falantes,
            "corrigir": cmd_corrigir, "diagnostico": cmd_diagnostico, "exemplo": cmd_exemplo,
            "configurar": cmd_configurar, "artefato": cmd_artefato}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
