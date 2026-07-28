import ollama

from config import LLM_MODEL_NAME

SYSTEM_PROMPT = """Sen EPDK elektrik piyasası mevzuatı konusunda yardımcı olan bir asistansın.
Sadece sana verilen belge parçalarına dayanarak cevap ver.

Kurallar:
- Cevabı belgelerde bulamıyorsan "Bu bilgi elimdeki belgelerde yok." de. Tahmin yürütme.
- Mevzuat sorularında tarih ve sayı önemlidir; belgede geçiyorsa yaz.
- Belgeler aynı konuda farklı şeyler söylüyorsa tarihi en yeni olanı esas al ve
  cevabında hangi tarihli düzenlemeye dayandığını belirt.
- Metinde "Mülga" (yürürlükten kaldırılmış) diye işaretlenmiş bir hükmü yürürlükteymiş
  gibi aktarma.
- Tutarları belgede yazdığı gibi aktar, rakam üretme. Tablolar düz metne
  çevrildiğinden bir satırda birden çok "açıklama | değer" yan yana gelebiliyor;
  değeri hemen solundaki açıklamayla eşleştir ve hangi aralığa ait olduğunu yaz.
- Cevabın sonunda hangi belgeye dayandığını [1], [2] şeklinde belirt.
- Aynı bilgiyi tekrar etme, tek seferde cevapla.
- Türkçe cevap ver."""


def build_context(chunks, metadatas):
    """Belge parçalarını kaynak numarasıyla birlikte tek metne dönüştürür."""
    parts = []
    for i, (chunk, meta) in enumerate(zip(chunks, metadatas, strict=True), 1):
        baslik = meta.get("title", "")
        kategori = meta.get("category", "")
        tarih = meta.get("date", "")
        rg = meta.get("rg_number", "")
        künye = f"[{i}] {baslik} | {kategori}"
        if tarih:
            künye += f" | Tarih: {tarih}"
        if rg:
            künye += f" | RG Sayı: {rg}"
        parts.append(f"{künye}\n{chunk}")
    return "\n\n---\n\n".join(parts)


def generate_answer(question, chunks, metadatas, model=LLM_MODEL_NAME):
    context = build_context(chunks, metadatas)
    prompt = f"""Belgeler:

{context}

Soru: {question}"""

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response["message"]["content"]
