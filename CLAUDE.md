# レシピ抽出API

## ⚠ 2026-09-16 Git化時点の注記

- 本プロジェクトは2026-09-16に`git init`し、他3つのAPIリポ（coop-api / recipe-ai-api / recipe-search-api）と同様のGit管理・`work/ai_handoff`運用下に置いた。それ以前はGit管理外だった。
- 下記「サーバー構成・ポート番号」「ビルド・デプロイ手順」節は、Git化前から存在する記述であり、**HTTPS入口化（`https://recipe-scraper.homehub-tools.dedyn.io`）等のVPS安全化を反映していない可能性がある**。他3アプリのCLAUDE.mdには「VPS安全化後の現行仕様」の注記があるが、本アプリはこの整理が未実施。デプロイ・VPS接続作業の前に現行構成を要確認。
- ログはVPS共通の構造化ログ規約（1行1JSON、stdout/stderr）に未対応（`ops/runtime-contract.yaml`参照）。

## プロジェクト概要

指定URLのレシピページからレシピ名・材料・作り方を抽出して返却するサーバーサイドAPI。
「今晩なに食べる？」アプリ（Expo/React Native）のバックエンドとして動作する。

主な機能:
- レシピページURLからレシピ名・材料・作り方を抽出
  - 一般サイト: JSON-LD (`@type: Recipe`) から取得
  - YouTube: YouTube Data API v3 で説明文を取得し、正規表現でパース
- タイトルのフォールバック: JSON-LD → og:title → `<title>` タグ
- ドメイン名（ソースサイト名）の抽出
- CORS対応（全オリジン許可）

## ディレクトリ構成と各ファイルの役割

```
recipe_scraper_api/
├── recipe_scraper_api_app.py   # FastAPIサーバー本体（全エンドポイント定義・スクレイピングロジック）
├── requirements.txt            # Pythonパッケージ依存
├── .env                        # 環境変数（Git管理外）
├── .env.example                # .envのテンプレート
├── deploy-files.txt            # デプロイ対象ファイル一覧
└── DEPLOY_recipe_scraper_api.md # WinSCP+TeraTerm用デプロイ手順書
```

### 主要ファイルの役割

| ファイル | 役割 |
|---------|------|
| `recipe_scraper_api_app.py` | 全APIエンドポイント、JSON-LD抽出ロジック、YouTube説明文パーサー |

## 使用技術・ライブラリ

| パッケージ | 用途 |
|-----------|------|
| FastAPI | Webフレームワーク |
| Uvicorn | ASGIサーバー |
| httpx | 非同期HTTPクライアント（レシピページ取得・YouTube API呼び出し） |
| BeautifulSoup4 | HTMLパース |
| python-dotenv | 環境変数管理 |

- Python 3.10以上推奨（`str | None` 型ヒント使用）
- 標準ライブラリ: `json`, `os`, `re`, `urllib.parse`

## サーバー構成・ポート番号

### VPS環境
- さくらVPS（大阪）: `<VPS_IP>`（実IPはデプロイスクリプトを参照）
- OS: Ubuntu 22.04 LTS
- 実行ユーザー: `deploy`

### ポート構成

| ポート | サービス | パス | 説明 |
|--------|---------|------|------|
| 8001 | AIレシピ生成API | `/home/ubuntu/recipe_api_app.py` | Claude/GPTによるレシピ生成 |
| 8002 | Webレシピ検索API | `/home/ubuntu/recipe-search-api/` | Webスクレイピングによるレシピ検索 |
| 8003 | COOP連携API | `/home/ubuntu/coop_api/` | COOPメール解析・献立提案 |
| 8004 | **レシピ抽出API** | `/opt/apps/recipe_scraper_api/` | 本プロジェクト |

### APIエンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/recipe/extract?url=<URL>` | 指定URLからレシピ名・材料・作り方を抽出 |
| GET | `/health` | ヘルスチェック |

YouTube URLを渡すと自動的に YouTube Data API v3 を使用する（URL判定は自動）。

### レスポンス例

```json
// 正常（材料・作り方あり）
{
  "url": "https://...",
  "title": "鶏のから揚げ",
  "source": "cookpad.com",
  "ingredients": ["鶏もも肉 300g", "醤油 大さじ2"],
  "instructions": ["鶏肉を一口大に切る", "調味料を混ぜて漬け込む"]
}

// 正常（材料・作り方なし ＝ JSON-LD 非対応サイト）
{
  "url": "https://...",
  "title": "鶏のから揚げ",
  "source": "example.com",
  "ingredients": null,
  "instructions": null
}

// エラー
{"url": "https://...", "title": null, "source": "cookpad.com", "ingredients": null, "instructions": null, "error": "HTTP 404"}
```

### 認証
- 認証なし（全エンドポイント認証不要）

## ビルド・デプロイ手順

### ローカル開発
```bash
# 仮想環境の作成・有効化
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate         # Windows

# パッケージインストール
pip install -r requirements.txt

# サーバー起動
python recipe_scraper_api_app.py
```

