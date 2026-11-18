# Guideline Gateway (Offline-First Guideline RAG)

**Guideline Gateway** is a domain-agnostic, offline-first question-answering system built on Retrieval-Augmented Generation (RAG) and Small Language Models (SLM). It runs **100% offline** on **minimal hardware** (CPU-only laptop or mini-PC with 4–8 GB RAM).

Users ask questions in natural language, and the system answers strictly based on the loaded guideline document, always accompanying claims with verifiable article/clause citations.

---

> [!IMPORTANT]
> ### ⚽ Reference Use Case: Football Laws of the Game
> **The football rules (*Laws of the Game*, IFAB/FIFA) serve as the reference use case and end-to-end test case for this platform.**
> 
> * **Example / Test Case Only:** Football rules were selected as the initial benchmark because they are dense, hierarchical (17 Laws), full of situational exceptions, and easy for domain practitioners to verify.
> * **Domain-Agnostic Core:** The core engine (`engine/`, retrieval, generation, guardrails, and interfaces) contains **no domain-specific logic**. 
> * **Pluggable Knowledge Packs (`.kpack`):** All domain-specific assets—source documents, glossaries, topic routers, prompts, and evaluation sets—live inside a Knowledge Pack. Loading a new domain (e.g., safety SOPs, hospital protocols, legal regulations) requires **zero changes to the core engine code**.

---

## Key Features

* **100% Offline by Construction:** Zero runtime network calls. Models and indexes run entirely on local hardware.
* **Resource-Frugal Architecture:**
  * **SLM Runtime:** Local quantized GGUF models (`llama.cpp` via `llama-cpp-python`, targeting Qwen2.5 1.5B/3B or Llama-3.2 1B/3B).
  * **Ultra-Fast Hybrid Search:** Standard SQLite FTS5 (BM25) combined with NumPy in-memory vector search (< 1 ms latency for ~1,000 chunks, ~1.5 MB RAM footprint). No heavy external vector databases or native C-extensions required.
* **Grounded Answers & Citations:** Answers are generated strictly from retrieved evidence. Every claim includes a verifiable citation tag `[C#]`.
* **Abstain Guardrails:** Automatically declines or abstains when evidence is insufficient or out of scope instead of hallucinating.
* **Bilingual Support:** Configured for Indonesian (ID) and English (EN) with domain glossary expansion.
* **Multi-Turn Conversations:** Supports conversational follow-up questions within a session with context sliding windows.
* **Interfaces:**
  * Modern, responsive **Web Chat UI** built with **Svelte + Tailwind CSS** (served statically by FastAPI).
  * Local **REST API** (`127.0.0.1:8000`).
  * Admin and user **CLI**.

---

## High-Level Architecture

```
BUILD-TIME (Developer / Admin Machine)          RUN-TIME (Offline User Device)
─────────────────────────────────────          ───────────────────────────────
Source PDF (e.g. Laws of the Game)              Client: Svelte Web UI / CLI
   │                                                   │
   ▼                                                   ▼
[1] Two-Stage Parser (PyMuPDF -> Markdown)      [A] FastAPI Local Server (127.0.0.1)
   │                                                   │
   ▼                                                   ▼
[2] Structure-Aware Chunker                     [B] Query Processor
   │  (Law > Section > Clause)                      │  (Multi-turn, Glossary ID↔EN, Scope)
   ▼                                                   ▼
[3] Batch Embedding (multilingual-e5-small)     [C] Hybrid Retriever
   │                                                │  (BM25 FTS5 + NumPy Dot Product -> RRF)
   ▼                                                   ▼
[4] SQLite Builder (chunks + BLOB + FTS5)       [D] Context Builder (Token Budgeting)
   │                                                   ▼
   ▼                                            [E] Local SLM (llama.cpp GGUF Q4)
[5] kpack Packager -> football-laws.kpack              ▼
                                                [F] Guardrails (Citation check & Abstain)
                                                       ▼
                                                Cited Response with Clause References
```

---

## Knowledge Pack (`.kpack`) Structure

Domain knowledge is packaged into a self-contained archive:

```
football-laws-2024-25.kpack   (zip)
├── manifest.json        # ID, edition, hash, required model specs & dims
├── pack.yaml            # Domain config, thresholds, answer format
├── knowledge.sqlite     # Chunks table, FTS5 index, raw embedding BLOBs
├── glossary.yaml        # Domain ID↔EN terminology mapping
├── router.yaml          # Topic-to-Law routing rules
├── prompts/             # Domain-specific system & answer prompts
├── eval/golden.jsonl    # Reference questions for regression testing
└── SOURCES.md           # Source attribution & licensing
```

> **Note on Model Separation:** Large model binaries (GGUF LLM weights and ONNX embedding models) are **not** bundled in `.kpack`. They are managed in the local host runtime (`models/`), keeping `.kpack` files extremely lightweight (a few megabytes).

---

## MVP Scope & Prioritization

* **🔴 P0 (Core MVP):** End-to-end offline pipeline: PDF parsing ➔ Intermediate Markdown ➔ SQLite BLOB index ➔ Hybrid search (BM25 + NumPy) ➔ SLM generation with citations ➔ Svelte + Tailwind CSS chat UI.
* **🟡 P1 (MVP Polish):** Multi-turn follow-up questions, glossary expansion, topic router boost, CLI tools, and automated regression golden set.
* **⚪ P2 (Post-MVP / Phase 2):** Visual diagram/infographic parsing, Android native build, cross-pack federation.

---

## Detailed Documentation

For full product specifications, hardware benchmarks, and architectural designs, see:
* 📄 [PRD & Tech Spec Document](docs/PRD_and_Tech_Spec.md)
