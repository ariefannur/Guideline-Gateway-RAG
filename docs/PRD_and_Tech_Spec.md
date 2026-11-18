# PRD & Tech Spec — Offline-First Guideline RAG

**Reference use case (test case):** Football Laws of the Game guide (sourced from FIFA/IFAB) · **Version:** 0.1 (Draft) · **Date:** 18 November 2026

---

# PART A — PRODUCT REQUIREMENTS DOCUMENT (PRD)

## 1. Summary

**Guideline Gateway** is a question-answering system built on RAG (Retrieval-Augmented Generation) with a *Small Language Model* (SLM). It runs **fully offline** on **minimal hardware**. It acts as a "gateway" to a specific guideline or rulebook: users ask in natural language, and the system answers **only from the source documents**, always with **article/clause citations**.

The system is **domain-agnostic**: the core engine (ingestion, retrieval, generation, guardrails, interfaces) contains no domain logic. Everything domain-specific — source documents, glossary, routing rules, prompt templates, answer format, confidence thresholds, and evaluation set — is packaged in a **Knowledge Pack**. A new domain means a new pack, with no change to the core code.

The football rules (*Laws of the Game*) serve as the **reference use case and test case**: they prove the pipeline works end to end and act as the regression benchmark. Platform success is measured by building a second domain with a different document structure without changing the core code, not by success on football alone.

## 2. Background & Problem

- The football rules (17 Laws) are dense, full of exceptions, and updated every season. New referees, academy coaches, tournament organizers, and fans often misread them (offside, handball, DOGSO, substitutions, etc.).
- Internet access is not always available on the pitch (regional tournaments, academies, referee courses).
- Large cloud LLMs need internet, cost money, and are prone to **hallucination** on official rules, which is unacceptable for guideline use.
- Many organizations have other guideline documents (SOPs, regulations, manuals) with the same problem, so the solution must be replicable.

## 3. Goals & Non-Goals

### Goals

1. Answer questions **accurately, with sources, and verifiably**, for any domain that is loaded.
2. Run **fully offline** (no network calls at runtime).
3. Run on **minimal hardware** (target: CPU-only laptop/mini-PC, 4–8 GB RAM).
4. Be **domain-agnostic**: core engine free of domain logic; changing domain = changing the Knowledge Pack.
5. **Reference use case:** the football rules serve as the end-to-end test case and regression benchmark for the whole platform.
6. Support **source and query languages configured per pack** (v1: Indonesian and English).
7. **Abstain** when evidence is insufficient instead of making things up.

### Non-Goals

- Not a replacement for official decisions or authorities in each domain (e.g., referees and IFAB for football).
- No video analysis or automated decisions (e.g., VAR in the reference pack).
- Not a general chatbot; questions outside the active pack's corpus are declined.
- No fine-tuning on the user's device.
- No cloud sync or user accounts.
- No claim of universal accuracy: every pack must pass its own evaluation before release.

## 4. User Personas

| Persona | Needs | Context |
| --- | --- | --- |
| **New referee / referee course** | Quick rule check with the article cited | Studying, no signal |
| **Academy coach / PE teacher** | Explanations of the rules for young players | Pitch, laptop/tablet |
| **Tournament organizer** | Reference for disputes | Organizer's office, unstable connection |
| **Fan / journalist** | Understanding controversial decisions | Home/cafe |
| **Knowledge Pack admin** | Add new domains, update editions | Technical, offline |

## 5. User Stories & Acceptance Criteria

| ID | User Story | Acceptance Criteria |
| --- | --- | --- |
| US-01 | As a referee, I ask "can a player be offside when receiving the ball from a throw-in?" | Correct answer, names the relevant Law, shows the original source text (EN) plus an explanation (ID) |
| US-02 | As a user, I want to see the sources of an answer | Every answer has at least 1 citation (Law, section, page, edition); clicking a citation opens the original text |
| US-03 | As a user, I ask something outside football | The system politely declines: "outside the scope of this guide" |
| US-04 | As a user, I ask something the document does not regulate | The system answers "no basis found in the document" and points to the nearest section |
| US-05 | As a user, I submit a multi-rule scenario (e.g., handball + DOGSO) | The system retrieves at least 2 relevant Laws and summarizes both with citations |
| US-06 | As an admin, I load a new edition of the Laws | The new Knowledge Pack installs from a file (USB); the old version can be rolled back |
| US-07 | As an admin, I create a new domain | Preparing a PDF + `pack.yaml` + eval set is enough; the build pipeline produces the pack with no code change |
| US-08 | As a user on a weak device | First response time (TTFT) meets the hardware tier target; the app does not crash from OOM |

## 6. Functional Requirements

- **FR-1 Cited Q&A:** answers are generated from retrieved text passages; citations are mandatory.
- **FR-2 Bilingual mode:** queries in ID/EN; the answer is in the query language; original quotes stay in the source language.
- **FR-3 Abstain & scope guard:** retrieval confidence threshold; below it the system declines or abstains.
- **FR-4 Search-only mode:** if the SLM is unavailable or too slow, show the retrieved clauses without generation.
- **FR-5 Domain glossary:** ID↔EN term mapping (e.g., Indonesian "tendangan bebas langsung" ↔ *direct free kick*) to expand queries.
- **FR-6 Knowledge Pack manager:** install, list, activate, roll back, and verify pack integrity.
- **FR-7 Interfaces:** CLI, local REST API, and a lightweight web chat UI built with **Svelte + Tailwind CSS** (compiled into static assets and served directly by FastAPI).
- **FR-8 Multi-turn conversation & local history:** supports conversational follow-up questions within a session. Query processor contextualizes follow-up questions using recent history (last 2–3 turns) with a dedicated sliding token budget. Stored locally, can be cleared or deleted.
- **FR-9 Feedback:** a "wrong/insufficient answer" button stored locally for the next pack improvement (exported manually).
- **FR-10 Domain profile:** parser, chunking strategy, prompt template, answer format, router, and guardrails are selected through configuration in `pack.yaml`, not through code.
- **FR-11 Multi-pack:** several packs can be installed at once; the user selects the active pack. Cross-pack routing is deferred to v1.1.
- **FR-12 Pack template & validator:** `kpack init` creates a new pack skeleton; `kpack validate` checks completeness (glossary, router, golden set, SOURCES.md) before build.
- **FR-13 Two-stage Ingestion & Auditability:** pipeline ekstraksi PDF menghasilkan intermediate Markdown berstruktur sebelum di-chunk dan di-indeks, sehingga admin dapat mengaudit teks regulasi sebelum dijadikan basis data vektor.

