"""Aday parçaları soruyla olan gerçek alakalarına göre yeniden sıralar.

Embedding araması soruyu ve parçaları ayrı ayrı vektöre çevirip karşılaştırıyor;
bu hızlı ama kaba. Reranker (cross-encoder) soru ile parçayı birlikte okuyup tek
bir alaka puanı üretiyor, bu yüzden "yönetmeliğin amacı" ile "yönetmeliğin
şartları" gibi konusu aynı ama sorulana cevabı farklı metinleri ayırt edebiliyor.

GPU'da sıralama CPU'ya göre ~16 kat hızlı, ancak VRAM'i embedding modeli ve
Ollama'daki LLM ile paylaşmak zorunda; LLM modelini bir süre bellekte tuttuğu
için GPU'da her zaman yer bulunmuyor. Bu yüzden önce GPU deneniyor, bellek
yetmezse sessizce CPU'ya düşülüyor: yavaş ama çalışır.
"""

import torch
from sentence_transformers import CrossEncoder

from config import RERANK_MODEL_NAME

_models = {}


def _get_model(device):
    if device not in _models:
        _models[device] = CrossEncoder(RERANK_MODEL_NAME, device=device, max_length=512)
    return _models[device]


def _score(question, chunks):
    pairs = [(question, c) for c in chunks]
    if torch.cuda.is_available():
        try:
            return _get_model("cuda").predict(pairs)
        except torch.cuda.OutOfMemoryError:
            # GPU'daki yarım kalan tahsisler bırakılmazsa CPU'ya düşsek bile
            # bellek boşa tutulmuş oluyor.
            _models.pop("cuda", None)
            torch.cuda.empty_cache()
    return _get_model("cpu").predict(pairs)


def rerank(question, chunks, metadatas, top_k):
    """Parçaları alaka puanına göre sıralayıp en iyi top_k tanesini döner."""
    if not chunks:
        return chunks, metadatas

    scores = _score(question, chunks)
    order = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)[:top_k]
    return [chunks[i] for i in order], [metadatas[i] for i in order]
