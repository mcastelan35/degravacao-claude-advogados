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
VENV = RAIZ / ".venv"
VENV_PY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# Acentos e símbolos no terminal do Windows.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _dentro_da_venv() -> bool:
    return Path(sys.prefix).resolve() == VENV.resolve()


def instalar(baixar_modelo: str | None) -> int:
    if not (3, 11) <= sys.version_info[:2] <= (3, 14):
        print(f"✗ Este Python é o {sys.version.split()[0]}; a ferramenta precisa do Python 3.11 a 3.14 "
              "(recomendado 3.12). Instale em https://www.python.org/downloads/")
        return 1
    if not VENV_PY.exists():
        print(f"• criando ambiente virtual em {VENV} …")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    print("• instalando dependências (faster-whisper, gdown)…")
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "--upgrade", "pip", "-q"])
    subprocess.check_call([str(VENV_PY), "-m", "pip", "install", "-r", str(RAIZ / "requirements.txt")])
    if baixar_modelo:
        print(f"• baixando modelo Whisper '{baixar_modelo}' (pode levar alguns minutos)…")
        subprocess.check_call([str(VENV_PY), str(RAIZ / "degravar.py"), "_baixar_modelo", baixar_modelo])
    print("\n✓ Instalação concluída. Próximo passo: python degravar.py configurar (escolher a pasta dos vídeos)")
    return 0


# Se a .venv existe e não estamos nela, reexecuta o script com o Python da .venv.
if __name__ == "__main__" and VENV_PY.exists() and not _dentro_da_venv() and sys.argv[1:2] != ["instalar"]:
    sys.exit(subprocess.call([str(VENV_PY), str(Path(__file__).resolve()), *sys.argv[1:]]))

import argparse  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
import webbrowser  # noqa: E402
from datetime import datetime  # noqa: E402

from degravacao import documento, fontes  # noqa: E402
from degravacao.util import minutagem, slugify, src_relativo  # noqa: E402

VOCABULARIO = RAIZ / "config" / "vocabulario.txt"
PREFERENCIAS = RAIZ / "config" / "preferencias.json"
MODELOS_FALANTES = RAIZ / "modelos"
ENTRADA_PADRAO = RAIZ / "entrada"