## 7. Non-Functional Requirements

| Category | Target (to be validated by benchmarks) |
| --- | --- |
| **Offline** | 0 network connections at runtime; all models and indexes are local |
| **Hardware Tier A (minimum)** | x86-64/ARM64 CPU, 4 cores, 4 GB RAM, no GPU, 5 GB disk |
| **Hardware Tier B (comfortable)** | 6–8 core CPU, 8 GB RAM, 10 GB disk |
| **Latency Tier A** | Retrieval ≤ 300 ms; TTFT ≤ 5 s; full answer ≤ 30 s |
| **Latency Tier B** | TTFT ≤ 3 s; full answer ≤ 20 s |
| **Peak RAM** | Tier A ≤ 3 GB; Tier B ≤ 5 GB |
| **Accuracy (golden set)** | Recall@5 ≥ 90%; faithfulness ≥ 95%; citation accuracy ≥ 95%; answer correctness ≥ 85% |
| **Security & privacy** | User data never leaves the device; packs are signed/hashed |
| **Portability** | Linux, Windows, macOS; Android (optional, via llama.cpp) |
| **Maintainability** | New domain ≤ 1 working day for an experienced admin |

## 8. Success Metrics

- **Quality:** the golden-set metrics above, computed automatically on every pack build.
- **Trust:** share of answers flagged "wrong" by users < 5%.
- **Pilot adoption:** at least 20 weekly active users in the pilot (local referees/coaches/organizers).
- **Efficiency:** median time to find an answer drops compared with opening the PDF manually (measured by a short survey).
- **Reusability:** a second domain (e.g., other tournament regulations/SOPs) is built without changing the core code.

## 9. Platform Scope & Reference Use Case

### 9.1 Platform scope (cross-domain)

The platform serves any structured reference guideline document. The table lists example target domains; football is the first row and acts as the reference pack.

| Domain | Example documents | Chunking profile | Risk level | Guardrail notes |
| --- | --- | --- | --- | --- |
| Sports rules (reference) | Laws of the Game | hierarchical-clause | Medium | Article citation required |
| Internal SOPs / procedures | Safety SOPs, runbooks | procedural-steps | Medium | Step order must not change |
| Regulations / policies | Company rules, implementation guidelines | hierarchical-clause | Medium | Article citation required, edition shown |
| Product / technical manuals | Machine manuals, troubleshooting guides | section-table | Medium | Tables and error codes preserved |
| FAQ / knowledge base | Customer-service FAQ | qa-pair | Low | Direct answer + reference |
| High-risk guidance | Non-diagnostic clinical, legal | hierarchical-clause | High | Expert validation required, stricter abstain threshold, firm disclaimer |

v1 agnostic requirements:

- Source formats: PDF and Markdown are mandatory; DOCX, HTML, and TXT follow through additional parsers.
- Source language and query language are configured per pack.
- Several packs can be installed at once; the user selects the active pack.
- Acceptance criterion: a second pack with a different document structure is built without changing the core code and passes its own evaluation gate.

### 9.2 Reference use case: Laws of the Game

Football was chosen as the test case because its rules are hierarchical, full of exceptions, and easy for practitioners to verify. The scope below applies to the reference pack only, not to the limits of the system.

**Primary source:** the latest *Laws of the Game* document. Note: the Laws are published by **IFAB** and also distributed by **FIFA**; editions change every season (usually effective 1 July). The edition must be recorded in the pack metadata and verified against the current version before release.

**v1 content scope:**

