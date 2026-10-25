# Ayikla

Canon RAW+JPEG çekimlerini iki turda ayıklar. **Windows x64 · Python 3.12 · PySide6.**

**Başlat:** `dist\Ayikla.exe` dosyasına çift tıkla, **Çekim klasörü seç**. Python kurulumu gerekmez. Uygulama tam ekran açılır; F11 veya Esc ile pencereye dönülür.

| Tuş | İşlev |
|---|---|
| → / Enter | 1. tur: seç; JPG + eşleşen CR3 → `01_secilen\` |
| ← / X | 1. tur: ele; çift → `_red\` |
| Boşluk / ↓ | Karar vermeden sonraki fotoğraf |
| ↑ | Karar vermeden önceki fotoğraf |
| Z | Son kararı geri al; uygulama kapandıktan sonra da çalışır |
| M | 1. tur / 2. tur arasında geçiş |
| E | 2. tur: JPG + varsa CR3 → `02_edit\` kopyala; tekrar E ile seçimi kaldır |
| Ctrl+O | Başka çekim klasörü aç |
| F11 / Esc | Tam ekranı değiştir / pencereye dön |

`02_edit\` içeriğini Lightroom Classic'e içe aktar. 1. tur yalnızca henüz karar verilmemiş JPEG'leri, 2. tur `01_secilen\` içindekileri gösterir. CR3'süz JPEG de işlenir; sarı rozetle belirtilir. Alt klasörler taranmaz; `.JPG` ve `.JPEG` desteklenir. Eşleşme aynı klasörde, dosya gövde adına göre ve harf duyarsız yapılır.

**Dosya güvenliği:** Üzerine yazılmaz, hiçbir fotoğraf silinmez; `_red\` boşaltılmaz. E ile kaldırılan veya Z ile geri alınan düzenleme kopyaları `.ayikla_saklanan\` içinde saklanır. Bu klasör zamanla büyüyebilir. `ayikla_log.jsonl` kararları, tam dosya yollarını ve son bakılan kareyi tutar; taşımalar yarıda kalırsa bir sonraki açılışta tamamlanır. Günlüğü ve `.ayikla_saklanan\` klasörünü sakla. Hedef çakışması varsa dosyalar korunur; çakışmayı giderip **Yeniden dene** veya klasörü yeniden aç. Günlük yazma hatasında uygulamayı yeniden başlat.

Geliştirme (PowerShell, proje klasöründe):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\run.ps1
.\.venv\Scripts\python.exe -m pytest --basetemp .tmp\pytest-local -q
.\build.ps1
.\.venv\Scripts\python.exe scripts\verify_frozen.py
```

Bu bilgisayarda proje içindeki `.tools\python312\tools\python.exe` de hazırdır; `run.ps1` ve `build.ps1` bunu otomatik bulur. Build `dist\Ayikla.exe` üretir. Kaynak/testler yerel git deposundadır; remote yoktur.

Paket doğrulaması yalnızca `.tmp\` altında yeni, yapay çekim oluşturur; sonucu `docs\verification.json` içine yazar. Pillow yalnızca test görselleri ve EXIF örnekleri üretmek için kullanılır; uygulamaya dahil değildir.

