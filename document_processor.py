"""Diskteki mevzuat belgelerinden düz metin çıkarır.

Arşivde altı ayrı format var (.doc/.docx/.pdf/.xls/.xlsx/.zip) ve her biri
farklı bir okuyucu gerektiriyor. extract_text() uzantıya bakıp doğru okuyucuya
yönlendirir; çağıran taraf formatı bilmek zorunda kalmaz.
"""

import os
import zipfile


def _extract_pdf(path):
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def _table_rows(table):
    """Tablo satırlarını "hücre | hücre" biçiminde üretir.

    İki ayrıntı önemli: birleştirilmiş hücreler python-docx'te kapsadıkları her
    sütun için tekrar döndüğünden başlık aynı satırda defalarca çıkıp değerleri
    parçanın dışına itiyor, bu yüzden ardışık tekrarlar ayıklanıyor. Ayrıca
    hücreler arasına görünür bir ayraç konuyor; düz metne çevrilmiş tabloda
    hangi değerin hangi açıklamaya ait olduğu ancak böyle ayırt edilebiliyor.
    """
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = " ".join(cell.text.split())
            if text and (not cells or cells[-1] != text):
                cells.append(text)
        if cells:
            yield " | ".join(cells)


def _extract_docx(path):
    import docx
    document = docx.Document(path)
    parts = [p.text for p in document.paragraphs]
    # Mevzuatta tarife/bedel bilgisi çoğunlukla tabloda duruyor, atlanmamalı.
    for table in document.tables:
        parts.extend(_table_rows(table))
    return "\n".join(parts)


def _extract_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    lines = []
    for sheet in wb.worksheets:
        lines.append(f"[Sayfa: {sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
    wb.close()
    return "\n".join(lines)


def _extract_xls(path):
    import xlrd
    book = xlrd.open_workbook(path)
    lines = []
    for sheet in book.sheets():
        lines.append(f"[Sayfa: {sheet.name}]")
        for r in range(sheet.nrows):
            cells = [str(c) for c in sheet.row_values(r) if str(c).strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_zip(path):
    """Arşivin içindeki desteklenen dosyaları açıp metinlerini birleştirir."""
    parts = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            ext = os.path.splitext(name)[1].lower()
            if ext not in EXTRACTORS or ext == ".zip":
                continue
            # Okuyucuların çoğu dosya yolu beklediği için geçici dosyaya yazılıyor.
            tmp = os.path.join(TEMP_DIR, os.path.basename(name))
            os.makedirs(TEMP_DIR, exist_ok=True)
            with open(tmp, "wb") as f:
                f.write(zf.read(name))
            # Arşivdeki tek bir bozuk dosya, kalanların çıkarılmasını engellememeli.
            # noinspection PyBroadException
            try:
                parts.append(EXTRACTORS[ext](tmp))
            except Exception:
                pass
            finally:
                os.remove(tmp)
    return "\n".join(parts)


def _extract_doc(path):
    """Eski .doc için doc_converter'ın ürettiği metin dosyasını okur.

    Dönüşüm Word otomasyonu gerektirdiğinden burada değil, önceden toplu olarak
    yapılıyor; karşılığı yoksa belge sessizce atlanır.
    """
    from doc_converter import txt_path_for
    txt = txt_path_for(path)
    if not os.path.exists(txt):
        return ""
    with open(txt, encoding="utf-8", errors="replace") as f:
        return f.read()


TEMP_DIR = "data/_tmp"

EXTRACTORS = {
    ".pdf": _extract_pdf,
    ".docx": _extract_docx,
    ".doc": _extract_doc,
    ".xlsx": _extract_xlsx,
    ".xls": _extract_xls,
    ".zip": _extract_zip,
}


def extract_text(path):
    """Belgeden düz metni döner; format desteklenmiyorsa boş dize."""
    ext = os.path.splitext(path)[1].lower()
    extractor = EXTRACTORS.get(ext)
    if not extractor:
        return ""
    return extractor(path)


def chunk_text(text, chunk_size=500, overlap=50):
    """Metni parçalara böler; kesim noktasını sayı/kelime ortasına denk getirmez.

    Sabit karakter sayısında kesmek "2.161" gibi bir tutarı "2.1" ve "61" diye
    ikiye bölebiliyor ve model rakamı yanlış okuyordu. Tablolar satır bazlı
    çıkarıldığı için (her satır "açıklama | değer") kesim tercihen satır sonuna,
    o yoksa boşluğa çekiliyor; böylece satır ve içindeki değer bütün kalıyor.
    """
    chunks = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            # En az yarıya kadar dolduktan sonraki ilk uygun sınıra çekil.
            floor = start + chunk_size // 2
            cut = text.rfind("\n", floor, end)
            if cut == -1:
                cut = text.rfind(" ", floor, end)
            if cut != -1:
                end = cut
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        # İlerlemeyi garantiye alarak (en az yarım parça) overlap uygula.
        start = max(end - overlap, start + chunk_size // 2)
    return chunks
