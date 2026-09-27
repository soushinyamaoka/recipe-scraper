# Server Change Notice

record_type: server_change
template_type: full
policy_bundle_version: 2026-09-04.1
notice_id: 20260927-RECIPESCRAPER-001
app: recipe-scraper
source_branch: main
source_commit: 84892f7f11f7cb9273154fcc0f499307b78a3d7e
production_baseline_commit: null
release_commits: b47e3d6d4a5778cc96cb791209a0ea7214e2808c, 84892f7f11f7cb9273154fcc0f499307b78a3d7e, 54c63e96730ed9c3f4361b22e4e09e39814bae97, 16e86ae500a4cdfe92279f8b63dab06edc0e252d, 1641d462024dd63e4c7d8b66d772583a20ae0af7
remote: https://github.com/soushinyamaoka/recipe-scraper.git
impact_level: L2
status: ready_for_review
created_by: Codex（実装）、Claude（検証・通知書修正）
production_change: required
vps_management_handoff: required
deployment_status: not_started

## commit・remoteの補足（RS-001-B01対応）

- `source_commit`は実装commit（サイト別抽出・manifest修正）。
- `production_baseline_commit`が`null`なのは、`production_deployments.yaml`にrecipe-scraperのエントリがなく、これまでのproduction反映実績が正本記録として確認できないため。
- `release_commits`は、Git化時の初回commitから本notice文書のcommitまでの全件。
- `remote`は2026-09-27にユーザーが新規作成したGitHubリポジトリ。local HEAD・cached `origin/main`・実remote `refs/heads/main`が一致していることを、提出のたびに確認している（直近の一致は「提出前セルフチェック」参照）。

## 変更概要

白ごはん.com（`sirogohan.com`）向けに、ドメイン別のHTML抽出フォールバックを追加し、材料・作り方を取得できるようにする。あわせて`deploy-files.txt`から`.env`を除外する。

## 変更理由

このサイトは現行のJSON-LD抽出では材料・作り方を取得できない（構造化データを持たないため）。また配布manifestに`.env`が含まれており、ドキュメント化された「2ファイル」の配布方針、および秘密情報ファイルの配布契約と矛盾していた。

## server_impact判定

server_impact: notify

判定理由: production反映後、このドメインに対するAPI応答へ材料・作り方が追加される。port、bind、URL、health endpoint、起動command、依存、環境変数、DB、job、ログ、監視は変更なし。

## 現在と変更後

| 項目 | 現在 | 変更後 |
|---|---|---|
| レシピ抽出応答 | JSON-LDのfield、またはタイトルのみ | 既存のJSON-LD経路は変更なし。sirogohan.comはJSON-LDでrecipe情報が取れない場合にサイト別フォールバックを使う |
| 配布manifest | アプリ本体・requirements・`.env` | アプリ本体・requirementsのみ。`.env`は明示的に除外 |

## 影響対象

- service/container: 既存のrecipe-scraper APIサービス。service定義変更なし
- URL/port/health: 変更なし
- cron/timer/worker: 変更なし
- dependency: production依存の変更なし
- data/DB/volume: 変更なし
- log/monitoring: 変更なし

## production変更

- 必要性: あり
- 想定作業: VPS管理レビューと、別途承認されたアプリ変更のdeploy。本task・本検証ではproductionへの接続・変更は行っていない
- downtime: `pip install`とservice再起動の間、短い停止が起こり得る（下記「Deploy・rollback」参照）
- maintenance window: 未定。利用者影響は想定されない

## 利用者への影響

- user_maintenance_impact: none
- 対象利用者・機能: sirogohan.comのURLに対するレシピ抽出で、材料・作り方が返るようになる
- 通知方法: 利用者向けメンテナンス通知は想定していない

## env・secret contract

- 変更: なし（manifestから秘密情報を含む`.env`を除外しただけ）
- 変数名・secret種類のみ: 変更なし
- provisioning/rotation: 変更なし

## Data・migration・backup

- schema/format変更: なし
- migration: なし
- backup対象: なし
- restore確認: 該当なし
- backward compatibility: JSON-LDで材料か作り方のどちらかが取得できるサイトの既存経路は変更しない

## Deploy・rollback（RS-001-B02対応）

