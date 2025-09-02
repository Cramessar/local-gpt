# 💻 Local GPT

Local-first AI assistant with:

- **Chat UI** (Next.js + React)
- **Toolserver** (FastAPI + Python)
- **Resource Monitor** (CPU, GPU, Memory via psutil + NVML)
- **Docs & RAG** (upload PDFs/DOCs/CSVs and ask questions)
- **Dockerized** for one-line setup

---

## 🚀 Features
- 🔹 Chat with local LLMs via **vLLM** or **Ollama**
- 🔹 Real-time system monitoring (CPU, RAM, GPU)
- 🔹 Document upload & indexing (PDF, DOCX, CSV, XLSX)
- 🔹 Retrieval-Augmented Generation (RAG) on your own files
- 🔹 Easy Docker setup (`docker compose up`)

---

## 📂 Project Structure
```
local-gpt/
├── frontend/            # Next.js chat UI
│   ├── components/      # ResourcePanel, DocTools, etc.
│   ├── pages/           # Chat + RAG UI
│   └── public/
├── toolserver/          # FastAPI backend
│   ├── app.py           # FastAPI entry
│   ├── rag_routes.py    # Upload + RAG endpoints
│   ├── vectorstore.py   # ChromaDB integration
│   ├── file_extract.py  # Extract text from PDFs, DOCX, XLSX
│   └── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🐳 Setup with Docker
```bash
# Build & start
docker compose up --build
```

Services:
- **Frontend** → http://localhost:3000  
- **Toolserver** → http://localhost:8000  

---

## 🧑‍💻 Local Dev (without Docker)

### Backend
```bash
cd toolserver
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 📚 RAG (Docs & Uploads)
1. Upload PDFs/DOCX/CSVs/XLSX in the **sidebar**
2. They get chunked + stored in **ChromaDB**
3. Ask questions in the chat with **“Use docs (RAG)”** enabled

---

## ⚡ Requirements
- Python 3.11
- Node 18+
- Docker Desktop (if using Docker)
- (Optional) NVIDIA GPU + drivers for GPU monitoring

---

## 🛠️ Tech Stack
- **Frontend:** Next.js (React + TypeScript)
- **Backend:** FastAPI (Python 3.11)
- **DB:** ChromaDB (vector store)
- **RAG:** `pdfplumber`, `python-docx`, `pandas`, `PyMuPDF`
- **Monitoring:** `psutil`, `pynvml`

---

## 📝 Roadmap
- [ ] Add authentication for multi-user access  
- [ ] Support more file formats (PowerPoint, Markdown)  
- [ ] Improve GPU/CPU charts  
- [ ] Plug in custom LLMs via API  

---

## 🤝 Contributing
PRs and issues welcome!  
Please open an issue before large changes.

---

## 📄 License
MIT — free to use, modify, and share.
