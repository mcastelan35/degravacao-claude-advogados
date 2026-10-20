"""Transcrição local com Whisper (faster-whisper). Nada sai do computador."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Limiares para marcar trechos que merecem conferência humana.
LIMIAR_LOGPROB = -0.8     # confiança média do segmento (log-prob)
LIMIAR_PALAVRA = 0.45     # probabilidade média das palavras do segmento

MODELOS_ALIAS = {"turbo": "large-v3-turbo", "preciso": "large-v3", "rapido": "small"}


_DLLS_CUDA = ("cublas64_12.dll", "cudnn64_9.dll")             # o que o CTranslate2 carrega para rodar na GPU
_SO_CUDA = ("libcublas.so.12", "libcudnn.so.9")
MEMORIA_LARGE_V3_GB = 6                                         # abaixo disso o large-v3 em float16 não cabe na placa


def _pastas_nvidia(sub: str) -> list[Path]:
    """Pastas dos wheels nvidia-cublas-cu12 / nvidia-cudnn-cu12 (requirements-gpu.txt)."""
    import importlib.util
    spec = importlib.util.find_spec("nvidia")
    bases = (spec.submodule_search_locations or []) if spec else []
    return [p for base in bases for p in Path(base).glob(f"*/{sub}")]


def _bibliotecas_cuda() -> bool:
    """Torna visíveis as bibliotecas CUDA instaladas pelo pip e devolve se elas carregam.

    No Windows são DLLs em nvidia/*/bin; no Linux, .so em nvidia/*/lib. O Mac não tem CUDA.
    """
    import ctypes
    if sys.platform == "darwin":
        return False
    if os.name == "nt":
        for pasta in _pastas_nvidia("bin"):
            if str(pasta) not in os.environ.get("PATH", ""):
                os.add_dll_directory(str(pasta))
                os.environ["PATH"] = str(pasta) + os.pathsep + os.environ.get("PATH", "")
        try:
            for dll in _DLLS_CUDA:
                ctypes.WinDLL(dll)
        except OSError:
            return False
        return True
    for nome in _SO_CUDA:   # Linux: carrega com RTLD_GLOBAL para o CTranslate2 achar depois
        candidatos = [p / nome for p in _pastas_nvidia("lib")] + [Path(nome)]
        if not any(_carrega_so(c) for c in candidatos):
            return False
    return True


def _carrega_so(caminho: Path) -> bool:
    import ctypes
    try:
        ctypes.CDLL(str(caminho), mode=ctypes.RTLD_GLOBAL)
        return True
    except OSError:
        return False


def _placas_cuda() -> int:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count()
    except Exception:  # noqa: BLE001
        return 0


def gpu_disponivel() -> bool:
    """Placa NVIDIA com as bibliotecas CUDA prontas para a transcrição."""
    return _placas_cuda() > 0 and _bibliotecas_cuda()


def motivo_sem_gpu() -> str | None:
    """Por que a placa NVIDIA não serve, para o diagnóstico: driver antigo ou bibliotecas ausentes."""
    if _placas_cuda() == 0:
        return "o driver da NVIDIA não responde ao CUDA 12: atualize o driver no site da NVIDIA (GeForce Experience ou nvidia.com/drivers)"
    if not _bibliotecas_cuda():
        return "faltam as bibliotecas CUDA"
    return None


def tipo_calculo_cuda() -> str:
    """float16 quando a placa faz essa conta com eficiência; senão int8 (placas antigas, GTX 9xx/10xx)."""
    try:
        import ctranslate2
        tipos = set(ctranslate2.get_supported_compute_types("cuda"))
    except Exception:  # noqa: BLE001
        return "float16"
    for tipo in ("float16", "int8_float16", "int8"):
        if tipo in tipos:
            return tipo
    return "float16"


def memoria_gpu_gb() -> float | None:
    import shutil
    import subprocess
    if not shutil.which("nvidia-smi"):
        return None
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                           capture_output=True, text=True, timeout=20)
        return int(r.stdout.strip().splitlines()[0].strip()) / 1024
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired):
        return None


def gpu_para_large_v3() -> bool:
    """Se a placa aguenta o modelo grande em float16: CUDA pronto, conta em float16 e memória suficiente.
    Placas fracas ou antigas ficam com o turbo (que também roda na placa), em vez de cair para o large-v3 na CPU."""
    if not gpu_disponivel() or tipo_calculo_cuda() != "float16":
        return False
    memoria = memoria_gpu_gb()
    return memoria is None or memoria >= MEMORIA_LARGE_V3_GB


def _dispositivo(pedido: str) -> tuple[str, str]:
    if pedido == "cpu":
        return "cpu", "int8"
    tem_gpu = _placas_cuda() > 0
    if tem_gpu and not _bibliotecas_cuda():
        print("  ⚠ placa NVIDIA encontrada, mas faltam as bibliotecas CUDA; usando CPU. "
              "Para usar a placa, rode o comando `instalar` de novo.")
        tem_gpu = False
    if pedido == "cuda" or (pedido == "auto" and tem_gpu):
        return "cuda", tipo_calculo_cuda()
    return "cpu", "int8"


def carregar_modelo(nome: str, dispositivo: str = "auto"):
    # Os modelos são públicos: o aviso do Hugging Face sobre "requisições sem token" só confunde.
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    from faster_whisper import WhisperModel

    nome = MODELOS_ALIAS.get(nome, nome)
    disp, tipo = _dispositivo(dispositivo)
    print(f"  ⚙ carregando modelo '{nome}' em {disp.upper()} (primeira vez baixa o modelo)…")
    try:
        modelo = WhisperModel(nome, device=disp, compute_type=tipo, cpu_threads=os.cpu_count() or 4)
    except Exception as e:  # noqa: BLE001 — GPU sem CUDA/cuDNN instalados, por exemplo
        if disp == "cpu":
            raise
        print(f"  ⚠ GPU indisponível ({e}); usando CPU.")
        disp, tipo = "cpu", "int8"
        modelo = WhisperModel(nome, device=disp, compute_type=tipo, cpu_threads=os.cpu_count() or 4)
    modelo._degravacao_info = {"modelo": nome, "dispositivo": disp}  # type: ignore[attr-defined]
    return modelo


def _barra(atual: float, total: float, inicio: float, estado: dict) -> None:
    if total <= 0:
        return
    frac = min(1.0, atual / total)
    decorrido = time.time() - inicio
    eta = (decorrido / frac - decorrido) if frac > 0.01 else 0
    if not sys.stdout.isatty():
        # Saída em arquivo (Claude Code em segundo plano, log): uma linha a cada 10%, sem \r.
        passo = int(frac * 10)
        if passo > estado.get("passo", 0):
            estado["passo"] = passo
            print(f"  ▶ {passo * 10}% · decorrido {int(decorrido // 60)} min · restante ~{int(eta // 60)} min", flush=True)
        return
    cheio = int(frac * 30)
    sys.stdout.write(
        f"\r  ▶ {'█' * cheio}{'░' * (30 - cheio)} {frac * 100:5.1f}%  "
        f"decorrido {int(decorrido // 60)}min  restante ~{int(eta // 60)}min   "
    )
    sys.stdout.flush()


ABREVIACOES = {"sr.", "sra.", "srs.", "dr.", "dra.", "drs.", "exa.", "exmo.", "exma.", "art.", "arts.",
               "inc.", "n.", "nº.", "fls.", "p.", "pág.", "min.", "proc.", "v.", "etc."}


def _frases(seg_ini: float, seg_fim: float, palavras: list[dict], texto: str) -> list[dict]:
    """Divide um segmento do Whisper em frases, usando o tempo de cada palavra.

    Mantém o texto original; só corta em pontuação final (. ? !) fora de abreviações.
    """
    if not palavras:
        return [{"ini": seg_ini, "fim": seg_fim, "txt": texto, "palavras": []}]
    grupos, atual = [], []
    for w in palavras:
        atual.append(w)
        token = w["txt"].strip().lower()
        if token.endswith((".", "?", "!", "…")) and token not in ABREVIACOES and len(atual) >= 3:
            grupos.append(atual)
            atual = []
    if atual:
        if grupos and len(atual) < 3:
            grupos[-1] += atual
        else:
            grupos.append(atual)
    return [
        {"ini": g[0]["ini"], "fim": g[-1]["fim"], "txt": "".join(w["txt"] for w in g).strip(), "palavras": g}
        for g in grupos
    ]


def carregar_audio(caminho: Path):
    """Decodifica uma vez (16 kHz, mono): serve à transcrição, à forma de onda e à separação de falantes."""
    from faster_whisper.audio import decode_audio
    return decode_audio(str(caminho), sampling_rate=16000)


def picos(audio, colunas: int) -> list[int]:
    """Forma de onda resumida (0–100 por coluna) para a linha do tempo do player."""
    import numpy as np

    colunas = max(1, min(colunas, len(audio)))
    if not len(audio):
        return []
    usado = len(audio) // colunas * colunas
    blocos = np.abs(audio[:usado]).reshape(colunas, -1).max(axis=1)
    referencia = float(np.percentile(blocos, 99)) or 1.0
    return [int(v) for v in np.clip(np.sqrt(blocos / referencia) * 100, 0, 100)]


def transcrever(modelo, audio, idioma: str | None = "pt", vocabulario: str = "") -> dict:
    """Transcreve integralmente (`audio` vem de carregar_audio) e devolve um dicionário serializável em JSON."""
    prompt_inicial = (
        "Transcrição fiel de gravação em português do Brasil, com pontuação, "
        "acentuação e nomes próprios corretos."
    )
    segmentos_iter, info = modelo.transcribe(
        audio,
        language=idioma or None,
        task="transcribe",
        beam_size=5,
        best_of=5,
        temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
        vad_filter=True,                       # remove silêncios longos (evita "alucinações")
        vad_parameters={"min_silence_duration_ms": 700},
        condition_on_previous_text=False,      # evita laços de repetição em gravações longas
        initial_prompt=prompt_inicial,
        hotwords=vocabulario or None,          # termos jurídicos, nomes de partes etc.
        word_timestamps=True,
        hallucination_silence_threshold=2.0,
    )

    inicio = time.time()
    progresso: dict = {}
    segmentos = []
    for s in segmentos_iter:
        palavras = [
            {"ini": round(float(w.start), 2), "fim": round(float(w.end), 2), "txt": w.word, "p": round(float(w.probability), 3)}
            for w in (s.words or [])
        ]
        texto = s.text.strip()
        if not texto:
            continue
        for f in _frases(round(float(s.start), 2), round(float(s.end), 2), palavras, texto):
            media_p = sum(w["p"] for w in f["palavras"]) / len(f["palavras"]) if f["palavras"] else 1.0
            segmentos.append({
                "i": len(segmentos),
                "ini": f["ini"],
                "fim": f["fim"],
                "txt": f["txt"],
                "logprob": round(float(s.avg_logprob), 3),     # do segmento original do Whisper
                "sem_fala": round(float(s.no_speech_prob), 3),
                "baixa_confianca": bool(s.avg_logprob < LIMIAR_LOGPROB or media_p < LIMIAR_PALAVRA),
                "palavras": f["palavras"],
            })
        _barra(s.end, info.duration, inicio, progresso)
    if sys.stdout.isatty():
        print()

    meta = getattr(modelo, "_degravacao_info", {})
    return {
        "idioma": info.language,
        "prob_idioma": round(float(info.language_probability), 3),
        "duracao": round(float(info.duration), 2),
        "duracao_com_fala": round(float(getattr(info, "duration_after_vad", info.duration)), 2),
        "modelo": meta.get("modelo", "?"),
        "dispositivo": meta.get("dispositivo", "?"),
        "tempo_processamento": round(time.time() - inicio, 1),
        "segmentos": segmentos,
        "picos": picos(audio, int(min(3000, max(400, info.duration * 4)))),
    }