- **実際のdeploy経路**: `deploy-recipe-scraper-api.bat`（`C:\work\PRG\Sakura\Dev\deploy\recipe-api\`配下）は`LOCAL_DIR=C:\work\PRG\Python\recipe_scraper_api`を指しているが、このパスは存在しない（現在のリポジトリは`C:\work\PRG\ZZ_Other\Python\recipe_scraper_api`）。**この`.bat`はそのままでは使えない。** 本noticeではこのwrapperの修正は行わない（別途のrelease計画・承認事項とする）。
  - 使える経路は、共通`deploy.bat recipe-scraper-api <正しいLOCAL_DIR>`を直接実行する方法。これは`deploy-files.txt`記載の2ファイル（`recipe_scraper_api_app.py`、`requirements.txt`）をVPS1へscp転送した後、sshでVPS1側の`/opt/apps/deploy.sh recipe-scraper-api`を実行する。このscriptがvenvへ`pip install -r requirements.txt`を行い、`recipe-scraper-api`のsystemd serviceを再起動する。
  - `.env`はこの経路で転送されない（`deploy-files.txt`から除外済み、既存VPS上の`.env`はそのまま）。
- deploy前提: VPS管理レビュー受理、上記経路の実行版計画の確定、別途のproduction承認。
- deploy手順:
  1. 反映前に、VPS1上の現行`recipe_scraper_api_app.py`・`requirements.txt`のSHA-256を記録する（レビュー時点の値: `recipe_scraper_api_app.py` = `34d675804bca548d7d1284f1c06ba76eb2fd38af25ea514d276da72ed51819c6`、`requirements.txt` = `9486827792744f1d378a7a084aa6f25eec53f2415f94b7552df95e713cf24eeb`。実施時に再確認する）。
  2. `deploy.bat recipe-scraper-api <正しいLOCAL_DIR>`で2ファイルを転送し、`/opt/apps/deploy.sh recipe-scraper-api`を実行する。
  3. `pip install`とservice再起動が完了するまでの間、短い停止が起こり得る。
  4. 反映後、`/health`（内部・公開の両方）がHTTP 200を返すことを確認する。
  5. 実際の`sirogohan.com`のURLで`/api/recipe/extract`を呼び、材料・作り方が返ることを確認する（canary）。
- rollback方法: 手順1で記録したhashに対応する旧2ファイルを保存しておき、それらを同じ`deploy.bat`経路で再度転送・`/opt/apps/deploy.sh recipe-scraper-api`を再実行して依存を再適用・service再起動する。再起動後、`/health`がHTTP 200を返すことを確認する。
- rollback不能条件: 反映前に旧2ファイルを保存していない場合、hashの記録だけでは内容そのものを復元できない。

## Health・テスト

- health contract変更: None
- 実施テスト（Claudeが検証環境を用意し実施、2026-09-27）:
  - `python -m pytest`: 5件pass（材料グループ表記、note-text/動画blockの除外、JSON-LD優先、未対応ドメインのフォールバック、空構造時にエラーにならないこと）。
  - アプリ単体import（`.env`読込を回避した状態）: 成功。
  - `git diff --check`: pass。
  - いずれも実サイト・実データへは接続していない（合成HTMLのみ使用）。
- 未実施テスト: 実VPS上での動作確認、実際の`sirogohan.com`ページに対する疎通確認は行っていない（production接続を伴うため）。

## Log・監視

- log量/形式/保存先変更: None
- 新しいalert条件: None
- secret/個人情報対策: `.env`の値は読んでいない・コピーしていない。配布manifestから`.env`を除外した

## 提出前セルフチェック

- production baseline: `production_deployments.yaml`にrecipe-scraperのエントリがなく、本アプリがこれまでにVPS管理側の管理下でproduction反映された記録が確認できない。この点はVPS管理側での確認が必要。
- テストはClaudeが検証環境を用意して実施し、上記「Health・テスト」に記載のとおりpass。
- リモート: 2026-09-27にユーザーがGitHubリポジトリ（`https://github.com/soushinyamaoka/recipe-scraper.git`）を作成し、origin設定・pushを実施した。本commit時点のlocal HEADをpush後、local HEAD = origin/main が一致することを確認する（VPS管理側のread-only preflightでの実remote照合はレビュー側で実施）。

未確認・該当なしの理由: production baselineの正本記録が存在しないため、既存baselineとの差分という形の確認ができない。

## 未解決事項

- production baselineの正本記録（`production_deployments.yaml`）にrecipe-scraperのエントリがない状態自体を、VPS管理側で確認・整備するか判断が必要。
- 実VPS上での動作確認は別途必要。

## 希望時期

VPS管理側の確認後に決定。

## VPS管理チャットへの引き継ぎ

- 引き継ぎ要否: 必要
- ユーザーへの案内: 表示済み（定型文どおり）
- VPS管理チャットへ渡すローカル絶対path: `C:\work\PRG\ZZ_Other\Python\recipe_scraper_api\ops\server-change-notices\20260927-RECIPESCRAPER-001-sirogohan-extraction.md`

## Approval

- app owner: task 20260927-007で実装承認済み（ユーザー指示）。テスト検証と通知書修正はClaudeが実施。
- VPS management review: 初回`blocked`（RS-001-B01・B02）。本更新で両点に対応し、再審査依頼として提出
- production approval: 未取得
- related task_id: 20260927-007
