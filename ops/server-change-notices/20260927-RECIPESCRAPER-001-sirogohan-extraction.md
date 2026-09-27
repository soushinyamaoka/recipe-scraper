# Server Change Notice

record_type: server_change
template_type: full
policy_bundle_version: 2026-09-04.1
notice_id: 20260927-RECIPESCRAPER-001
app: recipe-scraper
source_branch: main
source_commit: 84892f7（完全SHAはローカルGit履歴参照。remote未設定のためpush不可）
production_baseline_commit: null（production_deployments.yamlにrecipe-scraperのエントリなし。本アプリはproduction反映実績自体が未確認）
release_commits: b47e3d6（Git化・初回commit）, 84892f7（本notice対象の変更）
impact_level: L2
status: ready_for_review
created_by: Codex（実装）、Claude（検証・通知書修正）
production_change: required
vps_management_handoff: required
deployment_status: not_started

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
- downtime: コードの挙動自体によるdowntimeは想定されない。deploy手順の詳細はVPS管理側で確認
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

## Deploy・rollback

- deploy前提: VPS管理レビューと、別途のproduction承認
- deploy手順の変更: manifestが、文書化済みの2ファイルのみになる（`.env`除外）
- rollback方法: 承認済みのVPS手順で、直前のアプリソースとmanifestへ戻す
- rollback不能条件: 特になし

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
- このリポジトリはGitHubリモート未設定のため、remoteへの反映はできていない（push不可）。VPS管理側へ渡す場合、リモート設定または別の受け渡し方法の確認が必要。

未確認・該当なしの理由: production baselineの正本記録が存在しないため、既存baselineとの差分という形の確認ができない。

## 未解決事項

- recipe-scraperのGitHubリモートが未設定。VPS管理側への正式な提出方法（リモート経由か、別の受け渡し方法か）を確認する必要がある。
- production baselineの正本記録（`production_deployments.yaml`）にrecipe-scraperのエントリがない状態自体を、VPS管理側で確認・整備するか判断が必要。
- 実VPS上での動作確認は別途必要。

## 希望時期

VPS管理側の確認後に決定。

## VPS管理チャットへの引き継ぎ

- 引き継ぎ要否: 必要
- ユーザーへの案内: 表示済み（定型文どおり、ただしremote未設定の旨を別途申し添える）
- VPS管理チャットへ渡すローカル絶対path: `C:\work\PRG\ZZ_Other\Python\recipe_scraper_api\ops\server-change-notices\20260927-RECIPESCRAPER-001-sirogohan-extraction.md`

## Approval

- app owner: task 20260927-007で実装承認済み（ユーザー指示）。テスト検証と通知書修正はClaudeが実施。
- VPS management review: 未実施（新規提出）
- production approval: 未取得
- related task_id: 20260927-007
