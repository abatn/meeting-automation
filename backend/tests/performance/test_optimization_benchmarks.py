#!/usr/bin/env python3
"""ONNX + Sentinel Optimization Benchmark.
Baseline: ONNX=133.24s, Sentinel=111.30s, Pipeline=275.30s
Run: E2E_TEST=true pytest tests/performance/test_optimization_benchmarks.py -v -s
"""
import gc
import os
import struct
import time

import numpy as np
import pytest

AUDIO = os.environ.get("BENCHMARK_AUDIO_PATH", "/home/opc/meeting_benchmark.wav")
MDIR = os.path.join(os.path.dirname(__file__), "..", "..", "app", "models", "speaker_embeddings")
ONNX_P = os.path.join(MDIR, "ecapa-speaker-v1.onnx")
FBANK_P = os.path.join(MDIR, "fbank-80x201-f32.bin")
SENT_P = os.environ.get("SENTINEL_MODEL_PATH",
    "/home/opc/meeting-automation/qwen2.5-1.5b-instruct-q4_k_m.gguf")
SR = 16000


def _fbank():
    with open(FBANK_P, "rb") as f:
        d = f.read()
    return np.array(struct.unpack(f"{len(d)//4}f", d), dtype=np.float32).reshape(80, -1)


def _feats(audio, filters):
    audio = audio.astype(np.float32)
    if audio.ndim == 1:
        audio = audio[np.newaxis, :]
    n = audio.shape[1]
    fl = int(SR * 25.0 / 1000.0)
    fs = int(SR * 10.0 / 1000.0)
    nf = max(1, 1 + (n - fl) // fs)
    out = np.zeros((nf, 80), dtype=np.float32)
    for i in range(nf):
        s2 = i * fs
        e2 = min(s2 + fl, n)
        fr = audio[0, s2:e2]
        if len(fr) < fl:
            fr = np.pad(fr, (0, fl - len(fr)))
        fr = fr * np.hamming(fl)
        sp = np.abs(np.fft.rfft(fr, n=400))[:filters.shape[1]]
        out[i] = np.log(np.dot(filters, sp) + 1e-30)
    return out - np.mean(out, axis=0, keepdims=True)


def _onnx(threads=1, parallel=False, arena=False):
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.intra_op_num_threads = threads
    so.execution_mode = ort.ExecutionMode.ORT_PARALLEL if parallel else ort.ExecutionMode.ORT_SEQUENTIAL
    so.enable_cpu_mem_arena = arena
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(ONNX_P, sess_options=so, providers=["CPUExecutionProvider"])


def _sentinel(n_threads=1, n_ctx=2048):
    from llama_cpp import Llama
    return Llama(model_path=SENT_P, n_ctx=n_ctx, n_threads=n_threads, verbose=False)


@pytest.fixture(scope="module")
def fb():
    return _fbank()


@pytest.fixture(scope="module")
def feats(fb):
    import librosa
    a2, _ = librosa.load(AUDIO, sr=SR, mono=True)
    out = []
    st = 0
    while st < len(a2):
        en = min(st + int(16.0 * SR), len(a2))
        seg = a2[st:en]
        if len(seg) >= SR:
            out.append(_feats(seg, fb))
        st = en
    return out[:33]


@pytest.fixture(scope="module")
def chunks():
    c1 = ("Speaker A: Bonjour. Budget. Speaker B: D accord. " * 8)
    c2 = ("Speaker A: Plan trimestriel. Speaker B: Priorites? " * 8)
    c3 = ("Speaker A: Decisions finales. Speaker B: Approuve. " * 8)
    return [c1, c2, c3]


class TestONNXOptimization:
    """Benchmark ONNX with different thread/parallel/arena configs."""
    MAX = 200

    def _run(self, sess, fts, label):
        t0 = time.time()
        n = 0
        for f in fts:
            e = f[np.newaxis, ...].astype(np.float32)
            l = np.array([f.shape[0]], dtype=np.float32)
            sess.run(None, {"features": e, "feature_lens": l})
            n += 1
        dt = time.time() - t0
        print(f"\n  ONNX [{label}]: {dt:.2f}s / {n} segs = {dt/n:.3f} s/seg")
        return dt

    def test_a1_baseline_t1(self, feats):
        s = _onnx(1, False, False); t = self._run(s, feats, "baseline t=1"); del s; gc.collect()
        assert t < self.MAX

    def test_a2_threads_2(self, feats):
        s = _onnx(2, False, False); t = self._run(s, feats, "threads=2"); del s; gc.collect()
        assert t < self.MAX

    def test_a3_threads_4(self, feats):
        s = _onnx(4, False, False); t = self._run(s, feats, "threads=4"); del s; gc.collect()
        assert t < self.MAX

    def test_a4_parallel(self, feats):
        s = _onnx(2, True, False); t = self._run(s, feats, "PARALLEL t=2"); del s; gc.collect()
        assert t < self.MAX

    def test_a5_arena_on(self, feats):
        s = _onnx(1, False, True); t = self._run(s, feats, "arena=ON"); del s; gc.collect()
        assert t < self.MAX


class TestSentinelOptimization:
    """Benchmark Sentinel with different thread configs."""
    MAX = 200

    def _run(self, llm, ch, label):
        from app.services.sentinel_service import SentinelService
        svc = SentinelService.__new__(SentinelService)
        svc.llm = llm
        svc._semaphore = __import__("asyncio").Semaphore(1)
        import asyncio
        t0 = time.time()
        for c in ch:
            asyncio.get_event_loop().run_until_complete(svc.summarize_chunk(c))
        dt = time.time() - t0
        print(f"\n  Sentinel [{label}]: {dt:.2f}s / {len(ch)} chunks")
        return dt

    def test_b1_baseline_t1(self, chunks):
        llm = _sentinel(1); t = self._run(llm, chunks, "baseline t=1"); del llm; gc.collect()
        assert t < self.MAX

    def test_b2_threads_2(self, chunks):
        llm = _sentinel(2); t = self._run(llm, chunks, "threads=2"); del llm; gc.collect()
        assert t < self.MAX

    def test_b3_threads_4(self, chunks):
        llm = _sentinel(4); t = self._run(llm, chunks, "threads=4"); del llm; gc.collect()
        assert t < self.MAX


class TestCombinedOptimization:
    """Test best ONNX + Sentinel combination."""
    MAX = 150

    def test_c1_best_combo(self, feats, chunks):
        s = _onnx(2, False, False)
        llm = _sentinel(2)
        t0 = time.time()
        for f in feats:
            e = f[np.newaxis, ...].astype(np.float32)
            l = np.array([f.shape[0]], dtype=np.float32)
            s.run(None, {"features": e, "feature_lens": l})
        from app.services.sentinel_service import SentinelService
        svc = SentinelService.__new__(SentinelService)
        svc.llm = llm
        svc._semaphore = __import__("asyncio").Semaphore(1)
        import asyncio
        for c in chunks:
            asyncio.get_event_loop().run_until_complete(svc.summarize_chunk(c))
        dt = time.time() - t0
        print(f"\n  Combined: {dt:.2f}s (ONNX t=2 + Sentinel t=2)")
        del s, llm; gc.collect()
        assert dt < self.MAX