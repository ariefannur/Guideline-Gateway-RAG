# Analisis Kode & Diagram Flow

## Ringkasan singkat

| Folder / File | Peran utama |
|---|---|
| `engine/` | Implementasi **pipeline** LLM: `pipeline.py` mengatur alur *query → retriever → generator*. `retriever.py` membaca SQLite (`knowledge.sqlite`) dengan FTS5 untuk pencarian chunk relevan. |
| `kpack/` | Paket **knowledge pack** yang berisi *chunker, embedder, indexer* serta skema DB. `PackEmbedder` menghasilkan embedding untuk setiap chunk. |
| `scripts/ingest_football_laws.py` | **Ingestion script**: <br/>1️⃣ Membaca `pack.yaml` → daftar sumber (markdown, PDF).<br/>2️⃣ Meng‑chunk teks lewat `ContextBuilder` (hierarchical‑clause).<br/>3️⃣ Membuat objek `Chunk`.<br/>4️⃣ Meng‑embed semua chunk dengan `PackEmbedder`.<br/>5️⃣ Menyimpan chunk + embedding ke tabel `chunks` dan men‑index‑nya ke `chunks_fts` (FTS5) di `packs/football-laws-2024-2025/knowledge.sqlite`. |
| `docs/PRD_and_Tech_Spec.md` | Spesifikasi produk & alur kerja (tidak diperlukan untuk diagram, tapi memberi konteks kebutuhan). |
| `server/` | API FastAPI (`app.py`) yang mengekspose endpoint **/ask**. Endpoint memanggil `engine.pipeline.run()` untuk memproses pertanyaan pengguna. |
| `tests/` | Unit‑test untuk memastikan pipeline, retriever, dan ingest berfungsi. |

---

## 1️⃣ Flowchart: Ingestion data → DB

```mermaid
flowchart TD
    A[Start: `scripts/ingest_football_laws.py`] --> B[Load pack.yaml]
    B --> C[Gather source files (markdown / PDF)]
    C --> D[Chunk each source<br/>ContextBuilder(max_context_tokens=2500)]
    D --> E[Create Chunk objects]
    E --> F[Batch embed texts<br/>PackEmbedder.embed(texts)]
    F --> G[Attach embedding bytes to Chunk]
    G --> H[Open SQLite DB (knowledge.sqlite)]
    H --> I[Create tables if missing<br/>chunks + chunks_fts (FTS5)]
    I --> J[INSERT OR REPLACE chunks<br/>(chunk_id, metadata, text, embedding)]
    J --> K[Refresh FTS5 index]
    K --> L[Commit & close DB]
    L --> M[Ingestion complete]
```

**Catatan penting**
- Semua chunk disimpan di tabel **`chunks`** (raw + embedding).
- **`chunks_fts`** menyediakan pencarian full‑text yang dipakai oleh `engine.retriever`.
- Skrip dijalankan setelah ada perubahan sumber; menghasilkan DB yang siap dipakai oleh layanan.

---

## 2️⃣ Flowchart: Chat → LLM → DB → User

```mermaid
flowchart LR
    U[User mengirim pertanyaan via UI] -->|HTTP POST /ask| S[FastAPI server (app.py)]
    S --> P[engine.pipeline.run(query)]
    P --> R[engine.retriever.search(query)] 
    R --> DB[(SQLite knowledge.sqlite<br/>chunks_fts FTS5 search)]
    DB --> R
    R -->|Top‑k relevant chunks| G[engine.generator.generate(query, chunks)]
    G -->|LLM (e.g., OpenAI / local model) menghasilkan jawaban| P
    P -->|Response payload| S
    S -->|HTTP response| U
```

**Rincian langkah**
1. **User** mengirim teks pertanyaan.
2. **Server** (`app.py`) menerima request dan memanggil **pipeline**.
3. **Retriever** men‑query SQLite menggunakan FTS5 (`chunks_fts`) untuk menemukan chunk‑chunk yang paling relevan.
4. Hasil chunk (teks + embedding) diserahkan ke **generator** yang men‑format prompt untuk LLM.
5. **LLM** menghasilkan jawaban berdasarkan konteks chunk.
6. Jawaban dikirim kembali ke UI pengguna.

---

## Detail Bagan `Create tables if missing → chunks + chunks_fts (FTS5)`

```mermaid
flowchart TD
    %% 1. Buka / buat DB
    DBOpen[Open SQLite DB (knowledge.sqlite)] --> CreateTables

    %% 2. Buat tabel utama
    CreateTables[CREATE TABLE IF NOT EXISTS chunks] --> TableChunks
    TableChunks[✔ chunks (chunk_id PK, law_no, law_title, path, page, edition,
                  source_type, text, embedding BLOB)] 

    %% 3. Buat Virtual Table FTS5
    CreateTables --> CreateFTS
    CreateFTS[CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5] --> TableFTS
    TableFTS[✔ chunks_fts (chunk_id UNINDEXED, law_title, path, text,
                content='chunks', content_rowid='rowid')]

    %% 4. Hubungkan FTS5 ke tabel utama
    TableFTS --> LinkContent
    LinkContent[FTS5 automatically reads from *chunks* via the
                `content='chunks'` clause] 

    %% 5. Populate / sync index
    LinkContent --> PopulateFTS
    PopulateFTS[INSERT OR REPLACE rows into *chunks*<br/>→ FTS5 index updates automatically] 

    %% 6. Selesai
    PopulateFTS --> Commit[COMMIT transaction] --> Close[Close DB connection] --> Done[✓ Ingestion step ready for chunk insertion]
```

### Penjelasan tiap langkah
| Langkah | Apa yang terjadi |
|---|---|
| **Open SQLite DB** | Membuka (atau membuat bila belum ada) file `knowledge.sqlite`. |
| **CREATE TABLE chunks** | Tabel fisik yang menyimpan semua metadata chunk, teks, dan embedding (BLOB). |
| **CREATE VIRTUAL TABLE chunks_fts** | Virtual table FTS5 yang menyediakan pencarian full‑text; `content='chunks'` mengaitkannya dengan tabel nyata sehingga setiap baris di `chunks` otomatis di‑index. |
| **FTS5 reads from chunks** | Karena `content='chunks'`, FTS5 tidak menyimpan salinan teks; ia hanya merujuk ke kolom `text`, `law_title`, `path` pada tabel `chunks`. |
| **INSERT OR REPLACE** | Saat skrip ingest men‑insert chunk ke tabel `chunks`, SQLite secara internal memperbarui indeks FTS5 di `chunks_fts`. |
| **COMMIT & CLOSE** | Menyimpan perubahan dan menutup koneksi DB, memastikan integritas data dan indeks. |

---

*Dokumen ini dapat dijadikan referensi bagi tim pengembang untuk memahami alur ingest, struktur DB, serta cara LLM berinteraksi dengan knowledge base.*