def carregar_preferencias() -> dict:
    try:
        return json.loads(PREFERENCIAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


PREFS = carregar_preferencias()
ENTRADA = Path(PREFS["pasta_entrada"]) if PREFS.get("pasta_entrada") else ENTRADA_PADRAO
SAIDA = Path(PREFS["pasta_saida"]) if PREFS.get("pasta_saida") else RAIZ / "saida"
# Só a caixa de entrada interna (entrada/) move os vídeos; numa pasta escolhida pelo usuário
# os originais nunca são movidos nem alterados — o que já foi degravado é apenas pulado.
MOVER_DA_ENTRADA = ENTRADA.resolve() == ENTRADA_PADRAO.resolve()
DOWNLOADS = SAIDA / ".baixando"

# Formatos que o navegador não reproduz: convertidos para o player se houver ffmpeg.
NAO_REPRODUZIVEIS = {".mkv", ".avi", ".wmv", ".flv", ".mpg", ".mpeg", ".3gp", ".ts", ".wma", ".amr"}


# ---------------------------------------------------------------- utilidades

def exibir(caminho: Path) -> str:
    """Caminho curto para mensagens: relativo ao repositório quando estiver dentro dele."""
    try:
        return str(caminho.resolve().relative_to(RAIZ))
    except ValueError:
        return str(caminho)


def processados() -> dict[str, Path]:
    """Mapa chave-da-fonte → pasta, a partir das degravações já existentes."""
    mapa: dict[str, Path] = {}
    for j in SAIDA.glob("*/transcricao.json"):
        try:
            mapa[json.loads(j.read_text(encoding="utf-8"))["chave"]] = j.parent
        except Exception:  # noqa: BLE001
            continue
    return mapa


def pasta_destino(slug: str, chave: str, mapa: dict[str, Path]) -> Path:
    if chave in mapa:
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


def preparar_video_player(midia: Path, pasta: Path, converter: bool) -> Path:
    if midia.suffix.lower() not in NAO_REPRODUZIVEIS or not converter:
        return midia
    from degravacao.artefato import obter_ffmpeg
    try:
        ffmpeg = obter_ffmpeg()
    except Exception:  # noqa: BLE001
        print(f"  ⚠ o navegador não reproduz {midia.suffix} e o ffmpeg não foi encontrado.")
        return midia
    eh_audio = midia.suffix.lower() in fontes.EXT_AUDIO
    destino = pasta / (midia.stem + (".m4a" if eh_audio else ".mp4"))
    print(f"  ⚙ convertendo para {destino.suffix} (compatível com o navegador)…")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(midia)]
    cmd += (["-vn"] if eh_audio else ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"])
    cmd += ["-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(destino)]
    if subprocess.call(cmd) == 0:
        return destino
    print("  ⚠ conversão falhou; o player usará o arquivo original.")
    return midia


def regravar_documentos(pasta: Path, dados: dict) -> Path:
    """(Re)gera .md, legendas e player preservando a seção já estruturada pelo Claude."""
    from degravacao.player import gerar_player

    titulo = dados["titulo"]
    md = pasta / f"{dados['slug']}.md"
    estrutura_antiga = None
    if md.exists():
        atual = md.read_text(encoding="utf-8")
        ini, fim = atual.find(documento.MARCA_CLAUDE_INI), atual.find(documento.MARCA_CLAUDE_FIM)
        if 0 <= ini < fim and "_Pendente." not in atual[ini:fim]:
            estrutura_antiga = atual[ini:fim]
    md = documento.salvar_tudo(pasta, dados, titulo)
    if estrutura_antiga:
        novo = md.read_text(encoding="utf-8")
        ini, fim = novo.find(documento.MARCA_CLAUDE_INI), novo.find(documento.MARCA_CLAUDE_FIM)
        md.write_text(novo[:ini] + estrutura_antiga + novo[fim:], encoding="utf-8")
    gerar_player(pasta, dados, titulo, src_relativo(Path(dados["caminho_video"]), pasta))
    return md


# ---------------------------------------------------------------- falantes

def separar_falantes(midia: Path, dados: dict, num: int | None) -> None:
    from degravacao import falantes
    try:
        turnos = falantes.diarizar(midia, MODELOS_FALANTES, num)
    except Exception as e:  # noqa: BLE001 — a degravação continua sem falantes
        print(f"  ⚠ não foi possível separar os falantes ({e}); seguindo sem essa etapa.")
        return
    dados["falantes"] = falantes.atribuir(dados["segmentos"], turnos)
    dados["num_falantes_informado"] = num


def _intervalo(expr: str, total: int) -> range:
    a, _, b = expr.partition("-")
    ini, fim = int(a), int(b or a)
    if not (0 <= ini <= fim < total):
        raise ValueError(f"frase fora do intervalo 0–{total - 1}: {expr}")
    return range(ini, fim + 1)


def cmd_falantes(args) -> int:
    from degravacao import falantes

    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada. Use: python degravar.py listar")
        return 1
    arq = pasta / "transcricao.json"
    dados = json.loads(arq.read_text(encoding="utf-8"))
    segs = dados["segmentos"]
    mudou = False

    if args.separar or args.num_falantes:
        separar_falantes(Path(dados["caminho_midia"]), dados, args.num_falantes)
        mudou = bool(dados.get("falantes"))
    if not dados.get("falantes"):
        print("Esta degravação não tem falantes separados. Use: python degravar.py falantes "
              f"{pasta.name} --separar [--num-falantes N]")
        return 1

    for item in args.atribuir or []:
        alvo, _, rot = item.partition("=")
        rot = rot.strip().upper()
        if not rot.startswith("F") or not rot[1:].isdigit():
            print(f"✗ rótulo inválido em '{item}' (use F1, F2…)")
            return 1
        for i in _intervalo(alvo.strip(), len(segs)):
            segs[i]["falante"] = rot
            segs[i]["falante_incerto"] = False  # conferido
        mudou = True
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
        arq.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        regravar_documentos(pasta, dados)
        print("✓ falantes atualizados; .md, legendas e player regerados.")

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
    from degravacao import transcricao

    titulo = midia.caminho.stem
    slug = slugify(titulo)
    pasta = pasta_destino(slug, midia.chave, mapa)
    slug = pasta.name
    print(f"\n■ {midia.caminho.name}  →  {exibir(pasta)}")

    if modelo_ref.get("modelo") is None:
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, args.dispositivo)
    try:
        dados = transcricao.transcrever(modelo_ref["modelo"], midia.caminho, args.idioma, vocab)
    except RuntimeError as e:
        if getattr(modelo_ref["modelo"], "_degravacao_info", {}).get("dispositivo") != "cuda":
            raise
        print(f"\n  ⚠ falha na GPU ({e}); repetindo na CPU.")
        modelo_ref["modelo"] = transcricao.carregar_modelo(args.modelo, "cpu")
        dados = transcricao.transcrever(modelo_ref["modelo"], midia.caminho, args.idioma, vocab)

    if args.falantes or args.num_falantes:
        separar_falantes(midia.caminho, dados, args.num_falantes)

    pasta.mkdir(parents=True, exist_ok=True)
    # Destino final da mídia; mover/copiar só acontece depois que tudo foi gravado.
    levar = midia.mover or args.copiar_video
    arquivo = pasta / midia.caminho.name if levar else midia.caminho

    chave = midia.chave
    if midia.mover and midia.origem == "Arquivo local":
        chave = f"arquivo:{arquivo.resolve()}"  # o arquivo passa a morar na pasta de saída

    video = preparar_video_player(midia.caminho, pasta, not args.sem_converter)
    if video == midia.caminho:
        video = arquivo
    dados.update({
        "titulo": titulo,
        "slug": slug,
        "arquivo": midia.caminho.name,
        "origem": midia.origem,
        "url": midia.url,
        "chave": chave,
        "caminho_midia": str(arquivo.resolve()),
        "caminho_video": str(video.resolve()),
        "vocabulario": vocab,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
    })
    md = regravar_documentos(pasta, dados)
    # Gravado por último: é ele que marca a mídia como degravada.
    (pasta / "transcricao.json").write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    if levar and midia.caminho.resolve() != arquivo.resolve():
        (shutil.move if midia.mover else shutil.copy2)(str(midia.caminho), str(arquivo))
    mapa[chave] = pasta

    pars = documento.paragrafos(dados["segmentos"])
    duvidas = sum(1 for p in pars if any(dados["segmentos"][i]["baixa_confianca"] for i in p["segs"]))
    print(f"  ✓ {minutagem(dados['duracao'])} degravados em {dados['tempo_processamento'] / 60:.1f} min "
          f"· {len(pars)} parágrafos · {duvidas} trechos para conferência")
    if dados.get("falantes"):
        incertas = sum(1 for x in dados["segmentos"] if x.get("falante_incerto"))
        print(f"  ✓ {len(dados['falantes'])} falantes · {incertas} frases com falante a conferir")
    print(f"  ✓ documento: {exibir(md)}")
    print(f"  ✓ player:    {exibir(pasta / 'player.html')}")
    return pasta


def cmd_transcrever(args) -> int:
    SAIDA.mkdir(exist_ok=True)
    ENTRADA.mkdir(exist_ok=True)
    vocab = carregar_vocabulario(args.vocabulario)
    modelo_ref: dict = {}

    if args.monitorar:
        return monitorar(args, vocab, modelo_ref)

    mapa = processados()
    try:
        midias = fontes.resolver(args.entradas, ENTRADA, DOWNLOADS, set() if args.refazer else set(mapa),
                                 mover_caixa=MOVER_DA_ENTRADA)
    except fontes.ErroEntrada as e:
        print(f"✗ {e}")
        return 1
    if not midias:
        print(f"Nada novo para degravar. Coloque vídeos ou áudios em: {ENTRADA}")
        print(f"Degravações prontas ficam em: {SAIDA}")
        return 0

    print(f"{len(midias)} mídia(s) para degravar · modelo {args.modelo} · idioma {args.idioma or 'automático'}")
    falhas, feitas = 0, []
    for m in midias:
        try:
            feitas.append(degravar_uma(m, modelo_ref, args, vocab, mapa))
        except KeyboardInterrupt:
            print("\nInterrompido.")
            return 130
        except Exception as e:  # noqa: BLE001
            falhas += 1
            print(f"\n  ✗ falha ao degravar {m.caminho.name}: {e}")
    if DOWNLOADS.exists() and not any(DOWNLOADS.iterdir()):
        DOWNLOADS.rmdir()
    if args.abrir and feitas:
        abrir_resultados(feitas)
    return 1 if falhas else 0


def abrir_no_sistema(caminho: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(caminho)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.call(["open", str(caminho)])
    else:
        subprocess.call(["xdg-open", str(caminho)])


def abrir_resultados(pastas: list[Path]) -> None:
    """Uma degravação: abre o player. Várias: abre a pasta de resultados."""
    try:
        if len(pastas) == 1:
            webbrowser.open((pastas[0] / "player.html").resolve().as_uri())
        else:
            abrir_no_sistema(SAIDA)
    except Exception as e:  # noqa: BLE001
        print(f"  (não consegui abrir automaticamente: {e})")


def monitorar(args, vocab: str, modelo_ref: dict) -> int:
    print(f"Vigiando {ENTRADA} a cada {args.intervalo}s. Ctrl+C para sair.")
    tamanhos: dict[Path, int] = {}
    falharam: set[Path] = set()
    try:
        while True:
            feitos = set(processados())
            for arq in fontes.listar_pasta(ENTRADA):
                chave = f"arquivo:{arq.resolve()}"
                if arq in falharam or (not MOVER_DA_ENTRADA and chave in feitos):
                    continue
                tam = arq.stat().st_size
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
                tamanhos.pop(arq, None)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado.")
        return 0


# ---------------------------------------------------------------- configuração

def escolher_pasta(titulo: str, inicial: Path) -> Path | None:
    """Seletor de pastas do sistema; sem interface gráfica, pergunta no terminal."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        raiz = tk.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        escolha = filedialog.askdirectory(title=titulo, initialdir=str(inicial), mustexist=True, parent=raiz)
        raiz.destroy()
        return Path(escolha) if escolha else None
    except Exception:  # noqa: BLE001 — sem tkinter ou sem tela
        if not sys.stdin.isatty():
            return None
        resposta = input(f"{titulo}\nCole o caminho da pasta e tecle Enter: ").strip().strip('"')
        return Path(resposta).expanduser() if resposta else None


def cmd_configurar(args) -> int:
    prefs = carregar_preferencias()
    if args.mostrar:
        print(f"Pasta dos vídeos:      {ENTRADA}{'  (padrão)' if MOVER_DA_ENTRADA else ''}")
        print(f"Pasta das degravações: {SAIDA}")
        print(f"Modelo:                {prefs.get('modelo', 'large-v3')}")
        print(f"Separar falantes:      {'sim' if prefs.get('falantes') else 'não'}")
        return 0
    if args.padrao:
        PREFERENCIAS.unlink(missing_ok=True)
        print("✓ Configuração apagada: voltam a valer as pastas entrada/ e saida/ do repositório.")
        return 0

    alterou_algo = args.modelo or args.falantes
    entrada = Path(args.entrada).expanduser() if args.entrada else None
    if entrada is None and not alterou_algo:
        print("Escolha, na janela que vai abrir, a pasta onde você vai colocar os vídeos…")
        entrada = escolher_pasta("Pasta dos vídeos para degravar", Path.home())
        if entrada is None:
            print("Nenhuma pasta escolhida. Para informar direto: python degravar.py configurar --entrada \"CAMINHO\"")
            return 1
    if entrada is not None:
        if not entrada.is_dir():
            print(f"✗ Pasta não encontrada: {entrada}")
            return 1
        prefs["pasta_entrada"] = str(entrada.resolve())
        prefs["pasta_saida"] = str(Path(args.saida).expanduser().resolve() if args.saida
                                   else entrada.resolve() / "Degravações")
    elif args.saida:
        prefs["pasta_saida"] = str(Path(args.saida).expanduser().resolve())
    if args.modelo:
        prefs["modelo"] = args.modelo
    if args.falantes:
        prefs["falantes"] = args.falantes == "sim"

    PREFERENCIAS.parent.mkdir(exist_ok=True)
    PREFERENCIAS.write_text(json.dumps(prefs, ensure_ascii=False, indent=1), encoding="utf-8")
    print("✓ Configuração salva.")
    if prefs.get("pasta_entrada"):
        print(f"  Vídeos:      {prefs['pasta_entrada']}  (os originais nunca são movidos)")
        print(f"  Degravações: {prefs['pasta_saida']}")
    print(f"  Modelo: {prefs.get('modelo', 'large-v3')} · separar falantes: {'sim' if prefs.get('falantes') else 'não'}")
    print("\nPróximo passo: coloque vídeos na pasta e rode  python degravar.py  (ou dois cliques em Degravar).")
    return 0


# ---------------------------------------------------------------- outros comandos

def localizar(nome: str | None) -> Path | None:
    pastas = sorted((j.parent for j in SAIDA.glob("*/transcricao.json")), key=lambda p: p.stat().st_mtime)
    if not nome:
        return pastas[-1] if pastas else None
    p = Path(nome)
    if p.is_file():
        p = p.parent
    if (p / "transcricao.json").exists():
        return p
    alvo = slugify(nome)
    for pasta in reversed(pastas):
        if pasta.name == nome or pasta.name == alvo:
            return pasta
    for pasta in reversed(pastas):
        if alvo in pasta.name:
            return pasta
    return None


def cmd_assistir(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada. Use: python degravar.py listar")
        return 1
    player = pasta / "player.html"
    print(f"Abrindo {player}")
    webbrowser.open(player.resolve().as_uri() + (f"#t={args.em}" if args.em else ""))
    return 0


def cmd_listar(_args) -> int:
    pastas = sorted(SAIDA.glob("*/transcricao.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not pastas:
        print("Nenhuma degravação ainda.")
        return 0
    for j in pastas:
        d = json.loads(j.read_text(encoding="utf-8"))
        md = j.parent / f"{d['slug']}.md"
        estruturado = "estruturado" if "_Pendente." not in md.read_text(encoding="utf-8") else "sem estrutura"
        print(f"{d['slug']:<45} {minutagem(d['duracao'])}  {d['gerado_em'][:10]}  {d['origem']:<14} {estruturado}")
    return 0


def cmd_artefato(args) -> int:
    from degravacao import artefato

    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada. Use: python degravar.py listar")
        return 1
    dados = json.loads((pasta / "transcricao.json").read_text(encoding="utf-8"))
    md = (pasta / f"{dados['slug']}.md").read_text(encoding="utf-8")
    destino = pasta / "artefato"
    origem = Path(dados["caminho_midia"])
    if not args.sem_video and not origem.exists():
        print(f"  ⚠ mídia original não encontrada ({origem}); a página sai só com a transcrição.")
    print("  ⚙ preparando a mídia para o limite de 15 MB do artefato…")
    midia, tipo = artefato.preparar_midia(origem, destino / "midia", dados["duracao"],
                                          sem_video=args.sem_video or not origem.exists())
    titulo = args.titulo or dados["titulo"]
    pagina = destino / "index.html"
    pagina.write_text(artefato.gerar_pagina(dados, md, titulo, midia, tipo), encoding="utf-8")

    descricao = {"video": "vídeo", "audio": "só áudio (o vídeo não caberia)", "nenhuma": "sem mídia"}[tipo]
    print(f"✓ Página pronta para publicar ({descricao}).")
    print(f"  página: {pagina.resolve()}")
    if midia:
        print(f"  mídia:  {midia.resolve()}  ({midia.stat().st_size / 1e6:.1f} MB) → publicar como \"midia/{midia.name}\"")
    if not artefato.secao_estruturada(md):
        print("  ⚠ a degravação ainda não foi estruturada: a aba de resumo ficará vazia.")
    return 0


def cmd_regerar(args) -> int:
    pasta = localizar(args.nome)
    if not pasta:
        print("Degravação não encontrada.")
        return 1
    dados = json.loads((pasta / "transcricao.json").read_text(encoding="utf-8"))
    md = regravar_documentos(pasta, dados)
    print(f"✓ regerados: {md.name}, legendas e player.html (seção estruturada preservada)")
    return 0


def _baixar_modelo(nome: str) -> int:
    from degravacao.transcricao import carregar_modelo
    carregar_modelo(nome, "cpu")
    print("✓ modelo disponível.")
    return 0


# ---------------------------------------------------------------- argparse

COMANDOS = {"instalar", "configurar", "transcrever", "artefato", "assistir", "listar", "regerar", "falantes", "_baixar_modelo"}


def main(argv: list[str]) -> int:
    if not argv or (argv[0] not in COMANDOS and argv[0] not in {"-h", "--help"}):
        argv = ["transcrever", *argv]

    ap = argparse.ArgumentParser(prog="degravar", description="Degravação integral de vídeos/áudios.")
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("configurar", help="escolhe a pasta dos vídeos e preferências (fica salvo)")
    p.add_argument("--entrada", metavar="PASTA", help="pasta dos vídeos (sem isso, abre o seletor de pastas)")
    p.add_argument("--saida", metavar="PASTA", help="onde salvar as degravações (padrão: <pasta dos vídeos>/Degravações)")
    p.add_argument("--modelo", help="modelo padrão: large-v3 (preciso) ou turbo (rápido)")
    p.add_argument("--falantes", choices=["sim", "nao"], help="separar falantes por padrão")
    p.add_argument("--mostrar", action="store_true", help="mostra a configuração atual")
    p.add_argument("--padrao", action="store_true", help="volta para as pastas entrada/ e saida/ do repositório")

    p = sub.add_parser("instalar", help="cria .venv e instala dependências")
    p.add_argument("--baixar-modelo", metavar="MODELO", help="já baixa o modelo (ex.: large-v3, turbo)")

    p = sub.add_parser("transcrever", help="degrava links do Drive, arquivos ou pastas (padrão: entrada/)")
    p.add_argument("entradas", nargs="*", help="link do Google Drive, arquivo ou pasta")
    p.add_argument("--modelo", default=os.environ.get("DEGRAVAR_MODELO", PREFS.get("modelo", "large-v3")),
                   help="large-v3 (padrão, mais preciso) · turbo (bem mais rápido) · medium · small")
    p.add_argument("--idioma", default="pt", help="código do idioma (padrão pt; use '' para detectar)")
    p.add_argument("--dispositivo", default="auto", choices=["auto", "cpu", "cuda"])
    p.add_argument("--vocabulario", help="termos extras separados por vírgula (nomes das partes, termos técnicos)")
    p.add_argument("--refazer", action="store_true", help="degrava de novo mesmo se já processado")
    p.add_argument("--copiar-video", action="store_true", help="copia o arquivo local para a pasta de saída")
    p.add_argument("--sem-converter", action="store_true", help="não converte formatos que o navegador não abre")
    p.add_argument("--falantes", action="store_true", default=bool(PREFS.get("falantes")),
                   help="separa quem fala, pela voz (aproximado)")
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
    p.add_argument("--sem-video", action="store_true", help="publica só a transcrição, sem mídia")

    p = sub.add_parser("falantes", help="separa, nomeia e corrige falantes de uma degravação")
    p.add_argument("nome", nargs="?", help="nome/slug da degravação (padrão: a mais recente)")
    p.add_argument("--separar", action="store_true", help="roda a separação de falantes nesta degravação")
    p.add_argument("--num-falantes", type=int, metavar="N")
    p.add_argument("--nomear", action="append", metavar='F1="Juiz(a)"', help="dá nome a um falante")
    p.add_argument("--atribuir", action="append", metavar="12=F2", help="corrige o falante de frase(s): 12=F2 ou 40-43=F1")
    p.add_argument("--listar", action="store_true", help="mostra todas as frases com o falante atribuído")

    p = sub.add_parser("regerar", help="regera .md, legendas e player a partir do transcricao.json")
    p.add_argument("nome", nargs="?")

    p = sub.add_parser("_baixar_modelo")
    p.add_argument("nome")

    args = ap.parse_args(argv)
    if args.comando == "instalar":
        return instalar(args.baixar_modelo)
    if args.comando in {"transcrever", "falantes", "artefato", "_baixar_modelo"}:
        try:
            import faster_whisper  # noqa: F401
        except ImportError:
            print("Dependências ausentes. Rode primeiro:  python degravar.py instalar")
            return 1
    if args.comando == "_baixar_modelo":
        return _baixar_modelo(args.nome)
    return {"transcrever": cmd_transcrever, "assistir": cmd_assistir,
            "listar": cmd_listar, "regerar": cmd_regerar, "falantes": cmd_falantes,
            "configurar": cmd_configurar, "artefato": cmd_artefato}[args.comando](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
