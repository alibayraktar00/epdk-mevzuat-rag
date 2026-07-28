import re

import chromadb
import numpy as np

from config import CHROMA_DB_PATH, COLLECTION_NAME

client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
collection = client.get_or_create_collection(COLLECTION_NAME)

# Arşivde her yönetmeliğin çok sayıda versiyonu bulunduğu için en yakın
# parçalar çoğu zaman aynı maddenin farklı sürümleri oluyor. Bu ayarlar, aday
# havuzunu genişletip birbirine çok benzeyen parçaları eleyerek bağlamın
# gerçekten farklı bilgilerle dolmasını sağlıyor.
CANDIDATE_MULTIPLIER = 4
DUPLICATE_THRESHOLD = 0.95


def delete_document(content_id):
    """Bir belgenin tüm parçalarını indeksten siler.

    Yeniden indekslemede metin çıkarma değiştiyse belge daha az parçaya
    bölünebiliyor; upsert yalnızca aynı kimlikli kayıtları güncellediği için
    fazla kalan eski parçalar indekste kalıp aramaya karışıyordu.
    """
    collection.delete(where={"content_id": content_id})


def add_chunks(chunks, embeddings, metadata, ids):
    """Chunk'ları belgenin künyesiyle birlikte koleksiyona yazar.

    Aynı belge yeniden indekslenirse (ör. yarıda kalan çalışma) kayıtlar
    çoğalmasın diye add yerine upsert kullanılıyor.
    """
    collection.upsert(
        documents=chunks,
        embeddings=embeddings,
        metadatas=[dict(metadata) for _ in chunks],
        ids=ids,
    )


_DATE_PATTERN = re.compile(r"(\d{1,2})[.\-/](\d{1,2})[.\-/]((?:19|20)\d{2})")


def document_date(metadata):
    """Belgenin en yeni tarih işaretini (yıl, ay, gün) sırasıyla döner.

    Tarih üç yere dağılmış durumda: karar tarihi, Resmî Gazete tarihi ve bazen
    yalnızca başlık ("Son Versiyon 29.12.2025" gibi, date alanı boşken). Tek
    başına hiçbiri arşivin tamamını kapsamadığı, üçü birlikte kapsadığı için
    hepsi taranıp en yenisi alınıyor. Hiç tarih yoksa belge en eski sayılır.
    """
    best = (0, 0, 0)
    for field in ("date", "rg_date", "title"):
        for day, month, year in _DATE_PATTERN.findall(metadata.get(field) or ""):
            best = max(best, (int(year), int(month), int(day)))
    return best


def search(query_embedding, top_k=5):
    """Soruya en yakın parçaları, her metnin en güncel sürümüyle döner.

    Aynı mevzuatın yıllara yayılan sürümleri arşivde ayrı belgeler olarak
    duruyor ve metinleri neredeyse aynı olduğu için benzerlik sıralaması
    hangisinin öne geçeceğini rastgele belirliyor; bu da yürürlükten kalkmış
    bir hükmün güncelmiş gibi sunulmasına yol açıyordu. Bu yüzden birbirinin
    kopyası olan parçalarda tarihi en yeni olan tutuluyor.
    """
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=top_k * CANDIDATE_MULTIPLIER,
        include=["documents", "metadatas", "embeddings"],
    )
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    embeddings = np.asarray(results["embeddings"][0])

    picked_docs = []
    picked_metas = []
    picked_embs = []
    for doc, meta, emb in zip(documents, metadatas, embeddings, strict=True):
        # Kopya elemenin amacı, aynı mevzuatın farklı belgelerdeki neredeyse
        # aynı sürümlerini teke indirmek. Aynı belgenin (content_id) parçaları
        # ise metnin farklı bölümleri olduğundan kopya sayılmamalı; aksi halde
        # bitişik iki parçadan biri (ör. tam da aranan cümleyi içeren) yanlışlıkla
        # eleniyordu.
        duplicate_of = None
        for j, picked_emb in enumerate(picked_embs):
            if picked_metas[j]["content_id"] == meta["content_id"]:
                continue
            # Vektörler normalize olduğu için nokta çarpımı kosinüs benzerliği.
            if float(picked_emb @ emb) >= DUPLICATE_THRESHOLD:
                duplicate_of = j
                break

        if duplicate_of is not None:
            if document_date(meta) > document_date(picked_metas[duplicate_of]):
                picked_docs[duplicate_of] = doc
                picked_metas[duplicate_of] = meta
                picked_embs[duplicate_of] = emb
            continue

        picked_docs.append(doc)
        picked_metas.append(meta)
        picked_embs.append(emb)

    return picked_docs[:top_k], picked_metas[:top_k]


def count():
    return collection.count()
