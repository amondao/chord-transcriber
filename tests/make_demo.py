# -*- coding: utf-8 -*-
"""検証用のデモ音源を生成する。

C - Am - F - G を各 2 秒で 2 回繰り返した和音を合成して demo.wav に保存。
C メジャーキーなので、期待されるディグリーは I - VIm - IV - V。
"""
import os
import sys
import numpy as np
import soundfile as sf

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SR = 22050
SEG = 2.0  # 1コードの秒数

# (ルートのピッチクラス, 構成音インターバル)
PROG = [
    (0, [0, 4, 7]),   # C  major  -> I
    (9, [0, 3, 7]),   # Am minor  -> VIm
    (5, [0, 4, 7]),   # F  major  -> IV
    (7, [0, 4, 7]),   # G  major  -> V
] * 2


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def render_chord(root_pc, intervals, dur, low=48):
    n = int(SR * dur)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    root_midi = low + root_pc
    notes = [root_midi - 12] + [root_midi + iv for iv in intervals] \
            + [root_midi + 12 + iv for iv in intervals]
    for m in notes:
        f = midi_freq(m)
        sig += np.sin(2 * np.pi * f * t)            # 基音
        sig += 0.4 * np.sin(2 * np.pi * 2 * f * t)  # 2倍音
    # クリック防止のフェード
    fade = int(0.01 * SR)
    env = np.ones(n)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    return sig * env


def main():
    audio = np.concatenate([render_chord(pc, iv, SEG) for pc, iv in PROG])
    audio /= np.max(np.abs(audio))
    out = os.path.join(os.path.dirname(__file__), 'demo.wav')
    sf.write(out, audio, SR)
    print(f"生成しました: {out}")


if __name__ == '__main__':
    main()
