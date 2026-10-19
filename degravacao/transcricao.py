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


def _dispositivo(pedido: str) -> tuple[str, str]:
    if pedido == "cpu":
        return "cpu", "int8"
    try:
        import ctranslate2
        tem_gpu = ctranslate2.get_cuda_device_count() > 0
    except Exception:  # noqa: BLE001
        tem_gpu = False
    if pedido == "cuda" or (pedido == "auto" and tem_gpu):
        return "cuda", "float16"
    return "cpu", "int8"


def carregar_modelo(nome: str, dispositivo: str = "auto"):
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


def _barra(atual: float, total: float, inicio: float) -> None:
    if total <= 0:
        return
    frac = min(1.0, atual / total)
    decorrido = time.time() - inicio
    eta = (decorrido / frac - decorrido) if frac > 0.01 else 0
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


def transcrever(modelo, caminho: Path, idioma: str | None = "pt", vocabulario: str = "") -> dict:
    """Transcreve integralmente e devolve um dicionário serializável em JSON."""
    prompt_inicial = (
        "Transcrição fiel de gravação em português do Brasil, com pontuação, "
        "acentuação e nomes próprios corretos."
    )
    segmentos_iter, info = modelo.transcribe(
        str(caminho),
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
        _barra(s.end, info.duration, inicio)
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
    }