- The 17 Laws (The Field of Play, The Ball, The Players, The Players' Equipment, The Referee, The Other Match Officials, The Duration of the Match, The Start and Restart of Play, The Ball In and Out of Play, Determining the Outcome of a Match, Offside, Fouls and Misconduct, Free Kicks, The Penalty Kick, The Throw-in, The Goal Kick, The Corner Kick).
- Additional parts: definitions, interpretations, VAR protocol, tie-break procedures (if present in the document).
- The ID↔EN glossary is written manually by the admin (not model-generated).

**Out of scope for v1:** competition-specific regulations (e.g., a particular league or country), futsal, beach soccer, match results/news. Visual/diagram/infographic parsing (misal: diagram posisi offside visual) di-flag untuk fase berikutnya (Phase 2); v1 murni fokus pada struktur teks dan klausul hierarkis.

## 10. Risks & Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| SLM hallucinates or drifts | Wrong rule answers | Strict "context only" prompt, citation verification, abstain threshold, show original quotes |
| English document, Indonesian query | Retrieval misses | Multilingual embedder, glossary, query expansion, cross-language evaluation |
| Multi-rule (situational) questions | SLM struggles to reason | Topic→Law router, multi-Law retrieval, structured answer (Decision / Basis / Note) |
| Very weak hardware | Slow or OOM | Model tiers (1B/3B), Q4 quantization, search-only mode, context limits |
| Document copyright | Distribution obstacles | Check IFAB/FIFA licensing before distributing packs with the text; alternative: users build the pack locally from a PDF they download themselves |
| Outdated rule edition | Stale answers | Show edition in the UI; warn if the pack is over 1 year old; offline update mechanism |
| Poor PDF parsing (tables/figures) | Corrupted context | Validate parsing output, manual correction at build time, golden tests |

## 11. MVP Scope Prioritization (P0 / P1 / P2)

Untuk mencegah *scope creep*, seluruh kapabilitas dan pekerjaan dikelompokkan ke dalam 3 tingkat prioritas:

### 🔴 P0 — Core MVP (Must-Have / Blocker)
> **Goal:** Membuktikan sistem berfungsi penuh *end-to-end* secara offline: dari file PDF ➔ Ingestion ➔ SQLite + NumPy Hybrid Search ➔ SLM lokal ber-sitasi ➔ Svelte Web UI.

* **Epic 1: Ingestion & Pack Builder (`kpack`)**
  * `TASK-1.1`: Ekstraksi PDF ke Intermediate Markdown (`laws.md`) via `PyMuPDF` (denoising running header, footer, page number).
  * `TASK-1.2`: Structure-aware Chunker (memotong klausul 150–350 token + menyematkan Contextual Header `[Law X > ...]`).
  * `TASK-1.3`: Batch embedding model `multilingual-e5-small` (ONNX Runtime CPU) + normalisasi L2.
  * `TASK-1.4`: SQLite Builder (tabel `chunks` dengan metadata, teks, dan `embedding BLOB` + virtual table FTS5).
  * `TASK-1.5`: Packaging arsip file `.kpack`.
* **Epic 2: Core Engine & Retrieval (`engine`)**
  * `TASK-2.1`: Pack Loader (buka SQLite dan load matriks embedding ke NumPy array in-memory ~1.5 MB).
  * `TASK-2.2`: Hybrid Search (BM25 via SQLite FTS5 + Cosine Similarity via NumPy dot product).
  * `TASK-2.3`: Fusi peringkat menggunakan Reciprocal Rank Fusion (RRF, k=60).
  * `TASK-2.4`: Hard Abstain threshold (Cosine Similarity Top-1 < `min_score` 0.35 ➔ langsung return `abstain`).
* **Epic 3: SLM Generation & Guardrails (`engine`)**
  * `TASK-3.1`: Runtime `llama-cpp-python` untuk memuat model GGUF lokal (Qwen2.5-1.5B Q4).
  * `TASK-3.2`: Context Builder (merakit system prompt + evidence chunk `[C1]`, `[C2]` sesuai token budget).
  * `TASK-3.3`: Grounded Prompting (instruksi hanya menjawab dari konteks, format baku).
  * `TASK-3.4`: Regex Citation Validator (memastikan tag `[C#]` valid terhadap konteks yang disajikan).
* **Epic 4: Server & Web UI (`server` & `ui`)**
  * `TASK-4.1`: FastAPI server: endpoint `POST /v1/ask` (support non-stream & SSE streaming).
  * `TASK-4.2`: Web UI Svelte + Tailwind CSS (chat bubble responsif, badge sitasi `[C#]` interaktif).
  * `TASK-4.3`: FastAPI me-mount static build dari Svelte (`ui/dist/`) di root `/`.

---

### 🟡 P1 — MVP Polish (Should-Have / Fast-Follow)
> **Goal:** Meningkatkan akurasi kueri ID/EN, percakapan lanjutan (multi-turn), manajemen pack, dan evaluasi regresi.

* **Epic 5: Query Processor & Multi-Turn**
  * `TASK-5.1`: Multi-turn query contextualization (ringkas query lanjutan menggunakan 1–2 percakapan sebelumnya).
  * `TASK-5.2`: Integrasi `glossary.yaml` (ekspansi istilah Indonesia ke Inggris untuk BM25).
  * `TASK-5.3`: Integrasi `router.yaml` (skor boost berdasarkan topik Law).
* **Epic 6: CLI & Pack Management**
  * `TASK-6.1`: User CLI: `gateway ask "pertanyaan"` dan `gateway serve`.
  * `TASK-6.2`: Admin CLI: `kpack build packs/football-laws/` dan `kpack validate`.
  * `TASK-6.3`: Endpoint manajemen pack (`GET /v1/packs`, `POST /v1/packs/{id}/activate`).
* **Epic 7: Evaluasi & Golden Set Awal**
  * `TASK-7.1`: Dataset mini `golden.jsonl` (30 pertanyaan aturan sepak bola).
  * `TASK-7.2`: Automated evaluation test runner (Recall@5 & Abstain Accuracy).

---

### ⚪ P2 — Post-MVP / Phase 2 (Sengaja Ditunda)
> **Goal:** Fitur tingkat lanjut yang **TIDAK** dikerjakan pada rilis MVP.

1. **Multimodal / Diagram Parsing:** Ekstraksi gambar diagram visual offside atau infografis lapangan.
2. **Android Native / JNI Build:** Build standalone smartphone APK.
3. **Cross-Pack Federation:** Pencarian lintas beberapa knowledge pack sekaligus.
4. **Constrained Decoding (GBNF Grammar):** Enforcement token via grammar formal (digantikan regex validator di P0).
5. **Auto-judge LLM Dev Pipeline:** Evaluator otomatis menggunakan model cloud besar.

---

## 12. Milestones

| Phase | Duration | Output |
| --- | --- | --- |
| **M0 — Research & Setup** | 1 week | Final model choices, first benchmarks on target hardware |
| **M1 — Ingestion & Retrieval (P0)** | 2 weeks | Parser, chunker, hybrid index, retrieval eval (Recall@k) |
| **M2 — Generation & Guardrails (P0)** | 2 weeks | Prompt, SLM runtime, citations, abstain, faithfulness eval |
| **M3 — Interfaces & Pack Manager (P0/P1)** | 2 weeks | CLI, REST API, Svelte + Tailwind CSS Web Chat UI (compiled static SPA), pack install/rollback |
| **M4 — Pilot & Evaluation (P1)** | 2 weeks | Test with real referees/coaches, fixes from feedback |
| **M5 — Generalization** | 1–2 weeks | Pack template, new-domain documentation, a second pack with a different document structure as the agnostic test (v1 release gate) |

## 13. Open Questions & Decided Items

1. **Client Platform & Web UI (Decided):** MVP berfokus pada Desktop/Laptop via CLI, Local REST API, dan Web Chat UI berbasis **Svelte + Tailwind CSS** (di-build sebagai static SPA yang disajikan oleh FastAPI). Dukungan Android native/JNI dialokasikan untuk fase lanjutan.
2. **Multi-turn Support (Decided):** Mendukung percakapan lanjutan (*follow-up*) dengan query contextualizer dan token sliding budget (~400 token).
3. **Diagrams/Images (Decided):** Ekstraksi dan pemrosesan visual/diagram di-flag untuk fase berikutnya; v1 murni teks regulasi terstruktur.
4. Will the pack be distributed to others (licensing issue) or used internally only?
5. Are answer languages beyond ID/EN needed?
6. How much tolerance is there for "search-only" mode on very weak devices?
7. Who is the rule "validator" (licensed referee) for the golden set?

---

# PART B — TECH SPEC

## 1. Design Principles

1. **Grounded-first:** the model only summarizes retrieved evidence; retrieval quality matters more than model size.
2. **Offline by construction:** no runtime network dependency; all artifacts are local and versioned.
3. **Resource-frugal:** quantized models, short context, lightweight index (SQLite).
4. **Separate code from domain:** everything domain-specific lives in the Knowledge Pack.
5. **Verifiable:** every claim in an answer traces back to a chunk ID.
6. **Graceful degradation:** if generation fails or is slow, still show the retrieval results.

## 2. High-Level Architecture

There are two paths: **Build-time** (online / on the developer machine, produces the pack) and **Run-time** (offline on the user's device).

```
BUILD-TIME (admin machine)                      RUN-TIME (user device, offline)

Source PDF/Docs                                 Client: CLI / Web UI / Mobile
   │                                                   │
   ▼                                                   ▼
[1] Parser & Cleaner                            [A] API Gateway (local REST)
   │                                                   │
   ▼                                                   ▼
[2] Structure-aware Chunker                     [B] Query Processor
   │  (Law > Section > Clause)                      │  lang detect, glossary, scope check
   ▼                                                   ▼
[3] Embedding (small multilingual model)        [C] Hybrid Retriever
   │                                                │  BM25 (FTS5) + Vector (NumPy In-Memory) → RRF
   ▼                                                ▼
[4] Index Builder (SQLite + FTS5 + BLOB)        [D] (optional) Light Reranker
   │                                                ▼
   ▼                                            [E] Context Builder (token budget)
[5] Eval Harness (golden set)                       ▼
   │                                            [F] SLM Generator (llama.cpp, GGUF Q4)
   ▼                                                ▼
[6] Packager → *.kpack (+ manifest, hash)       [G] Guardrail: citation check, abstain
                                                    ▼
                                                Cited response
```

### 2.1 Boundary between generic core and domain

The core must contain no football-specific strings, regexes, or rules. All domain logic is data (YAML, Markdown, JSONL) inside the pack.

| Component | Generic (core code) | Domain-specific (in the pack) |
| --- | --- | --- |
| Ingestion | PDF/Markdown parsers, cleaning, chunk pipeline | Choice of parser and chunking profile, manual corrections |
| Query processing | Language detection, glossary expansion, scope check | glossary.yaml, router.yaml, scope\_description |
| Retrieval | Hybrid BM25 + vector, RRF, abstain threshold | top\_k, min\_score, router boost |
| Generation | SLM runtime, context builder, streaming | System prompt, answer schema, answer style |
| Guardrails | Citation validator, abstain, fallback | risk\_level, disclaimer, thresholds |
| Evaluation | Harness and metrics | golden.jsonl and pass thresholds |
| API / UI | REST, CLI, web UI | Domain name, sample questions, disclaimer text |

### 2.2 Domain profiles

A profile is a ready-made strategy bundle selected through `pack.yaml`. One pack can use different profiles per source document.

| Profile | Suited for | Chunking strategy | Default answer format |
| --- | --- | --- | --- |
| hierarchical-clause | Rules, regulations, policies (reference pack: Laws of the Game) | Split by article/clause; contextual header holds the hierarchy path | Decision, Basis, Note |
| procedural-steps | SOPs, runbooks, troubleshooting | One procedure = one chunk group; step order, prerequisites, and warnings preserved | Numbered steps, Prerequisites, Warnings |
| section-table | Product/technical manuals | Per section; tables become their own chunks with column headers carried over | Short answer, Specification, Reference |
| qa-pair | FAQ, knowledge base | One Q&A pair = one chunk; the question is embedded too | Direct answer, Reference |

### 2.3 Extension points

When a domain needs behavior that cannot be expressed as configuration, add a generic *extension point* rather than an `if domain == ...` branch in the core. v1 extension points:

- **Parser plugin:** adds a new source format.
- **Chunker plugin:** adds a new chunking profile.
- **Answer post-processor:** validates or formats answers to a domain schema.
- **Guardrail rule:** extra declarative rules (e.g., forbidden phrases, mandatory disclaimers).

Each extension point is a small interface with contract tests. Plugins load from the installation's `profiles/` directory; a pack only references them by name and carries no executable code.

## 3. Knowledge Pack

### 3.1 Structure

```
football-laws-2026-27.kpack   (zip)
├── manifest.json        # id, version, source edition, hash, required model specs & dims, schema
├── pack.yaml            # domain configuration (see 3.2)
├── knowledge.sqlite     # chunk table + FTS5 + vectors
├── glossary.yaml        # ID↔EN terms, synonyms
├── router.yaml          # topic → Law (light routing rules)
├── prompts/
│   ├── system.md
│   └── answer_template.md
├── eval/
│   └── golden.jsonl     # questions, reference answers, evidence chunks
└── SOURCES.md           # source attribution & licensing
```

> [!NOTE]
> **Pemisahan Model vs Pack:** File bobot model (GGUF generator dan ONNX embedding) **tidak dibungkus** di dalam `.kpack` agar ukuran pack tetap ringan (hitungan megabyte). File model disimpan di direktori global runtime host (misal: `~/.guideline-gateway/models/` atau `./models/`). File `manifest.json` mencatat spesifikasi model, dimensi embedding, dan checksum yang wajib dipenuhi oleh host.

### 3.2 Example `pack.yaml`

```yaml
id: football-laws            # reference pack / test case
edition: "2026/27"          # fill in per the verified source document
domain_profile: hierarchical-clause   # see 2.2
risk_level: medium           # low | medium | high, affects thresholds and disclaimer
source_lang: en
supported_query_langs: [id, en]
scope_description: "Football match rules, 11-a-side (Laws of the Game)"
sources:
  - file: sources/laws-of-the-game.pdf
    parser: pdf-structured
    chunking: hierarchical-clause
retrieval:
  top_k_bm25: 20
  top_k_vec: 20
  fused_top_k: 6
  min_score: 0.35            # below this → abstain (calibrated through eval)
generation:
  max_context_tokens: 2200
  max_new_tokens: 350
  temperature: 0.1
answer_format: [verdict, basis, caveat]
disclaimer: "Official decisions rest with the referee/competition authority."
```

## 4. Ingestion & Chunking Pipeline

Tahap ingestion dirancang dengan prinsip **kualitas data di atas segalanya** (*garbage in, garbage out*). Pipeline menggunakan pendekatan **2-Tahap (Two-Stage Pipeline)** dengan representasi perantara (*intermediate markdown*) agar admin dapat mengaudit dan memverifikasi teks regulasi sebelum di-indeks ke dalam basis data.

```
Source PDF
   │
   ▼
[1] PDF Structural Parser (PyMuPDF / fitz)
   │  - Deteksi font size & weight untuk hierarki heading
   │  - Bounding-box filtering (buang running header, footer, page number)
   │  - Skip diagram/image (di-flag untuk Phase 2)
   ▼
[2] Intermediate Structured Markdown (laws.md)
   │  - Format bersih berstruktur Markdown (# Law, ## Section, ### Clause)
   │  - Dapat diaudit & dikoreksi manual oleh admin jika diperlukan
   ▼
[3] Structure-Aware Chunker
   │  - Memotong per klausul/sub-pasal (150–350 tokens)
   │  - Menempelkan Contextual Header: [Law X > Section Y > Clause Z]
   ▼
[4] Batch Vector Embedding (ONNX Runtime CPU)
   │  - Model: multilingual-e5-small (dim 384)
   │  - Normalisasi L2 (agar dot-product identik dengan cosine similarity)
   ▼
[5] Index Storage (knowledge.sqlite)
      - Tabel chunks (metadata + raw text + embedding BLOB)
      - Virtual table FTS5 (full-text search BM25)
```

### 4.1 Detail Tahapan Ingestion

#### A. PDF Extraction & Noise Filtering (Denoising)
* **Library:** `PyMuPDF` (`fitz`) dipilih karena performa ekstraksi teks sangat cepat (C-based) serta mampu membaca atribut teks per-blok (`font_size`, `font_weight`, dan koordinat `bbox`).
* **Denoising Rules:**
  1. *Header & Footer Stripping:* Koordinat vertikal ($y < \text{margin\_top}$ dan $y > \text{margin\_bottom}$) diabaikan otomatis untuk membuang running header dokumen dan nomor halaman.
  2. *Artifact Cleaning:* Menghapus karakter ligatur PDF aneh, spasi ganda, dan baris kosong berlebih.
  3. *Diagram & Image Flagging:* Gambar, diagram lapangan, dan ilustrasi diabaikan untuk v1 (di-flag untuk Phase 2). Parser hanya fokus pada teks klausul regulasi murni.

#### B. Intermediate Representation (Structured Markdown)
* Hasil ekstraksi PDF dikonversi menjadi file perantara Markdown standar (`sources/extracted/laws.md`):
  * `# Law 11 — Offside`
  * `## 1. Offside Position`
  * `### 1.1 Clause Detail`
* **Keuntungan:** Admin dapat me-review, membandingkan dengan PDF asli via `git diff`, atau menyisipkan koreksi kata sebelum diproses ke database vektor.

#### C. Structure-Aware Chunking & Contextual Header
* **Unit Pemotongan:** Berbasis klausul atau butir aturan regulasi (bukan pemotongan buta berbasis jumlah karakter tetap).
* **Ukuran Target:** 150–350 token per chunk. Jika ada butir klausul yang panjang, dipotong pada batas kalimat dengan tumpang tindih (*overlap*) ±30 token.
* **Contextual Header Enrichment:** Setiap teks chunk disisipkan *breadcrumb* hierarki di baris paling atas sebelum di-embed:
  ```text
  [Law 11 — Offside > 2. Offside Offence > Interfering with an opponent]
  A player in an offside position at the moment the ball is played or touched by a team-mate is only penalised on becoming involved in active play by interfering with play...
  ```
  *Contextual header ini krusial agar model SLM dan pencarian vektor memahami konteks hierarki pasal secara utuh.*

#### D. Batch Embedding & Storage
* **Runtime:** ONNX Runtime (CPU-optimized, batch size 32 chunk).
* **Normalisasi L2:** Seluruh vektor embedding di-normalisasi ($\|v\|_2 = 1$). Dengan ini, perhitungan *cosine similarity* pada saat runtime disederhanakan menjadi operasi perkalian titik (*dot product*) NumPy yang selesai dalam < 1 milidetik.
* **Metadata per chunk:**

```json
{
  "chunk_id": "law11-2-1",
  "law_no": 11,
  "law_title": "Offside",
  "path": ["Offside offence", "Interfering with play"],
  "page": 94,
  "edition": "2024/25",
  "lang": "en",
  "text": "[Law 11 — Offside > 2. Offside Offence > Interfering with play]\nA player in an offside position...",
  "source_type": "original"
}
```

### 4.2 SQLite Schema

```sql
CREATE TABLE chunks(
  chunk_id TEXT PRIMARY KEY,
  law_no INT,
  law_title TEXT,
  path TEXT,
  page INT,
  edition TEXT,
  source_type TEXT,
  text TEXT,
  embedding BLOB  -- Array float32 384 dim (1.536 bytes raw byte buffer)
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
  chunk_id UNINDEXED,
  law_title,
  path,
  text,
  content='chunks',
  content_rowid='rowid'
);
```

> [!NOTE]
> **Vector Search via NumPy In-Memory:** Embedding disimpan sebagai raw bytes (`BLOB`) di SQLite. Saat Knowledge Pack dibuka pada runtime, seluruh embedding di-load ke NumPy 2D array in-memory (~1.5 MB RAM untuk ~1.000 chunks). Pencarian vector (cosine similarity) berjalan murni in-memory dalam < 1 ms menggunakan NumPy tanpa dependensi C-extension seperti `sqlite-vec`, menjamin portabilitas 100% di semua OS dan hardware minimal.

## 5. Model Selection

All size/performance figures are estimates and **must be benchmarked on target hardware** in M0.

### 5.1 Embedding (small, multilingual)

| Candidate | Notes |
| --- | --- |
| **multilingual-e5-small** (\~118M, 384 dim) | Default for Tier A; light, adequate for cross-language ID↔EN |
| **EmbeddingGemma** (\~300M) | Higher-quality alternative for Tier B; dimensions can be truncated |
| **bge-m3** (\~570M) | High quality but heavy; Tier B/C only |

Rule: the embedding model **must be identical** at build time and run time; its version is recorded in `manifest.json`.

### 5.2 Generator (SLM, instruct, quantized GGUF)

| Tier | Candidates | Quantization | Approx. model RAM |
| --- | --- | --- | --- |
| **A (4 GB RAM)** | Qwen2.5-1.5B-Instruct / Llama-3.2-1B / Gemma-3-1B | Q4\_K\_M | \~1–1.2 GB |
| **B (8 GB RAM)** | Qwen2.5-3B-Instruct / Llama-3.2-3B / Gemma-3-4B / Phi-3.5-mini | Q4\_K\_M | \~2–2.8 GB |

Selection criteria (tested on the golden set): (1) obeying the "context only" instruction, (2) Indonesian language quality, (3) following the citation format, (4) tokens/second on target CPUs, (5) a license that allows use/distribution.

**Core strategy:** small model + curated context + structured answer format. Choose the model from eval results, not reputation.

### 5.3 Reranker (optional)

A light cross-encoder (or a heuristic combined score) is enabled only on Tier B or when Recall@k misses its target. It is skipped on Tier A to protect latency.

## 6. Runtime Pipeline Details

### 6.1 Query Processor

1. **Multi-turn Contextualization**: jika request menyertakan riwayat percakapan sebelumnya (*chat history*), pertanyaan lanjutan (misal: *"bagaimana jika bolanya kena kiper dulu?"*) diringkas/dikontekstualisasikan menjadi query mandiri berbasis konteks putaran terakhir sebelum retrieval.
2. **Normalization** (lowercase, strip excess punctuation).
3. **Language detection** (light, rule-based or small library).
4. **Glossary expansion**: add English equivalents for Indonesian terms (e.g., "ofsaid" → *offside*, "kartu merah" → *sending-off, red card*).
5. **Topic router**: keyword rules map the query to candidate document sections via router.yaml (e.g., on the football pack: "penalti" → Law 14, "tangan" → Law 12). The router result is a **boost**, not a hard filter.
6. **Early scope check**: a query with no adequate semantic/lexical match → abstain here.

### 6.2 Hybrid Retrieval

- BM25 through SQLite FTS5 on the query (ID + expanded EN).
- Vector search: Cosine similarity via NumPy in-memory matrix multiplication over cached chunk embeddings.
- Fuse with **Reciprocal Rank Fusion** (k=60), then apply the router boost.
- Complex/situational queries: split deterministically by router result into sub-queries per Law (max 3) and merge the results.
- Output: `fused_top_k` chunks + scores.

### 6.3 Context Builder

- **Context budget allocation** (total window 2048–4096 tokens):
  - System prompt: ~200 tokens
  - Multi-turn recent history (sliding window 2–3 putaran terakhir): maks ~400 tokens
  - Retrieved evidence chunks (`[C1]`, `[C2]`, …): ~1500–2200 tokens (order chunks by score, add until budget exhausted, deduplicate adjacent clauses)
  - Model generation output budget: ~350–500 tokens
- Setiap chunk bukti dilabeli `[C1]`, `[C2]`, … lengkap dengan header Law/page.

### 6.4 Generation

System prompt (abridged; this is the football pack's `prompts/system.md`, the core only loads the template from the pack):

```
You are an assistant for football match rules.
Answer ONLY from the provided context. Do not use any other knowledge.
If the context is insufficient, say "Not enough basis found in the document".
Every rule statement must be followed by a citation marker [C#].
Answer format:
1) Decision (1–2 sentences)
2) Rule basis (bullets, each with a citation)
3) Notes/exceptions (if any)
Answer in the same language as the question.
```

Parameters: low temperature (0.0–0.2), limited `max_new_tokens`, *stop sequences* matching the format, optional **grammar/constrained decoding** (llama.cpp GBNF) to force the citation structure.

### 6.5 Post-Generation Guardrails

1. **Citation validation**: every `[C#]` must point to a chunk present in the context; invalid citation → drop that sentence or regenerate once.
2. **Support check** (light): for each cited sentence, compute lexical/semantic similarity with the referenced chunk; below threshold → mark "weakly supported".
3. **Abstain**: if the top retrieval score < `min_score` or the model answers not-enough-basis → standard response + show the 2–3 nearest clauses.
4. **Fallback**: if generation times out or fails → show the retrieval results (search-only mode).
5. **Footer**: show the rule edition and a disclaimer that official decisions rest with the referee/authority.

## 7. API (Local REST)

**`POST /v1/ask`**

```json
// Request
{
  "pack_id": "football-laws",
  "question": "Bagaimana jika bolanya disentuh pemain lawan sebelum masuk?",
  "history": [
    { "role": "user", "content": "Can a player be offside from a throw-in?" },
    { "role": "assistant", "content": "No. A player cannot be penalized for offside ... [C1]" }
  ],
  "mode": "answer",          // "answer" | "search_only"
  "stream": true
}
```

```json
// Response (non-stream)
{
  "status": "answered",      // answered | abstained | out_of_scope | error
  "answer": "No. A player cannot be penalized for offside ... [C1]",
  "citations": [
    {
      "ref": "C1",
      "chunk_id": "law11-1-1",
      "law_no": 11,
      "law_title": "Offside",
      "page": 93,
      "edition": "2026/27",
      "quote_original": "A player is not in an offside position if ... receives the ball directly from a throw-in"
    }
  ],
  "confidence": 0.82,
  "timings_ms": { "retrieval": 120, "ttft": 2400, "total": 11800 },
  "pack": { "id": "football-laws", "edition": "2026/27" }
}
```

**Other endpoints:**

- `GET /v1/packs` — list installed packs and their status.
- `POST /v1/packs/install` — install from a local `.kpack` file (hash verified).
- `POST /v1/packs/{id}/activate` · `POST /v1/packs/{id}/rollback`.
- `GET /v1/chunks/{chunk_id}` — original text for citation display.
- `POST /v1/feedback` — store feedback locally.
- `GET /healthz` — model, index, and memory status.

Note: the server binds to `127.0.0.1` only by default.

## 8. Technology & Stack

| Layer | MVP choice | Rationale | Production option |
| --- | --- | --- | --- |
| LLM runtime | **llama.cpp** (GGUF) via `llama-cpp-python` | Mature CPU support, quantization, runs on all OSes | llama.cpp server / native binding; Android via JNI |
| Embedding runtime | ONNX Runtime or llama.cpp (embedding GGUF) | Light, CPU-friendly | Same |
| Storage | **SQLite** + FTS5 + **NumPy In-Memory** (embeddings as BLOB) | Single file, no server, 100% portable cross-platform without native C extensions, <1ms vector latency | Same |
| Backend | Python (FastAPI) | Fast iteration | Rust/Go or C++ for a single binary |
| UI | **Svelte + Tailwind CSS** (SPA build, served statically by FastAPI) | Highly reactive, modern styling, lightweight bundle, smooth streaming token rendering | Native/mobile clients use the same REST API |
| Build pipeline | Python CLI (`kpack build`) | Reproducible, scriptable | Local CI |
| Packaging | PyInstaller / bundle with model | One-install distribution | Per-OS installers |

## 9. Hardware Resource Profiles

|  | Tier A (minimum) | Tier B (comfortable) |
| --- | --- | --- |
| CPU | 4-core x86-64/ARM64 (AVX2 / NEON) | 6–8 cores |
| RAM | 4 GB | 8 GB |
| Disk | 5 GB | 10 GB |
| Generator model | \~1–1.5B Q4 | \~3–4B Q4 |
| Embedding | e5-small | e5-small / EmbeddingGemma |
| Reranker | Disabled | Optional |
| Context | 2048–3072 | 4096 |
| Threads | n\_cores − 1 | n\_cores − 1 |
| Options | `mmap`, `mlock` off, small batch | GPU offload if available |

General optimizations: Q4\_K\_M quantization, bounded KV cache, `mmap` for model loading, *prompt caching* for the fixed system prompt, token streaming for lower perceived latency, *lazy* model loading and unloading after long idle.

## 10. Evaluation

### 10.1 Golden Set

- **Initial size:** 150–200 questions, written/validated by licensed referees or experienced practitioners.
- **Composition:** direct factual (40%), situational scenarios (30%), multi-Law (15%), Indonesian terms/slang (10%), out-of-scope/trap (5%).
- **`golden.jsonl` format:**

```json
{"id":"q-017","q":"The goalkeeper holds the ball for more than 6 seconds. What is the consequence?",
 "lang":"en","type":"factual",
 "gold_answer":"...","gold_chunks":["law12-x-y"],"must_abstain":false}
```

The composition above is a template for the reference pack. Other domains adjust the proportions, but always include trap/out-of-scope questions and cross-language questions.

### 10.2 Metrics

| Metric | How measured | Target |
| --- | --- | --- |
| Recall@k / MRR | Gold chunk appears in top-k retrieval results | R@5 ≥ 90% |
| Faithfulness | Every claim supported by the context | ≥ 95% |
| Citation accuracy | Citation points to the correct chunk | ≥ 95% |
| Answer correctness | Compared with the reference answer (manual review + LLM judge in dev) | ≥ 85% |
| Abstain precision/recall | Trap questions are correctly declined | ≥ 90% |
| Latency & RAM | Automated benchmark per tier | Per PRD §7 |

A larger-model automatic judge is used **only in the development environment** (never on user devices), and its results are sampled for manual review.

### 10.3 Regression Gate

Every pack build must pass the metric thresholds above; otherwise the pack is not released. Model/prompt/chunking changes are compared against the previous baseline.

## 11. Security, Privacy & Integrity

- No outbound telemetry; all logs are local and can be disabled.
- The local server listens on `127.0.0.1` only unless explicitly configured otherwise.
- **Pack integrity:** SHA-256 hash in `manifest.json` + optional signature; install rejects packs whose hash does not match.
- **Model artifacts:** model checksums are recorded in the manifest.
- **Prompt injection:** the corpus comes from trusted documents curated by the admin; user content never enters the corpus; context is clearly delimited and the model is told to treat context as data.
- **Licensing:** `SOURCES.md` lists the source, edition, and distribution permission status.

## 12. Local Observability

Structured logs (JSON lines) contain: query ID (no personal data), retrieval scores, selected chunks, status (answered/abstained), per-stage latency, and memory use. They support debugging and threshold calibration and can be exported manually by users to improve the pack.

## 13. Updates & Versioning

- Pack version scheme: `<domain>-<edition>-r<revision>` (e.g., `football-laws-2026-27-r1`).
- Offline updates through a `.kpack` file (USB/manual download); several versions can be installed side by side; **rollback** is one step.
- Changing the embedding model requires an **index rebuild** (a new pack); never mix them.
- The UI warns if the pack edition is older than the validity period set in the manifest.

## 14. Generalizing to Other Domains

To create a new domain (e.g., safety SOPs, other tournament regulations, non-diagnostic clinical guidance):

1. Run `kpack init <domain>` to create a pack skeleton from `packs/_template/`.
2. Fill in `pack.yaml` (domain profile, risk level, scope, thresholds) and place the source documents.
3. Write `glossary.yaml` and `router.yaml` (optional but recommended).
4. Create 100+ golden questions with a domain expert; trap and cross-language questions are mandatory.
5. Run `kpack validate`, then `kpack build` → evaluate → release if it passes the gate.
6. Adjust `prompts/` if the domain's answer format differs (e.g., step-by-step procedures).

Note: high-risk domains (medical, legal) need stricter guardrails and disclaimers, plus expert validation before release.

**Agnostic test (v1 release gate):** a second pack with a different document structure (e.g., a procedural SOP or an FAQ) must be built just by creating a new pack, with no change to `engine/`. If a code change is unavoidable, it is recorded as a generic extension point and the football pack tests must still pass.

## 15. Repository Structure (Proposed)

```
guideline-gateway/
├── engine/            # generic: query, retrieval, context, generation, guardrails
├── kpack/             # generic build pipeline: parse, chunk, embed, index, eval, package
├── profiles/          # domain profiles: hierarchical-clause, procedural-steps, section-table, qa-pair
├── server/            # REST API + serves static web UI
├── ui/                # Svelte + Tailwind CSS frontend chat interface (builds to static assets for server)
├── cli/               # ask, packs, bench, kpack init/validate/build
├── packs/
│   ├── _template/     # empty pack skeleton
│   └── football-laws/ # REFERENCE PACK / test case
├── bench/             # hardware & model benchmark scripts
├── docs/
└── tests/             # includes a test that the engine is free of domain logic
```

## 16. Test Plan

- **Unit:** chunker (clause boundaries), glossary, router, citation validator.
- **Integration:** build pack → install → ask → verify the end-to-end response.
- **Automated evaluation:** golden set on every change (regression gate).
- **Benchmarks:** latency/RAM on real Tier A and Tier B devices (not just VMs).
- **Offline test:** run with the network blocked (firewall) and confirm no connection attempts.
- **User testing:** sessions with referees/coaches; collect answers judged wrong for improvement.

## 17. Next Steps (Recommended Execution)

1. Download the latest *Laws of the Game* document (for the reference pack) and record its edition and license.
2. Run **M0**: benchmark 2–3 generator models and 2 embedding models on the minimum hardware you target.
3. Build a small golden set (30–50 questions) first to guide model selection and chunking.
4. Prototype the end-to-end pipeline in Python, keeping the `engine/` and `packs/` boundary clean from day one.
5. Once the reference pack passes the gate, build a second pack with a different document structure as the agnostic test.
