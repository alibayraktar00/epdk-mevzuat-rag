import csv
import os
import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

MEVZUAT_URL = "https://www.epdk.gov.tr/Detay/Icerik/23-2-3/mevzuat"
FAST_ACCESS_URL = "https://www.epdk.gov.tr/Detay/GetFastAccessList"
DOWNLOAD_URL = "https://www.epdk.gov.tr/Detay/DownloadDocument"

DOCS_DIR = "data/docs"
DATASET_CSV = "data/mevzuat_dataset.csv"

FIELDNAMES = [
    "content_id", "title", "category", "date", "rg_date", "rg_number",
    "number", "source_url", "local_path",
]

# Sunucu bu belgeler için HEAD isteğine boyut bildiriyor ama GET'te gövdeyi hiç
# göndermiyor; EPDK tarafındaki bir sorun ve istemciden çözülemiyor. Her
# çalıştırmada tekrar denemek boşuna zaman kaybı olduğu için atlanıyorlar.
BROKEN_CONTENT_IDS = {
    "Nl7xFguusHk=", "MG3yEvYZTuE=", "c1yGRv23hWA=", "vMgtJnhrktg=",
    "h+ynHaMdrVc=", "T9zFQIukjuo=", "U5WfM/H8bj8=",
}


def get_category_nodes(page_url=MEVZUAT_URL):
    """Mevzuat sayfasındaki akordiyon ağacında data-id taşıyan tüm düğümleri döner."""
    resp = requests.get(page_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")

    nodes = []
    for li in soup.select("ul.text-liste li.accordion-pop"):
        a = li.find("a", attrs={"data-id": True})
        if not a:
            continue
        fid = a["data-id"]
        title = a.get_text(strip=True)
        nodes.append((fid, title))
    return nodes


def request_with_retry(method, url, attempts=4, **kwargs):
    """Geçici ağ hatalarında (timeout vb.) artan bekleme ile tekrar dener."""
    last_error = None
    for attempt in range(attempts):
        try:
            resp = requests.request(method, url, headers=HEADERS, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_error = e
            time.sleep(2 * (attempt + 1))
    raise last_error


def get_documents_for_node(fid, category_title):
    """Bir kategori düğümü için gerçek belge listesini (metadata dahil) döner."""
    resp = request_with_retry(
        "POST", FAST_ACCESS_URL, timeout=30, json={"fId": fid},
    )
    data = resp.json()

    docs = []
    for item in data.get("model") or []:
        for detail in item.get("FastAccessDetail") or []:
            if not detail.get("IsFileType"):
                continue
            docs.append({
                "content_id": detail["ContentId"],
                "title": detail.get("Title") or item.get("Title") or category_title,
                "category": category_title,
                "date": item.get("Date", ""),
                "rg_date": item.get("RgDate", ""),
                "rg_number": item.get("RgNumber", ""),
                "number": item.get("Number", ""),
            })
    return docs


def sanitize_filename(content_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", content_id)


def guess_extension(resp, fallback_title=""):
    disposition = resp.headers.get("Content-Disposition", "")
    m = re.search(r"\.([A-Za-z0-9]{2,5})\"?\s*$", disposition.strip())
    if m:
        return "." + m.group(1).lower()
    m = re.search(r"\.([A-Za-z0-9]{2,5})$", fallback_title.strip())
    if m:
        return "." + m.group(1).lower()
    return ".pdf"


def download_document(content_id, title=""):
    """Belgeyi parça parça (streaming) indirir.

    Bazı belgeler gövdesi yavaş aktığı için tek parça indirmede zaman aşımına
    uğruyor; streaming'de zaman aşımı tüm gövdeye değil her parçaya işlediği
    için bu belgeler de inebiliyor.
    """
    source_url = f"{DOWNLOAD_URL}?id={content_id}"
    resp = request_with_retry("GET", source_url, timeout=(15, 60), stream=True)
    content = b"".join(resp.iter_content(chunk_size=65536))
    ext = guess_extension(resp, title)
    return content, source_url, ext


def load_existing_ids(csv_path):
    if not os.path.exists(csv_path):
        return set()
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return {row["content_id"] for row in csv.DictReader(f)}


def run(limit_nodes=None, sleep_between=0.1):
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DATASET_CSV), exist_ok=True)

    existing_ids = load_existing_ids(DATASET_CSV)
    write_header = not os.path.exists(DATASET_CSV)

    nodes = get_category_nodes()
    if limit_nodes:
        nodes = nodes[:limit_nodes]
    print(f"{len(nodes)} kategori bulundu.")

    with open(DATASET_CSV, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()

        seen_ids = set(existing_ids)
        new_count = 0
        for fid, category_title in nodes:
            try:
                docs = get_documents_for_node(fid, category_title)
            except requests.RequestException as e:
                print(f"HATA (kategori {fid}): {e}")
                continue

            for doc in docs:
                cid = doc["content_id"]
                if cid in seen_ids or cid in BROKEN_CONTENT_IDS:
                    continue
                seen_ids.add(cid)

                try:
                    content, source_url, ext = download_document(cid, doc["title"])
                except requests.RequestException as e:
                    print(f"HATA (belge {cid}): {e}")
                    continue

                local_path = os.path.join(DOCS_DIR, sanitize_filename(cid) + ext)
                with open(local_path, "wb") as pdf_file:
                    pdf_file.write(content)

                doc["source_url"] = source_url
                doc["local_path"] = local_path
                writer.writerow(doc)
                new_count += 1
                print(f"indirildi: {doc['title']} -> {local_path}")

            time.sleep(sleep_between)

    print(f"Bitti. Yeni indirilen belge sayısı: {new_count}")


if __name__ == "__main__":
    run()
