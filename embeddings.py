"""Metinleri anlam vektörlerine (embedding) çevirir.

Kullanılan e5 ailesi modelleri metnin rolünü önek ile bekliyor: indekslenen
belge parçaları "passage: ", aranan soru "query: " ile başlamalı. Önek
verilmezse benzerlik skorları belirgin şekilde bozuluyor.
"""

import torch
from sentence_transformers import SentenceTransformer

from config import EMBED_MODEL_NAME

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model = SentenceTransformer(EMBED_MODEL_NAME, device=DEVICE)


def embed_passages(texts):
    prefixed = ["passage: " + t for t in texts]
    return model.encode(
        prefixed, normalize_embeddings=True, batch_size=32, show_progress_bar=False
    ).tolist()


def embed_query(text):
    return model.encode(
        ["query: " + text], normalize_embeddings=True
    ).tolist()
