#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chord_transcribe.py
====================
曲（音声ファイル）を読み込み、コード進行を検出して
キーに対するディグリーネーム（度数表記）で書き起こすツール。

依存: numpy, scipy, soundfile （いずれもインストール済み）
      非対応フォーマット(m4a等)は ffmpeg があれば自動変換して読み込む。

処理の流れ:
  1. 音声を読み込み 22.05kHz モノラルに変換
  2. STFT からクロマグラム（12音名ごとのエネルギー）を計算
  3. コードテンプレートと照合し、Viterbi で時間方向に平滑化
  4. Krumhansl-Schmuckler 法でキーを自動推定
  5. 各コードのルート度数からディグリーネームへ変換して出力

使い方:
  python chord_transcribe.py 曲.mp3
  python chord_transcribe.py 曲.wav --key Am --seventh --csv out.csv
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import stft, resample_poly

# --------------------------------------------------------------------------
# 定数
# --------------------------------------------------------------------------
TARGET_SR = 22050
PITCH_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# コードの構成音（Cルート=0 を基準としたピッチクラス）
CHORD_DEFS = {
    'maj':  [0, 4, 7],
    'min':  [0, 3, 7],
    'dim':  [0, 3, 6],
    'aug':  [0, 4, 8],
    '7':    [0, 4, 7, 10],
    'min7': [0, 3, 7, 10],
    'maj7': [0, 4, 7, 11],
}
# 表記用サフィックス（実音名・ディグリー共通）
QUALITY_SUFFIX = {
    'maj': '', 'min': 'm', 'dim': 'dim', 'aug': 'aug',
    '7': '7', 'min7': 'm7', 'maj7': 'M7',
}

# ルートからの半音差 → ディグリー（ローマ数字）。ASCII の b/# で表記。
DEGREE_MAJOR = ['I', 'bII', 'II', 'bIII', 'III', 'IV',
                '#IV', 'V', 'bVI', 'VI', 'bVII', 'VII']
DEGREE_MINOR = ['I', 'bII', 'II', 'bIII', 'III', 'IV',
                '#IV', 'V', 'bVI', 'VI', 'bVII', 'VII']

# Krumhansl-Schmuckler キープロファイル
KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                     2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                     2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


