# Discord 副本招募 Bot

目前是本機測試用 MVP，使用 Python 與 `discord.py`。

## 功能

- `/raid create` 建立副本招募
- 副本名稱、時間、人數（目前固定 6 人）
- 按鈕加入、退出、查看名單、關閉招募
- 防止重複加入
- 滿 6 人時通知
- 隊長可以標記指定成員
- 同一個頻道可以同時存在多個招募

## 修改職業選單

編輯 `config.json` 的 `job_families` 清單即可，不需要修改 `bot.py`。加入隊伍時會先選職業系，再選該職業系內的職業。

使用 `/raid_invite` 時填入招募名稱即可；同一個頻道不允許建立同名的進行中招募。

## 本機啟動

1. 建立虛擬環境並安裝套件：

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. 複製 `.env.example` 為 `.env`，填入 Bot Token。

3. 啟動：

   ```powershell
   py bot.py
   ```

需要在 Discord Developer Portal 開啟 Bot，並使用包含 `bot` 與 `applications.commands` scope 的邀請連結加入測試伺服器。

