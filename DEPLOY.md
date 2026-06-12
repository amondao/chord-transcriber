# デプロイ手順（インターネット常時公開）

このアプリは Docker 化済みなので、Docker に対応したクラウドならどこでも公開できます。
ここでは **Render（簡単・無料枠あり）** を主に、**Google Cloud Run（重い処理向け）** も説明します。

---

## 事前準備：GitHub にコードを上げる

どのサービスも GitHub 連携が基本です。`chord-transcriber` フォルダで:

```bash
git init
git add .
git commit -m "chord-transcriber web app"
```

GitHub で空のリポジトリを作成し、表示される手順に従って push:

```bash
git remote add origin https://github.com/<あなたのID>/chord-transcriber.git
git branch -M main
git push -u origin main
```

---

## 方法A：Render（おすすめ・無料で試せる）

1. https://render.com にアクセスし、GitHub アカウントでサインアップ
2. ダッシュボードで **New +** → **Web Service**
3. さきほどの GitHub リポジトリを選択
4. 設定:
   - **Language / Runtime**: Docker（リポジトリの `Dockerfile` を自動検出）
   - **Instance Type**: まずは **Free**（512MB）。安定運用は **Starter（$7/月〜）**
5. **Create Web Service** を押すとビルド＆デプロイが始まり、
   `https://xxxx.onrender.com` のような URL が発行されます

### Render 無料枠の注意
- 15分アクセスがないと **スリープ** し、次回アクセス時に起動へ数十秒かかる
- メモリ512MB。**長い曲（5分以上）はメモリ不足で落ちる** ことがある（対策は末尾）

---

## 方法B：Google Cloud Run（メモリを増やせる＝長い曲も安定）

[`gcloud` CLI](https://cloud.google.com/sdk/docs/install) をインストール後、`chord-transcriber` フォルダで:

```bash
gcloud run deploy chord-transcriber \
  --source . \
  --region asia-northeast1 \
  --memory 2Gi \
  --timeout 300 \
  --allow-unauthenticated
```

- メモリ 2Gi で OOM を回避、タイムアウト 300 秒で長い曲にも対応
- 使われていない間は 0 台にスケール（コールドスタートあり。無料枠内に収まりやすい）

---

## 公開にあたっての注意

- **メモリ**: 音声解析はメモリを使います。無料512MBでは長い曲で落ちることがあるため、
  短い曲で試すか、Cloud Run（2Gi）や有料プランを使ってください。
- **処理時間**: 長い曲は解析に時間がかかります（gunicorn のタイムアウトは 180 秒に設定済み）。
- **アップロード上限**: 80MB（`webapp.py` の `MAX_CONTENT_LENGTH` で変更可）。
- **プライバシー**: アップロードされた曲は一時フォルダで解析し、処理後すぐ削除します（サーバーに保存しません）。
- **著作権**: 第三者が著作権のある曲をアップロードする可能性があります。公開範囲や利用規約の掲示を検討してください。
- **悪用対策**: 公開 URL は誰でも使えます。必要なら Basic 認証などのアクセス制限を追加してください（実装は対応可能です）。