### VPSへのデプロイ
デプロイ対象は `deploy-files.txt` に記載の2ファイル:
```
recipe_scraper_api_app.py
requirements.txt
```

```bash
# 1. WinSCP等でファイルを /opt/apps/recipe_scraper_api/ にアップロード

# 2. SSH接続後、パッケージ更新（変更がある場合）
sudo -u deploy bash
cd /opt/apps/recipe_scraper_api
source venv/bin/activate
pip install -r requirements.txt
deactivate
exit

# 3. サービス再起動
sudo systemctl restart recipe-scraper-api

# 4. 動作確認
sudo systemctl status recipe-scraper-api
curl "http://localhost:8004/health"
```

### 初回セットアップ
```bash
# VPS上でdeployユーザーとして実行
sudo -u deploy bash
cd /opt/apps/recipe_scraper_api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
exit

# systemdサービス登録
sudo systemctl daemon-reload
sudo systemctl enable recipe-scraper-api
sudo systemctl start recipe-scraper-api
```

systemdサービス定義ファイル（`/etc/systemd/system/recipe-scraper-api.service`）:
```ini
[Unit]
Description=Recipe Scraper API (Port 8004)
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=/opt/apps/recipe_scraper_api
ExecStart=/opt/apps/recipe_scraper_api/venv/bin/uvicorn recipe_scraper_api_app:app --host 0.0.0.0 --port 8004
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## 開発時の注意事項

### .envファイル
`.env.example` をコピーして `.env` を作成する。**`.env` はGit管理外**。
```
YOUTUBE_API_KEY=<YouTube Data API v3 のAPIキー>
```

### URL判定ロジック
`extract_video_id()` でYouTube URLかどうかを判定し、自動的に処理を切り替える。
- YouTube URL形式: `youtube.com/watch?v=`, `youtu.be/`, `youtube.com/shorts/`, `youtube.com/embed/`

### YouTube説明文パーサーの仕様
`parse_recipe_from_description()` が説明文を行単位で解析する。

対応しているセクションヘッダー形式:
- `【材料】` `【材料（2人分）】` `◆材料` `▼材料` `材料：` `材料（2人分）`
- `【作り方】` `◆作り方` `▼手順` `作り方：` `手順`

ヘッダー検出後、次のセクションヘッダーが出現するまでの行を収集する。行頭の `・` `-` `1.` `①` 等は除去して返す。

**制限**: 説明文の書式はチャンネルによって異なるため、ヘッダーが未対応の形式の場合は `null` を返す。

### タイトル抽出の優先順位（一般Webサイト）
1. JSON-LD (`@type: Recipe` の `name`)
2. OGP (`og:title`)
3. `<title>` タグ

### JSON-LD解析の注意点
- `@type` が文字列の場合とリストの場合の両方に対応済み
- `@graph` 内のネストされたRecipeオブジェクトも探索する
- `recipeInstructions` は文字列・文字列リスト・HowToStep・HowToSection の4形式に対応

### HTTPクライアント設定
- タイムアウト: 15秒（Webページ）/ 10秒（YouTube API）
- リダイレクト自動追従: 有効
- User-Agent: Chrome 120 を偽装（サイトによるブロック回避）

## よく使うコマンド

### ローカル開発
```bash
# サーバー起動
python recipe_scraper_api_app.py
```

### VPS管理
```bash
# サービス状態確認
sudo systemctl status recipe-scraper-api

# サービス再起動
sudo systemctl restart recipe-scraper-api

# ログ確認
sudo journalctl -u recipe-scraper-api -f
```

### API動作確認
```bash
export VPS_IP=<VPS_IPを設定>

# ヘルスチェック
curl "http://$VPS_IP:8004/health"

# レシピ名抽出
curl "http://$VPS_IP:8004/api/recipe/extract?url=https://cookpad.com/recipe/1234567"

# ローカルで確認
curl "http://localhost:8004/api/recipe/extract?url=https://cookpad.com/recipe/1234567"
```

## コミットルール

- コミットは「コミットして」と指示があった時のみ行う
- コミットの前に必ず変更内容に以下の機密情報が含まれていないか確認する
  - APIキー・トークン
  - パスワード
  - 個人情報（メールアドレス・電話番号等）
  - サーバーのIPアドレス・接続情報
  - .envファイルの内容
- 機密情報が含まれる場合は作業を中断してその旨を報告する
- 機密情報が含まれない場合のみコミットを実行する
- コミットメッセージは以下の形式で日本語で書く
  - バグ修正: `fix: 内容`
  - 新機能: `feat: 内容`
  - リファクタリング: `refactor: 内容`
  - その他: `chore: 内容`
- **push は明示指示があるときだけ行う。** 「pushして」と明示されていない場合は commit までで止め、push していないことを報告する。
- force push、履歴改変、既存変更の revert は行わない。