# --------------------------------------------------------------------------
# 音声読み込み
# --------------------------------------------------------------------------
def load_audio(path, target_sr=TARGET_SR):
    """音声ファイルを読み込み、target_sr のモノラル float 配列を返す。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"ファイルが見つかりません: {path}")
    try:
        y, sr = sf.read(path, dtype='float64', always_2d=False)
    except Exception:
        # soundfile が読めない形式は ffmpeg で WAV に変換
        y, sr = _load_via_ffmpeg(path, target_sr)

    if y.ndim > 1:                       # ステレオ → モノラル
        y = y.mean(axis=1)
    if sr != target_sr:                  # リサンプリング
        g = gcd(int(sr), int(target_sr))
        y = resample_poly(y, target_sr // g, sr // g)
        sr = target_sr
    peak = np.max(np.abs(y)) if y.size else 0.0
    if peak > 0:
        y = y / peak                     # 振幅正規化
    return y.astype(np.float64), sr


def _load_via_ffmpeg(path, target_sr):
    """ffmpeg 経由で読み込む（m4a / aac / wma など）。"""
    try:
        with tempfile.TemporaryDirectory() as td:
            out = os.path.join(td, 'tmp.wav')
            subprocess.run(
                ['ffmpeg', '-v', 'error', '-y', '-i', path,
                 '-ac', '1', '-ar', str(target_sr), out],
                check=True,
            )
            y, sr = sf.read(out, dtype='float64')
        return y, sr
    except FileNotFoundError:
        raise RuntimeError(
            "この形式は soundfile で直接読めず、ffmpeg も見つかりません。"
            "WAV/FLAC/MP3/OGG に変換するか ffmpeg を導入してください。"
        )


# --------------------------------------------------------------------------
# クロマグラム
# --------------------------------------------------------------------------
def compute_chroma(y, sr, n_fft=8192, hop=2048, fmin=55.0, fmax=2200.0):
    """STFT から 12 次元クロマグラムを計算する。

    返り値:
        chroma_norm : (12, n_frames)  フレームごとに L2 正規化したクロマ
        energy      : (n_frames,)     フレームの帯域内エネルギー
        times       : (n_frames,)     各フレームの時刻[秒]
    """
    f, t, Z = stft(y, fs=sr, window='hann', nperseg=n_fft,
                   noverlap=n_fft - hop, boundary=None, padded=False)
    power = np.abs(Z) ** 2

    # 解析対象の周波数だけ残す
    band = (f >= fmin) & (f <= fmax) & (f > 0)
    f = f[band]
    power = power[band, :]

    # 各周波数ビンを最も近いピッチクラスへ割り当て
    midi = 69 + 12 * np.log2(f / 440.0)
    pc = np.mod(np.round(midi).astype(int), 12)

    chroma = np.zeros((12, power.shape[1]))
    for k in range(12):
        mask = pc == k
        if np.any(mask):
            chroma[k, :] = power[mask, :].sum(axis=0)

    energy = chroma.sum(axis=0)
    chroma = np.log1p(chroma)                 # 対数圧縮でピークをならす
    norm = np.linalg.norm(chroma, axis=0)
    norm[norm == 0] = 1.0
    return chroma / norm, energy, t


# --------------------------------------------------------------------------
# コードテンプレート照合
# --------------------------------------------------------------------------
def build_templates(qualities):
    """指定したコード種を 12 ルート分展開してテンプレート行列を作る。"""
    templates, labels = [], []
    for q in qualities:
        base = np.zeros(12)
        for iv in CHORD_DEFS[q]:
            base[iv % 12] = 1.0
        base /= np.linalg.norm(base)
        for root in range(12):
            templates.append(np.roll(base, root))   # ルートへ回転
            labels.append((root, q))
    return np.array(templates), labels


def viterbi_smooth(sim, trans_penalty=0.3):
    """類似度系列を Viterbi で平滑化し、各フレームのコード番号列を返す。

    遷移コストは「同じコードを維持=0 / 別コードへ変化=-trans_penalty」。
    penalty が大きいほどコードが切り替わりにくく安定する。
    """
    n, T = sim.shape
    score = np.full((n, T), -np.inf)
    back = np.zeros((n, T), dtype=int)
    score[:, 0] = sim[:, 0]

    for t in range(1, T):
        prev = score[:, t - 1]
        order = np.argsort(prev)[::-1]
        best1, best2 = order[0], order[1]    # 自分以外の最良元を選ぶため上位2つ
        for s in range(n):
            stay = prev[s]                   # 同じコードを維持
            src = best2 if s == best1 else best1
            switch = prev[src] - trans_penalty   # 別コードから遷移
            if stay >= switch:
                score[s, t] = sim[s, t] + stay
                back[s, t] = s
            else:
                score[s, t] = sim[s, t] + switch
                back[s, t] = src

    path = np.empty(T, dtype=int)
    path[-1] = int(np.argmax(score[:, -1]))
    for t in range(T - 2, -1, -1):
        path[t] = back[path[t + 1], t + 1]
    return path


# --------------------------------------------------------------------------
# セグメント化
# --------------------------------------------------------------------------
def segmentize(path, times, min_dur=0.4):
    """フレーム列を (開始, 終了, コード番号) のセグメントへまとめる。"""
    if len(times) > 1:
        frame_dur = float(np.median(np.diff(times)))
    else:
        frame_dur = 0.0

    segs, start = [], 0
    for i in range(1, len(path)):
        if path[i] != path[start]:
            segs.append([times[start], times[i], int(path[start])])
            start = i
    segs.append([times[start], times[-1] + frame_dur, int(path[start])])

    return _merge_short(segs, min_dur)


def _merge_short(segs, min_dur):
    """短すぎるセグメントを隣接する長い方へ吸収する。"""
    while len(segs) > 1:
        for i, (s0, s1, _) in enumerate(segs):
            if s1 - s0 >= min_dur:
                continue
            if i == 0:
                segs[1][0] = segs[0][0]
                del segs[0]
            elif i == len(segs) - 1:
                segs[-2][1] = segs[-1][1]
                del segs[-1]
            else:
                left = segs[i - 1][1] - segs[i - 1][0]
                right = segs[i + 1][1] - segs[i + 1][0]
                if left >= right:
                    segs[i - 1][1] = segs[i][1]
                else:
                    segs[i + 1][0] = segs[i][0]
                del segs[i]
            break
        else:
            break  # 短いセグメントが無くなった

    # 吸収の結果できた同一コードの連続を結合
    merged = [segs[0]]
    for s in segs[1:]:
        if s[2] == merged[-1][2]:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return merged


# --------------------------------------------------------------------------
# キー検出
# --------------------------------------------------------------------------
def detect_key(chroma_norm, energy):
    """エネルギー重み付き平均クロマからキーを推定する。"""
    w = energy if energy.sum() > 0 else np.ones_like(energy)
    prof = (chroma_norm * w).sum(axis=1)
    prof = prof - prof.mean()

    maj = KS_MAJOR - KS_MAJOR.mean()
    minp = KS_MINOR - KS_MINOR.mean()

    best = (-np.inf, 0, 'major')
    for tonic in range(12):
        cmaj = np.corrcoef(prof, np.roll(maj, tonic))[0, 1]
        cmin = np.corrcoef(prof, np.roll(minp, tonic))[0, 1]
        if cmaj > best[0]:
            best = (cmaj, tonic, 'major')
        if cmin > best[0]:
            best = (cmin, tonic, 'minor')
    return best[1], best[2]


# --------------------------------------------------------------------------
# 表記変換
# --------------------------------------------------------------------------
def chord_name(root_pc, quality):
    return PITCH_NAMES[root_pc] + QUALITY_SUFFIX[quality]


def to_degree(root_pc, quality, tonic, mode):
    interval = (root_pc - tonic) % 12
    table = DEGREE_MAJOR if mode == 'major' else DEGREE_MINOR
    return table[interval] + QUALITY_SUFFIX[quality]


def parse_key(text):
    """'C' / 'Am' / 'F#m' / 'Bb major' などを (tonic_pc, mode) に変換。"""
    m = re.match(r'^\s*([A-Ga-g])([#b♯♭]?)\s*(.*)$', text)
    if not m:
        raise ValueError(f"キーを解釈できません: {text}")
    base = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}[m.group(1).upper()]
    acc = m.group(2)
    if acc in ('#', '♯'):
        base = (base + 1) % 12
    elif acc in ('b', '♭'):
        base = (base - 1) % 12
    rest = m.group(3).lower()
    mode = 'minor' if (rest.startswith('m') and not rest.startswith('maj')) else 'major'
    return base, mode


def fmt_time(sec):
    m = int(sec // 60)
    return f"{m}:{sec - 60 * m:05.2f}"


# --------------------------------------------------------------------------
# メイン処理
# --------------------------------------------------------------------------
def transcribe(path, qualities, key=None, trans_penalty=0.3,
               min_dur=0.4, n_fft=8192, hop=2048):
    y, sr = load_audio(path)
    duration = len(y) / sr

    chroma, energy, times = compute_chroma(y, sr, n_fft=n_fft, hop=hop)
    if chroma.shape[1] == 0:
        raise RuntimeError("音声が短すぎて解析できません。")

    tonic, mode = parse_key(key) if key else detect_key(chroma, energy)

    templates, labels = build_templates(qualities)
    sim = templates @ chroma                 # (n_chords, n_frames) コサイン類似度
    path_idx = viterbi_smooth(sim, trans_penalty)
    segments = segmentize(path_idx, times, min_dur)

    rows = []
    for s0, s1, ci in segments:
        root, q = labels[ci]
        rows.append({
            'start': s0, 'end': s1,
            'chord': chord_name(root, q),
            'degree': to_degree(root, q, tonic, mode),
        })
    return {
        'duration': duration,
        'tonic': tonic, 'mode': mode, 'key_given': key is not None,
        'segments': rows,
    }


def print_report(result):
    key = f"{PITCH_NAMES[result['tonic']]} {result['mode']}"
    src = '指定' if result['key_given'] else '自動検出'
    print()
    print(f"キー : {key}（{src}）")
    print(f"長さ : {fmt_time(result['duration'])}")
    print()
    print(f"{'区間':<22}{'コード':<10}ディグリー")
    print('-' * 48)
    for r in result['segments']:
        span = f"{fmt_time(r['start'])} - {fmt_time(r['end'])}"
        print(f"{span:<22}{r['chord']:<10}{r['degree']}")
    print()
    print('進行 : ' + ' | '.join(r['degree'] for r in result['segments']))
    print()


def save_csv(result, path):
    import csv
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['start_sec', 'end_sec', 'chord', 'degree'])
        for r in result['segments']:
            w.writerow([f"{r['start']:.3f}", f"{r['end']:.3f}", r['chord'], r['degree']])


def main(argv=None):
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    p = argparse.ArgumentParser(
        description='曲のコード進行をディグリーネームで書き起こします。')
    p.add_argument('audio', help='音声ファイル (wav/mp3/flac/ogg/m4a ...)')
    p.add_argument('--key', help='キーを手動指定 (例: C / Am / F#m / "Bb major")')
    p.add_argument('--seventh', action='store_true',
                   help='7th コード(7, m7, M7)も検出対象に加える')
    p.add_argument('--simple', action='store_true',
                   help='メジャー/マイナーの三和音だけで検出する')
    p.add_argument('--penalty', type=float, default=0.3,
                   help='コード変化のしにくさ (大きいほど安定。既定 0.3)')
    p.add_argument('--min-dur', type=float, default=0.4,
                   help='1コードの最小継続秒数 (既定 0.4)')
    p.add_argument('--csv', help='結果を CSV に保存するパス')
    args = p.parse_args(argv)

    if args.simple:
        qualities = ['maj', 'min']
    elif args.seventh:
        qualities = ['maj', 'min', 'dim', 'aug', '7', 'min7', 'maj7']
    else:
        qualities = ['maj', 'min', 'dim', 'aug']

    try:
        result = transcribe(args.audio, qualities, key=args.key,
                            trans_penalty=args.penalty, min_dur=args.min_dur)
    except Exception as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 1

    print_report(result)
    if args.csv:
        save_csv(result, args.csv)
        print(f"CSV を保存しました: {args.csv}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
