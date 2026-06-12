# 🎵 chord-transcriber

曲（音声ファイル）を読み込み、コード進行を **キーに対するディグリーネーム（度数表記）** で
書き起こすツールです。**コマンドライン版**と**ブラウザ版（Webアプリ）**の両方が使えます。

> 例: C メジャーの曲で `C → Am → F → G` なら `I → VIm → IV → V`

## 特長

- 追加の重いライブラリ不要（**numpy / scipy / soundfile** のみ、librosa 不使用）
- WAV / MP3 / FLAC / OGG はそのまま、m4a / aac 等は **ffmpeg** 経由で読み込み
- **キー自動検出**（手動指定も可能）
- メジャー / マイナー / dim / aug、7th コードに対応
- **CLI** ・ **ブラウザUI** ・ **クラウドデプロイ（Docker）** に対応

## ファイル構成

```
chord-transcriber/
├── chord_transcribe.py     # ★コア＆CLI：解析・コード/キー検出・ディグリー変換
├── webapp.py               # ブラウザ版サーバー（Flask。コアを再利用）
├── index.html              # ブラウザ版の画面
├── ここに曲をドロップ.bat        # CLIを「曲をドロップ」で実行（Windows）
├── Webアプリを起動.bat          # ブラウザ版を起動（Windows）
├── requirements.txt        # 依存パッケージ
├── Dockerfile              # クラウド公開用イメージ定義
├── .dockerignore / .gitignore
├── DEPLOY.md               # インターネット常時公開の手順
└── tests/
    ├── make_demo.py        # 検証用デモ音源（C-Am-F-G）の生成
    └── test_webapp.py      # Web版の自動検証（Flask test_client）
```

## セットアップ

```bash
pip install -r requirements.txt
```

WAV / MP3 / FLAC / OGG だけなら上記でOK。m4a / aac / wma 等も扱うなら別途
[ffmpeg](https://ffmpeg.org/) を導入してください。

---

## 使い方

### A. ブラウザ版（おすすめ）

`Webアプリを起動.bat` をダブルクリックすると、ブラウザが開きます（`http://127.0.0.1:5000`）。
曲をドラッグ＆ドロップして「解析する」を押すだけです。

```bash
# コマンドで起動する場合
python webapp.py
```

画面でできること：キー手動指定／検出モード切替／安定度調整／結果のCSVダウンロード。

### B. コマンドライン版

```bash
python chord_transcribe.py 曲.mp3
```

Windows では `ここに曲をドロップ.bat` に曲をドラッグ＆ドロップしてもOK。

#### オプション

| オプション | 説明 |
|------------|------|
| `--key C` / `--key Am` / `--key "Bb major"` | キーを手動指定（自動検出が外れたとき） |
| `--seventh` | 7th コード（7・m7・M7）も検出対象に加える |
| `--simple`  | メジャー / マイナーの三和音だけで検出（最も安定） |
| `--penalty 0.5` | コードの変わりにくさ。大きいほど安定（既定 0.3） |
| `--min-dur 0.5` | 1 コードの最小継続秒数（既定 0.4） |
| `--csv out.csv` | 結果を CSV 保存 |

#### 出力例

```
キー : C major（自動検出）
長さ : 0:16.00

区間                    コード       ディグリー
------------------------------------------------
0:00.19 - 0:02.04     C         I
0:02.04 - 0:04.09     Am        VIm
0:04.09 - 0:06.04     F         IV
0:06.04 - 0:08.08     G         V

進行 : I | VIm | IV | V
```

---

## 仕組み

1. 音声を 22.05kHz モノラルに変換
2. STFT からクロマグラム（12 音名ごとのエネルギー）を計算
3. コードテンプレートとのコサイン類似度を取り、Viterbi で時間方向に平滑化
4. Krumhansl-Schmuckler 法でキーを自動推定
5. 各コードのルート度数をディグリーネームへ変換

ディグリー表記は日本のポピュラー音楽で一般的な
**「大文字ローマ数字＋サフィックス」**（例: `IIm` `V7` `bVII`）方式です。

## 精度について

クロマ特徴に基づく自動採譜のため万能ではありません。目安として:

- ピアノ / 弾き語り / シンプルなバンド編成 … 比較的良好
- 歪んだギター・厚いシンセ・転調の多い曲 … 誤検出が増えがち

うまくいかないときの調整:

- キーが外れる → `--key` で明示
- コードが細かく揺れる → `--penalty` を上げる / `--min-dur` を増やす
- テンションを拾いたい → `--seventh`
- とにかく安定させたい → `--simple`

## デモ

```bash
python tests/make_demo.py            # tests/demo.wav を生成（C-Am-F-G のループ）
python chord_transcribe.py tests/demo.wav
python tests/test_webapp.py          # Web版の動作を検証
```

## インターネット公開

Docker 化済みで、Render / Google Cloud Run などへ常時公開できます。
手順は **[DEPLOY.md](DEPLOY.md)** を参照してください。

## ライセンス

[MIT License](LICENSE) © 2026 amondao — 著作権表示を残せば、自由に使用・改変・再配布できます（無保証）。

---

※ `songs/` フォルダ（手元の楽曲）と `tests/demo.wav`、`__pycache__/` は
`.gitignore` で除外しているため、リポジトリには含まれません。
