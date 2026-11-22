# EPDK Legislation Assistant (RAG)

A fully local question-answering assistant for the Turkish electricity market legislation published by EPDK (Energy Market Regulatory Authority). It answers questions in Turkish **only from the regulatory documents** and lists its sources with dates, links and a short quotation from the original text.

Developed during my summer internship at KEPSAŞ (Kayseri Elektrik Perakende Satış A.Ş.), 2026. It started from a prototype whose document collector returned zero documents.

## How it works

```
EPDK website ─► download bot ─► text extraction ─► chunking ─► embeddings ─► ChromaDB
                (2,715 docs)     (6 formats)                    (e5-large)    (~40,000 chunks)

Question ─► embedding ─► vector search (20 candidates) ─► reranker (top 5) ─► local LLM ─► answer + sources
```

| Step | Technology |
|---|---|
| Data collection | Requests, BeautifulSoup (reproduces the site's hidden list request, 464 category nodes) |
| Text extraction | pdfplumber, python-docx, openpyxl, xlrd, ZIP; old `.doc` files via Microsoft Word COM (macros disabled) |
| Embeddings | `intfloat/multilingual-e5-large` (GPU if available) |
| Vector database | ChromaDB (persistent) |
| Reranker | `BAAI/bge-reranker-v2-m3` cross-encoder (GPU, falls back to CPU) |
| Language model | `qwen2.5:7b` via Ollama, running locally |

No question or document leaves the computer.

## Quality measures

- **Newest version first** – the archive contains many historical versions of the same regulation; near-duplicate chunks are filtered so only the newest one is kept. The date is read from three fields (decision date, Official Gazette date, title).
- **Tables and numbers** – table rows keep their description next to their value and chunks break at line ends, so a figure like `2.161` is not cut into `61`.
- **Grounded answers** – the model is instructed to answer only from the retrieved passages, not to present repealed (*Mülga*) provisions as valid, and to cite sources as `[1]`, `[2]`.
- **Verifiable** – under each answer the sources are listed with a quotation from the original document, so a number can be checked.
- **Model choice** – two local models were compared on exactly the same retrieved context; Qwen2.5-7B answered 4/4 test questions correctly.

## Files

| File | Purpose |
|---|---|
| `mevzuat_bot.py` | Downloads all documents and their metadata into `data/` and a CSV dataset (resumable, with retries) |
| `doc_converter.py` | Converts old binary `.doc` files to text with Microsoft Word (Windows only) |
| `document_processor.py` | Extracts text from PDF, DOC, DOCX, XLS, XLSX and ZIP; splits it into chunks |
| `embeddings.py` | e5 embeddings with the required `query:` / `passage:` prefixes |
| `vector_store.py` | ChromaDB storage and search, keeps the newest of near-duplicate chunks |
| `index.py` | Indexes the whole archive; progress is saved so an interrupted run can continue |
| `reranker.py` | Cross-encoder reranking |
| `llm.py` | Prompt and answer generation with Ollama |
| `main.py` | Interactive command-line assistant |
| `config.py` | Model names, chunk size, database path |
| `scraper.py` | Early exploration script for the EPDK page structure |

## Setup

Requirements: Python 3.11, [Ollama](https://ollama.com), an NVIDIA GPU is recommended. Converting `.doc` files requires Windows and Microsoft Word.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
ollama pull qwen2.5:7b
```

For GPU support, install the CUDA build of PyTorch from [pytorch.org](https://pytorch.org/get-started/locally/).

## Usage

```bash
python mevzuat_bot.py     # 1. download documents into data/
python doc_converter.py   # 2. convert .doc files to text (Windows + Word)
python index.py           # 3. build the vector database in chroma_db/
python main.py            # 4. ask questions
```

Example:

```
Soru: 6446 sayılı Elektrik Piyasası Kanunu'nun amacı nedir?
```

The downloaded documents (`data/`) and the index (`chroma_db/`) are not part of the repository; they are large and can be regenerated with the steps above.

## Limitations

- 272 scanned PDFs without a text layer (mostly tariff tables) are skipped on purpose, because an OCR error in a number would be worse than no answer.
- The assistant is a command-line tool and the index is not updated automatically.
- Answers come from a 7B local model; always check figures against the quoted source.

## Related

- [TTS_Staj](https://github.com/alibayraktar00/TTS_Staj) – the first internship project, an IT request tracking system

## Author

Ali Bayraktar – Abdullah Gül University, Computer Engineering
