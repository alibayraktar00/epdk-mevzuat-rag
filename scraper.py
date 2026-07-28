import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_document_links(page_url):
    """Sayfadaki belge linklerini toplar.

    EPDK gibi siteler belgeleri '.pdf' ile biten bir URL olarak değil,
    '/Detay/DownloadDocument?id=...' gibi bir indirme endpoint'i üzerinden
    sunuyor. Bu linklerin gerçek uzantısı URL'de görünmediği için, gövdeyi
    indirmeden sadece Content-Disposition başlığını okumak amacıyla HEAD
    isteği atılıyor.
    """
    resp = requests.get(page_url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    candidates = []
    seen = set()
    for a in soup.find_all("a", href=True):
        full_url = requests.compat.urljoin(page_url, a["href"])
        if full_url in seen:
            continue
        seen.add(full_url)
        if full_url.lower().endswith(".pdf") or "downloaddocument" in full_url.lower():
            candidates.append(full_url)

    links = []
    for url in candidates:
        if url.lower().endswith(".pdf"):
            links.append(url)
            continue
        try:
            head = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            disposition = head.headers.get("Content-Disposition", "")
            if ".pdf" in disposition.lower():
                links.append(url)
        except requests.RequestException:
            continue
    return links


def debug_all_links(page_url, limit=30):
    """Sayfadaki TÜM linkleri gösterir (debug/inceleme amaçlı)."""
    resp = requests.get(page_url, headers=HEADERS)
    print("Status code:", resp.status_code)
    soup = BeautifulSoup(resp.content, "html.parser")

    all_links = soup.find_all("a", href=True)
    print(f"Toplam link sayısı: {len(all_links)}")

    for a in all_links[:limit]:
        text = a.get_text(strip=True)
        print(f"{a['href']}  ->  metin: '{text}'")


def debug_search_links(page_url, keyword=None):
    """'.pdf' içeren linkleri ve metninde 'kanun' geçen linkleri filtreler."""
    resp = requests.get(page_url, headers=HEADERS)
    print("Status code:", resp.status_code)
    soup = BeautifulSoup(resp.content, "html.parser")

    all_links = soup.find_all("a", href=True)
    print(f"Toplam link sayısı: {len(all_links)}\n")

    print("=== '.pdf' İÇEREN LİNKLER (büyük/küçük harf fark etmez) ===")
    pdf_links = [a for a in all_links if "pdf" in a["href"].lower()]
    print(f"Bulunan: {len(pdf_links)}")
    for a in pdf_links[:20]:
        print(f"{a['href']}  ->  '{a.get_text(strip=True)}'")

    print("\n=== 'Kanun' METNİ İÇEREN LİNKLER ===")
    kanun_links = [a for a in all_links if "kanun" in a.get_text(strip=True).lower()]
    print(f"Bulunan: {len(kanun_links)}")
    for a in kanun_links[:10]:
        print(f"{a['href']}  ->  '{a.get_text(strip=True)}'")

    # İsteğe bağlı özel anahtar kelime araması
    if keyword:
        print(f"\n=== '{keyword}' METNİ İÇEREN LİNKLER ===")
        kw_links = [a for a in all_links if keyword.lower() in a.get_text(strip=True).lower()]
        print(f"Bulunan: {len(kw_links)}")
        for a in kw_links[:10]:
            print(f"{a['href']}  ->  '{a.get_text(strip=True)}'")


if __name__ == "__main__":
    url = "https://www.epdk.gov.tr/Detay/Icerik/23-2-3/elektrik-piyasasi"

    print("========== 1) TÜM LİNKLER (ilk 30) ==========")
    debug_all_links(url)

    print("\n========== 2) PDF VE KANUN ARAMASI ==========")
    debug_search_links(url)

    print("\n========== 3) SADECE .pdf/.doc/.docx İLE BİTEN LİNKLER ==========")
    links = get_document_links(url)
    print(f"Bulunan belge sayısı: {len(links)}")
    for link in links:
        print(link)
