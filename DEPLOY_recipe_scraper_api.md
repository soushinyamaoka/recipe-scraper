# デプロイ手順（recipe_scraper_api / Port 8004）

## 1. ファイル配置（WinSCP）

ローカルの以下2ファイルをVPSにアップロード：

```
/opt/apps/recipe_scraper_api/recipe_scraper_api_app.py
/opt/apps/recipe_scraper_api/requirements.txt
```

## 2. Python仮想環境の作成（TeraTerm）

```bash
sudo -u deploy bash
cd /opt/apps/recipe-scraper-api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
exit
```

## 3. 動作確認（手動起動）

```bash
sudo -u deploy bash
cd /opt/apps/recipe-scraper-api
source venv/bin/activate
python recipe_scraper_api_app.py
```

別ターミナルから確認：

```bash
curl "http://localhost:8004/health"
```

`{"status":"ok"}` が返ればOK。`Ctrl+C` で停止。

## 4. systemdサービス登録

```bash
sudo nano /etc/systemd/system/recipe-scraper-api.service
```

以下を貼り付け（`Ctrl+O` → `Enter` で保存、`Ctrl+X` で終了）：

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

## 5. サービス起動・有効化

```bash
sudo systemctl daemon-reload
sudo systemctl enable recipe-scraper-api
sudo systemctl start recipe-scraper-api
sudo systemctl status recipe-scraper-api
```

`Active: active (running)` になっていればOK。

## 6. ログ確認

標準出力はjournalctlで確認：

```bash
sudo journalctl -u recipe-scraper-api -f
```

ファイルログが必要な場合は既存APIと同様に `/var/log/apps/` へ追加。

## 7. 最終確認

```bash
curl "http://localhost:8004/api/recipe/extract?url=https://cookpad.com/recipe/1234567"
```

`title` が返ってくれば完了。
