"""Separação de falantes (diarização) local com sherpa-onnx — sem conta nem chave.

Modelos baixados do GitHub do projeto sherpa-onnx no primeiro uso:
- segmentação: pyannote segmentation-3.0 convertido para ONNX (licença MIT);
- identificação de voz: WeSpeaker ResNet34 treinado no VoxCeleb (licença Apache 2.0).

O resultado é acústico e aproximado: frases curtas e trocas rápidas de pergunta e
resposta são as mais sujeitas a erro, por isso ficam marcadas como "falante a conferir".
"""

from __future__ import annotations

import bz2
import os
import shutil
import tarfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
SEGMENTACAO_TAR = f"{BASE}/speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2"
SEGMENTACAO_MEMBRO = "sherpa-onnx-pyannote-segmentation-3-0/model.onnx"
EMBEDDING = f"{BASE}/speaker-recongition-models/wespeaker_en_voxceleb_resnet34.onnx"

LIMIAR_PADRAO = 0.5       # agrupamento quando o número de falantes não é informado
PALAVRAS_CURTA = 4        # frases até este tamanho têm atribuição pouco confiável
SOBREPOSICAO_MINIMA = 0.6  # fração da frase que precisa cair no mesmo falante


def _baixar(url: str, destino: Path) -> None:
    tmp = destino.with_suffix(destino.suffix + ".parcial")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(destino)


def garantir_modelos(pasta: Path) -> tuple[Path, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    seg = pasta / "segmentacao-pyannote-3.0.onnx"
    emb = pasta / "wespeaker_en_voxceleb_resnet34.onnx"
    if not seg.exists():
        print("  ↓ baixando modelo de segmentação de falantes (7 MB)…")
        tar = pasta / "segmentacao.tar.bz2"
        _baixar(SEGMENTACAO_TAR, tar)
        with bz2.open(tar) as b, tarfile.open(fileobj=b, mode="r|") as t:
            for m in t:
                if m.name == SEGMENTACAO_MEMBRO:  # extrai só o arquivo esperado
                    with t.extractfile(m) as origem, open(seg, "wb") as f:
                        shutil.copyfileobj(origem, f)
                    break
        tar.unlink()
        if not seg.exists():
            raise RuntimeError("pacote de segmentação não contém o modelo esperado")
    if not emb.exists():
        print("  ↓ baixando modelo de identificação de voz (26 MB)…")
        _baixar(EMBEDDING, emb)
    return seg, emb


def diarizar(caminho: Path, pasta_modelos: Path, num_falantes: int | None = None,
             limiar: float = LIMIAR_PADRAO, audio=None) -> list[tuple[float, float, str]]:
    import sherpa_onnx
    from faster_whisper.audio import decode_audio

    seg, emb = garantir_modelos(pasta_modelos)
    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig(model=str(seg)),
            num_threads=os.cpu_count() or 4),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(emb), num_threads=os.cpu_count() or 4),
        clustering=sherpa_onnx.FastClusteringConfig(num_clusters=num_falantes or -1, threshold=limiar),
        min_duration_on=0.0,
        min_duration_off=0.0,
    )
    if not cfg.validate():
        raise RuntimeError("configuração de diarização inválida")
    print(f"  ⚙ separando falantes{f' ({num_falantes} informados)' if num_falantes else ''}…")
    inicio = time.time()
    if audio is None:   # já decodificado na transcrição, quando vem de lá
        audio = decode_audio(str(caminho), sampling_rate=16000)
    res = sherpa_onnx.OfflineSpeakerDiarization(cfg).process(audio).sort_by_start_time()
    print(f"  ✓ falantes separados em {(time.time() - inicio) / 60:.1f} min")
    return [(float(r.start), float(r.end), str(r.speaker)) for r in res]


def atribuir(segmentos: list[dict], turnos: list[tuple[float, float, str]]) -> dict:
    """Grava em cada frase o falante majoritário (F1, F2… por ordem de aparição).

    Devolve o resumo {"F1": {"nome": None, "tempo": segundos}, …}.
    """
    if not turnos:
        return {}
    rotulos: dict[str, str] = {}

    def rotulo(cluster: str) -> str:
        if cluster not in rotulos:
            rotulos[cluster] = f"F{len(rotulos) + 1}"
        return rotulos[cluster]

    def sobreposicao(ini: float, fim: float) -> Counter:
        c: Counter = Counter()
        for a, b, f in turnos:
            if b <= ini:
                continue
            if a >= fim:
                break
            c[f] += min(b, fim) - max(a, ini)
        return c

    for s in segmentos:
        c: Counter = Counter()
        for w in s.get("palavras") or [{"ini": s["ini"], "fim": s["fim"]}]:
            c.update(sobreposicao(w["ini"], w["fim"]))
        if c:
            cluster, tempo = c.most_common(1)[0]
            parcela = tempo / sum(c.values())
        else:  # frase sem fala detectada pela diarização: turno mais próximo
            meio = (s["ini"] + s["fim"]) / 2
            cluster = min(turnos, key=lambda t: min(abs(t[0] - meio), abs(t[1] - meio)))[2]
            parcela = 0.0
        s["falante"] = s["falante_acustico"] = rotulo(cluster)
        s["falante_incerto"] = bool(len(s["txt"].split()) <= PALAVRAS_CURTA or parcela < SOBREPOSICAO_MINIMA)

    return resumo(segmentos)


def resumo(segmentos: list[dict], anterior: dict | None = None) -> dict:
    tempos: dict[str, float] = {}
    for s in segmentos:
        if s.get("falante"):
            tempos[s["falante"]] = tempos.get(s["falante"], 0.0) + s["fim"] - s["ini"]
    anterior = anterior or {}
    return {
        f: {"nome": (anterior.get(f) or {}).get("nome"), "tempo": round(t, 1)}
        for f, t in sorted(tempos.items(), key=lambda kv: int(kv[0][1:]))
    }


def nome(dados: dict, rotulo: str | None) -> str:
    if not rotulo:
        return ""
    info = (dados.get("falantes") or {}).get(rotulo) or {}
    return info.get("nome") or f"Falante {rotulo[1:]}"
