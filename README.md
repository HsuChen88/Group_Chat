# Group Chat - Socket Programming
這是一個使用 **TCP/IP 協定** 實作的簡單多人即時群組聊天應用程式。基於 **Socket Programming** 技術，包含一個 Server 並允許多個 Client。所有客戶端都連接到伺服器，伺服器負責接收訊息並將其廣播（Broadcast）給所有在線的客戶端，從而實現群組聊天的功能。

## Project Goals
1.  Socket 程式設計基礎 (Socket Programming Fundamentals)
2.  TCP Handshake 與連線
3.  多執行緒處理

## User Interface
### Chat Server
<img width="493" height="576" alt="server" src="https://github.com/user-attachments/assets/bc28b786-7ca9-4357-8d6c-b4377f8a6f1a" />

### Multiple Clients
<img width="937" height="353" alt="client" src="https://github.com/user-attachments/assets/400df6a2-ca06-48cd-a304-f3ea8380829b" />


## Quick Start
為了方便快速部署和測試，我們提供兩個 PowerShell 自動化腳本：`start_server.ps1` 和 `start_client.ps1`。

> ### Prerequisites
> 1. Python 3.10 or newer
> 2. `pip install -r requirements.txt`
> 3. 允許執行 `*.ps1`

### 1. 啟動伺服器 (Server)
您可以開啟終端機視窗，並執行`server.py`，或在終端機中執行以下 PowerShell 腳本。

```bash
# 確保您有執行腳本的權限
# Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

.\start_server.ps1
```

### 2. 啟動客戶端 (Client)
伺服器啟動後，您可以開啟**多個**終端機視窗，並執行`client.py`，或使用自動化腳本一次啟動三個客戶端。

```bash
# 一次啟動三個客戶端
.\start_3_clients.ps1
```
