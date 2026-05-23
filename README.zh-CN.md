# AI 求职中介 (No API Heavy)

基于 AI 的求职助手，帮助用户优化简历、生成定制化申请材料、评估职位机会并管理职业流程。支持本地 LLM 部署和多语言工作流。

## 主要功能

- **主简历管理**：支持上传和管理多语言主简历（英文、日文、中文）。
- **简历定制**：分析职位描述，生成优化后的简历版本并提供详细修改建议。
- **职位机会评估**：对职位进行全面分析，包括市场数据、匹配度评分和面试准备指导。
- **自动职位扫描**：支持 SEEK、Doda 等平台的定时扫描及通知功能。
- **多语言支持**：完整支持英文、日文、中文简历和工作流。
- **本地优先设计**：可使用 Ollama 等本地模型，减少对外部 API 的依赖。

## 技术栈

- **后端**：FastAPI (Python 3.13+), LiteLLM
- **前端**：Chainlit
- **数据库**：TinyDB (JSON 文件存储)
- **PDF 处理**：Playwright
- **LLM 集成**：Ollama / OpenRouter / OpenAI 兼容接口

## 快速开始

### 环境要求
- Python 3.13+
- uv 包管理器（推荐）

### 安装步骤

```bash
git clone https://github.com/SydneyMCDonaldbigking/ai-job-mediator-no-api.git
cd ai-job-mediator-no-api

# 后端
cd backend && uv sync && cd ..

# 前端
cd frontend && pip install -r requirements.txt && cd ..
```

### 启动应用

```bash
# 启动后端
bash scripts/start-backend.sh

# 启动前端（新终端）
bash scripts/start-frontend.sh
```

应用地址：`http://127.0.0.1:3000`

详细配置请参考 `.env.example` 和 `backend/data/config.example.json`。

## 配置说明

系统采用双层配置：
1. 根目录 `.env` 文件配置服务端口和基础 URL。
2. `backend/data/config.json` 配置 LLM 提供商、回退链及应用设置。

## 支持的 AI 提供商

- Ollama（本地）
- OpenRouter
- OpenAI 兼容服务（含 NVIDIA）

## 许可证

本项目基于 Apache 2.0 许可证开源。