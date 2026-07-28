import contextlib
import csv
import os

DOC_TXT_DIR = "data/doc_txt"
DATASET_CSV = "data/mevzuat_dataset.csv"

# msoAutomationSecurityForceDisable: otomasyonla açılan belgelerde makroları
# uyarı göstermeden tamamen kapatır.
MSO_AUTOMATION_SECURITY_FORCE_DISABLE = 3


def txt_path_for(doc_path):
    """Bir .doc dosyasının dönüştürülmüş metin karşılığının yolunu verir."""
    base = os.path.splitext(os.path.basename(doc_path))[0]
    return os.path.join(DOC_TXT_DIR, base + ".txt")


def convert_all(limit=None):
    import pythoncom
    import win32com.client

    os.makedirs(DOC_TXT_DIR, exist_ok=True)

    with open(DATASET_CSV, newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f)
                if r["local_path"].lower().endswith(".doc")]

    todo = []
    for row in rows:
        out = txt_path_for(row["local_path"])
        if not os.path.exists(out):
            todo.append((row, out))

    if limit:
        todo = todo[:limit]

    print(f"{len(rows)} .doc dosyası, {len(todo)} dönüştürülecek.")

    pythoncom.CoInitialize()
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    # Bozuk dosyalarda Word diyalog açarsa script süresiz beklerdi.
    word.DisplayAlerts = False
    # Belgeler internetten indirildi ve otomasyonla açılıyor; içlerindeki makro
    # kodunun çalışmaması için makrolar tamamen devre dışı bırakılıyor.
    word.AutomationSecurity = MSO_AUTOMATION_SECURITY_FORCE_DISABLE

    ok = 0
    failed = 0
    try:
        for i, (row, out) in enumerate(todo, 1):
            src = os.path.abspath(row["local_path"])
            doc = None
            try:
                doc = word.Documents.Open(
                    src, ReadOnly=True, AddToRecentFiles=False,
                    ConfirmConversions=False, Visible=False,
                )
                # Word'e kaydettirmek yerine metni COM üzerinden okuyoruz:
                # SaveAs2 bir kısım belgede hata veriyor, ayrıca COM metni
                # doğrudan Unicode döndürdüğü için kod sayfası kaybı olmuyor.
                text = doc.Content.Text
                with open(out, "w", encoding="utf-8") as f:
                    f.write(text)
                ok += 1
            except Exception as e:
                failed += 1
                print(f"  HATA {type(e).__name__}: {os.path.basename(src)}")
            finally:
                if doc is not None:
                    # Temizlik: kapatma başarısız olsa da işi durdurmamalı.
                    with contextlib.suppress(Exception):
                        doc.Close(SaveChanges=False)

            if i % 50 == 0:
                print(f"[{i}/{len(todo)}] başarılı={ok} hatalı={failed}")
    finally:
        # Temizlik: Word kapanmasa da programı çökertmemeli.
        with contextlib.suppress(Exception):
            word.Quit()
        pythoncom.CoUninitialize()

    print(f"\nBitti. Dönüştürülen: {ok} | Hatalı: {failed}")


if __name__ == "__main__":
    convert_all()
