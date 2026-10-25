# Ayikla V1 — teslim raporu

25 Ekim 2026 · Windows x64 · Python 3.12.10 · PySide6 6.12.0 · PyInstaller 6.22.3

**Çalışanlar:** Tam ekran Türkçe galeri; klasör seçimi; EXIF yönü; arka planda önceki/sonraki JPEG ön yükleme; sayaçlar; JPG/CR3 çiftini seçme/eleme; tam dosya adını ve yolunu geri getiren Z; 2. turda düzenleme kopyası açma/kaldırma; CR3'süz fotoğraf rozeti. Son tur ve bakılan kare yeniden açılışta korunur.

**Güvenlik:** İki dosyanın hedefi de işlemden önce kontrol edilir. Windows taşıma çağrısı yarış durumunda da mevcut hedefin üzerine yazmaz. Günlük, dosyalara dokunmadan önce diske yazılıp senkronlanır; yarım işlem yeniden açılışta tamamlanır. Aynı çekime ikinci yazıcı kilitlenir. Bozuk günlük veya dışarıdan değişmiş dosya varsa işlem durur.

**Silme yok:** `_red\` boşaltılmaz. E ile kaldırılan ve Z ile geri alınan düzenleme kopyaları `.ayikla_saklanan\` altına taşınır. Yarım kalmış kopyalar da korunur. Bu ek klasör bilinçli olarak tutulur; geri alma için günlükle birlikte saklanmalıdır.

**Doğrulama:** `pytest`: **44 geçti**. Testler yalnızca proje içindeki `.tmp\` altında üretilen dosyaları kullandı. Kapsam: harf duyarsız eşleme, seç/ele/geri al, edit aç/kapat, yeniden açılış, eksik RAW, hedef çakışması ve yarış durumu, değişmiş kopya, sekiz EXIF yönü, klavye akışı, taşıma/kopyalama/geri almanın ortasında kesilme, günlük yazma hatası ve yarım günlük satırı onarımı.

Üretilen **`dist\Ayikla.exe`**, Python ve proje kaynakları arama yolundan çıkarılarak ayrıca çalıştırıldı: galeri, seç/ele, eksik RAW, Z, E, kopyayı silmeden kaldırma, günlüğü yeniden açma ve kalıcı geri alma geçti. Test başsız Qt ile yapıldı. Ayrıntı: [doğrulama kaydı](docs/verification.json), [arayüz görüntüsü](docs/arayuz.png).

**Paket:** Tek `.exe`, 45.325.045 bayt (~45,3 MB); Python kurulumu gerekmez. SHA-256:

```text
26684eff3b64533fd4e552256e5a986581b19e6862e71d29971bbb505ad42884
```

**Sınırlar:** Gerçek R50 fotoğrafları kullanılmadı; gerçek çekimde hız, monitör renk doğruluğu ve Lightroom/tablet akışı doğrulanmadı. CR3 içeriği çözülmez; dosya olarak taşınır/kopyalanır. Lightroom'a `02_edit\` içeri aktarma ve tablet senkronu kullanıcıya aittir. Alt klasörler taranmaz. Aynı gövde adına sahip birden fazla JPEG belirsizse klasör açılışı durur. Yerel Windows 10/11 x64 hedeflenir; başka Windows bilgisayarda denenmedi. Paket imzasızdır.

**Sonraki adımlar (uygulanmadı):** Seri/burst gruplama, yıldızlar, XMP, bulanıklık tespiti, film taramaları, ev sunucusuna arşivleme.

Tüm kaynak, bağımlılık ortamı, test dosyaları ve çıktılar `Ayikla\` içinde; bağımsız yerel git deposu, remote yok. Büyük geliştirme ortamı `.tools\`, geçici dosyalar `.tmp\` ve üretilen `dist\` git dışında tutulur; kaynaklar ve paketleme tarifi depodadır.
