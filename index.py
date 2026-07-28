"""Mevzuat arşivini vektör veritabanına indeksler.

CSV'deki her belge için: metni çıkar -> parçala -> embedding hesapla -> Chroma'ya
yaz. 2715 belge uzun sürdüğü için işlenen belgeler bir ilerleme dosyasına
kaydediliyor; çalışma yarıda kesilirse kalınan yerden devam eder.
"""

import csv
import json
import os
import sys

from config import CHUNK_SIZE, CHUNK_OVERLAP
from document_processor import extract_text, chunk_text
from embeddings import embed_passages
from vector_store import add_chunks, delete_document

DATASET_CSV = "data/mevzuat_dataset.csv"
PROGRESS_FILE = "data/indexed_ids.json"

# Bir belgenin embedding'leri tek seferde bu kadar chunk'lık gruplar halinde
# hesaplanıyor; hepsini birden vermek belleği şişiriyor.
EMBED_BATCH = 64


def load_progress():
    if not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        return set(json.load(f))


def save_progress(done_ids):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(done_ids), f)


def load_rows():
    with open(DATASET_CSV, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def index_document(row):
    """Tek belgeyi indeksler, yazılan chunk sayısını döner."""
    text = extract_text(row["local_path"])
    if not text or not text.strip():
        return 0

    chunks = chunk_text(text, CHUNK_SIZE, CHUNK_OVERLAP)
    delete_document(row["content_id"])
    # Kaynak gösterebilmek için her chunk'a belgenin künyesi ekleniyor.
    metadata = {
        "content_id": row["content_id"],
        "title": row["title"],
        "category": row["category"],
        "date": row["date"],
        "rg_date": row["rg_date"],
        "rg_number": row["rg_number"],
        "number": row["number"],
        "source_url": row["source_url"],
    }

    written = 0
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start:start + EMBED_BATCH]
        embeddings = embed_passages(batch)
        ids = [f"{row['content_id']}_{start + i}" for i in range(len(batch))]
        add_chunks(batch, embeddings, metadata, ids)
        written += len(batch)
    return written


def index_all(extensions=None, limit=None):
    """extensions verilirse sadece o uzantılar işlenir (ör. {'.pdf', '.docx'})."""
    rows = load_rows()
    done = load_progress()

    todo = []
    for row in rows:
        if row["content_id"] in done:
            continue
        ext = os.path.splitext(row["local_path"])[1].lower()
        if extensions and ext not in extensions:
            continue
        todo.append(row)

    if limit:
        todo = todo[:limit]

    print(f"Toplam {len(rows)} belge, {len(done)} zaten indeksli, {len(todo)} işlenecek.")

    total_chunks = 0
    failed = 0
    for i, row in enumerate(todo, 1):
        try:
            n = index_document(row)
            total_chunks += n
            done.add(row["content_id"])
            status = f"{n} chunk" if n else "metin yok"
        except Exception as e:
            failed += 1
            status = f"HATA {type(e).__name__}"
        print(f"[{i}/{len(todo)}] {status:18s} {row['title'][:60]}")

        if i % 25 == 0:
            save_progress(done)
            sys.stdout.flush()

    save_progress(done)
    print(f"\nBitti. Yazılan chunk: {total_chunks} | Başarısız belge: {failed}")


if __name__ == "__main__":
    # .doc'lar doc_converter ile önceden metne çevrildiği için burada da
    # işlenebiliyor. Metin katmanı olmayan taranmış PDF'ler boş metin döndürüp
    # kendiliğinden atlanıyor.
    index_all()
