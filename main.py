"""EPDK elektrik mevzuatı soru-cevap arayüzü."""

import io
import re
import sys

from config import USE_RERANKER
from embeddings import embed_query
from vector_store import search, count, document_date
from llm import generate_answer

# LLM'e verilecek parça sayısı.
TOP_K = 5
# Reranker'a sunulan aday havuzu; seçim yapabilirsin diye TOP_K'dan geniş.
CANDIDATE_K = 20

_CITATION = re.compile(r"\[\d+\]")
_NUMBER = re.compile(r"\d[\d.,]*")


def ask(question, top_k=TOP_K):
    q_embedding = embed_query(question)
    if USE_RERANKER:
        chunks, metadatas = search(q_embedding, top_k=CANDIDATE_K)
        # Reranker ağır bir model; kapalıyken hiç yüklenmemesi için içeride
        # import ediliyor.
        from reranker import rerank
        chunks, metadatas = rerank(question, chunks, metadatas, top_k)
    else:
        chunks, metadatas = search(q_embedding, top_k=top_k)
    answer = generate_answer(question, chunks, metadatas)
    return answer, chunks, metadatas


def format_date(metadata):
    year, month, day = document_date(metadata)
    return f"{day:02d}.{month:02d}.{year}" if year else "tarihsiz"


def excerpt_for(chunk, answer, width=200):
    """Parçadan, cevabı doğrulamaya yarayan satırı seçer.

    Model tablodaki rakamı yanlış okuyabildiği için cevapla birlikte kaynağın
    ham satırı da gösteriliyor. Cevapta geçen bir sayıyı içeren satır varsa o,
    yoksa parçanın ilk satırı veriliyor.
    """
    lines = [" ".join(line.split()) for line in chunk.splitlines() if line.strip()]
    if not lines:
        return ""

    numbers = {n for n in _NUMBER.findall(_CITATION.sub("", answer)) if len(n) > 1}
    for line in lines:
        if any(number in line for number in numbers):
            return line[:width]
    return lines[0][:width]


def print_sources(chunks, metadatas, answer):
    print("\nKaynaklar:")
    for i, (chunk, metadata) in enumerate(zip(chunks, metadatas, strict=True), 1):
        print(f"  [{i}] {metadata.get('title', '')} ({format_date(metadata)})")
        excerpt = excerpt_for(chunk, answer)
        if excerpt:
            print(f"      “{excerpt}”")
        if metadata.get("source_url"):
            print(f"      {metadata['source_url']}")


def repl():
    # Windows konsolu varsayılan kod sayfasında Türkçe karakterleri bozuyor.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    print(f"EPDK elektrik mevzuatı botu. İndekste {count()} parça var.")
    print("Tutar ve tarifelerde cevabın altındaki alıntıdan rakamı doğrulayın.")
    print("Çıkmak için boş satır ya da Ctrl+C.\n")

    first = True
    while True:
        try:
            question = input("Soru: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            break

        if first:
            # Modeller ilk soruda yükleniyor; uyarı olmadan donmuş gibi görünüyor.
            print("(modeller yükleniyor, ilk cevap biraz sürebilir...)")
            first = False

        answer, chunks, metadatas = ask(question)
        print(f"\n{answer}")
        print_sources(chunks, metadatas, answer)
        print()

    print("Görüşürüz.")


if __name__ == "__main__":
    repl()
