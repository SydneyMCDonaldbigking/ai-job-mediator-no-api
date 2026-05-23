# AI Job Mediator (No API Heavy)

AI-powered job application assistant that helps users optimize resumes, generate tailored content, evaluate job opportunities, and manage career operations. Supports local LLM deployment and multi-language workflows.

## Key Features

- **Master Resume Management**: Upload and maintain primary resumes in multiple languages (English, Japanese, Chinese).
- **Resume Tailoring**: Analyze job descriptions and generate optimized resume versions with detailed suggestions.
- **Job Opportunity Evaluation**: Comprehensive assessment of job postings including market analysis, fit scoring, and interview preparation guidance.
- **Automated Job Scanning**: Scheduled scanning from portals such as SEEK and Doda, with notification support.
- **Multi-language Support**: Full workflow support for English, Japanese, and Chinese resumes and communications.
- **Local-First Design**: Works with local models via Ollama or compatible providers with minimal external API dependency.

## Technology Stack

- **Backend**: FastAPI (Python 3.13+), LiteLLM
- **Frontend**: Chainlit
- **Database**: TinyDB (JSON-based)
- **PDF Processing**: Playwright
- **LLM Integration**: Ollama / OpenRouter / OpenAI-compatible endpoints

## Quick Start

### Prerequisites
- Python 3.13+
- uv package manager (recommended)

### Installation

```bash
# Clone the repository
git clone https://github.com/SydneyMCDonaldbigking/ai-job-mediator-no-api.git
cd ai-job-mediator-no-api

# Backend setup
cd backend
uv sync
cd ..

# Frontend setup
cd frontend
pip install -r requirements.txt
cd ..
```

### Running the Application

```bash
# Start backend
bash scripts/start-backend.sh

# Start frontend (in new terminal)
bash scripts/start-frontend.sh
```

Access the application at `http://127.0.0.1:3000`.

For detailed configuration, see `.env.example` and `backend/data/config.example.json`.

## Configuration

The system uses two configuration layers:
1. Root `.env` for service ports and base URLs.
2. `backend/data/config.json` for LLM providers, fallback chains, and application settings.

## Supported AI Providers

- Ollama (local)
- OpenRouter
- OpenAI-compatible services (including NVIDIA)

## License

This project is licensed under the Apache 2.0 License.
