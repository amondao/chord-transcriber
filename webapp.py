#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webapp.py — chord-transcriber のブラウザ UI（Flask）

ブラウザで曲をアップロードすると chord_transcribe.transcribe() で解析し、
キー・コード進行・ディグリーネームを表示する。

起動:
    python webapp.py
    → ブラウザで http://127.0.0.1:5000 を開く
"""
import os
import tempfile

from flask import Flask, request, jsonify

from chord_transcribe import transcribe, PITCH_NAMES, fmt_time

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 80 * 1024 * 1024  # アップロード上限 80MB

# 検出モード → コード種テンプレート
QUALITY_SETS = {
    'standard': ['maj', 'min', 'dim', 'aug', 'sus4', 'sus2'],
    'simple':   ['maj', 'min'],
    'seventh':  ['maj', 'min', 'dim', 'aug', 'sus4', 'sus2',
                 '7', 'min7', 'maj7', 'm7b5', 'dim7'],
    'full':     ['maj', 'min', 'dim', 'aug', 'sus4', 'sus2',
                 '7', 'min7', 'maj7', 'm7b5', 'dim7',
                 'add9', '9', 'maj9', 'm9'],
}

HERE = os.path.dirname(os.path.abspath(__file__))


@app.route('/')
def index():
    # Jinja を通さずそのまま返す（HTML/CSS/JS の波括弧と衝突させない）
    with open(os.path.join(HERE, 'index.html'), encoding='utf-8') as fp:
        return fp.read()


@app.route('/analyze', methods=['POST'])
def analyze():
    f = request.files.get('file')
    if f is None or f.filename == '':
        return jsonify({'error': 'ファイルが選択されていません。'}), 400

    mode = request.form.get('mode', 'standard')
    qualities = QUALITY_SETS.get(mode, QUALITY_SETS['standard'])
    key = (request.form.get('key') or '').strip() or None
    try:
        penalty = float(request.form.get('penalty', 0.3))
    except ValueError:
        penalty = 0.3

    try:
        with tempfile.TemporaryDirectory() as td:
            # 日本語ファイル名でも拡張子だけ保持して一時保存
            ext = os.path.splitext(f.filename)[1].lower() or '.wav'
            path = os.path.join(td, 'audio' + ext)
            f.save(path)
            result = transcribe(path, qualities, key=key, trans_penalty=penalty)
    except Exception as e:
        return jsonify({'error': f'解析に失敗しました: {e}'}), 500

    # 表示用に整形
    result['key_name'] = f"{PITCH_NAMES[result['tonic']]} {result['mode']}"
    result['duration_str'] = fmt_time(result['duration'])
    for seg in result['segments']:
        seg['start_str'] = fmt_time(seg['start'])
        seg['end_str'] = fmt_time(seg['end'])
    result['filename'] = f.filename
    return jsonify(result)


if __name__ == '__main__':
    print('chord-transcriber web app  ->  http://127.0.0.1:5000')
    app.run(host='127.0.0.1', port=5000, debug=False)
