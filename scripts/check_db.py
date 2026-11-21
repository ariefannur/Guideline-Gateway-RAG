import sqlite3
import pathlib

DB_PATH = pathlib.Path("packs/football-laws/knowledge.sqlite")

with sqlite3.connect(DB_PATH) as conn:
    cur = conn.cursor()

    # 1. Tabel yang ada
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cur.fetchall()
    print("Tables:", [t[0] for t in tables])

    # 2. Jumlah chunk
    cur.execute("SELECT COUNT(*) FROM chunks")
    cnt = cur.fetchone()[0]
    print("Total chunks:", cnt)

    # 3. Contoh chunk yang menyebut “substitutes”
    cur.execute(
        "SELECT chunk_id, law_title, text FROM chunks "
        "WHERE text LIKE '%offside%' OR text LIKE '%offside%' LIMIT 5"
    )
    rows = cur.fetchall()
    for i, (cid, title, txt) in enumerate(rows, 1):
        snippet = (txt[:200] + "...") if len(txt) > 200 else txt
        print(f"\n[Result {i}] chunk_id={cid}, law_title={title}\n{snippet}\n")