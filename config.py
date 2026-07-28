EMBED_MODEL_NAME = "intfloat/multilingual-e5-large"
# Metni "anlam vektörüne" (sayı dizisi) çeviren model.
# Soru ile belgeleri aynı dile çevirip benzerliklerini ölçmek için kullanılıyor.
# multilingual = çok dilli, Türkçe'yi anlıyor.
USE_RERANKER = True
RERANK_MODEL_NAME = "BAAI/bge-reranker-v2-m3"
#Yeniden sıralayıcı.
# Aramanın getirdiği 20 adayı, soruyla gerçek alaka düzeyine göre yeniden diziyor.
LLM_MODEL_NAME = "qwen2.5:7b"
CHROMA_DB_PATH = "./chroma_db"
COLLECTION_NAME = "elektrik_piyasasi"
# Mevzuatta bir madde çoğunlukla 500 karakterden uzun; küçük parçalar maddeyi
# ortadan bölüp bağlamı bozuyor. e5 modeli 512 token (Türkçe'de ~1500-2000
# karakter) alabildiği için parça boyu buna yaklaştırıldı.
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
BASE_URL = "https://www.epdk.gov.tr/Detay/Icerik/23-2-3/elektrik-piyasasi"
