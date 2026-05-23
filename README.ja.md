# AI Job Mediator (No API Heavy)

AI を活用した求職支援ツール。履歴書の最適化、応募書類の作成、求人評価、キャリア運用を支援します。ローカル LLM 対応と多言語ワークフローをサポートしています。

## 主な機能

- **マスターレジュメ管理**：英語・日本語・中国語の複数言語対応マスターレジュメの管理。
- **履歴書カスタマイズ**：求人票を分析し、最適化された履歴書バージョンと詳細な改善提案を生成。
- **求人評価**：求人の市場分析、適合度スコアリング、面接対策を含む総合評価。
- **自動求人スキャン**：SEEK、Doda などの求人ポータルからの定期スキャンと通知機能。
- **多言語対応**：英語・日本語・中国語の履歴書およびコミュニケーションをサポート。
- **ローカル優先設計**：Ollama などによるローカルモデル運用が可能で、外部 API 依存を最小化。

## 技術スタック

- **バックエンド**：FastAPI (Python 3.13+), LiteLLM
- **フロントエンド**：Chainlit
- **データベース**：TinyDB (JSON ファイルベース)
- **PDF 処理**：Playwright
- **LLM 統合**：Ollama / OpenRouter / OpenAI 互換エンドポイント

## クイックスタート

### 前提条件
- Python 3.13+
- uv パッケージマネージャー（推荐）

### インストール

```bash
git clone https://github.com/SydneyMCDonaldbigking/ai-job-mediator-no-api.git
cd ai-job-mediator-no-api

# バックエンド
cd backend && uv sync && cd ..

# フロントエンド
cd frontend && pip install -r requirements.txt && cd ..
```

### 起動

```bash
# バックエンド起動
bash scripts/start-backend.sh

# フロントエンド起動（別ターミナル）
bash scripts/start-frontend.sh
```

アプリケーション URL：`http://127.0.0.1:3000`

詳細な設定は `.env.example` および `backend/data/config.example.json` を参照してください。

## 設定

二層構成を採用：
1. ルート `.env` でポートとベース URL を設定。
2. `backend/data/config.json` で LLM プロバイダーとアプリケーション設定を管理。

## 対応 AI プロバイダー

- Ollama（ローカル）
- OpenRouter
- OpenAI 互換サービス（NVIDIA 含む）

## ライセンス

Apache 2.0 ライセンスのもとで公開されています。