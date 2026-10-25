# Ayikla 1.1 — sonuç ve ölçümler

25 Ekim 2026 · Windows 11 x64 · Python 3.12.10 · PySide6 6.12.0 · Pillow 12.3.0

**Teslim:** `dist\Ayikla\Ayikla.exe`, yanındaki `_internal\` ve `MasaustuKisayolu.ps1`. Klasörün tamamı birlikte taşınır; Python kurulumu gerekmez. Yerel git deposu, remote yok.

## V1 → V1.1 benchmark

300 çift: her JPEG **6000×4000, ortalama 8.303.674 bayt (8,30 MB)**; CR3'ler 70 KB yapay dosyalar. Dört sabit tohumlu RGB gürültü tabanı, 300 ayrı EXIF zamanı; dosya boyutunu şişirmek için dolgu kullanılmadı. Her açılış için ayrı çekim dizini; testler yalnızca `.tmp\benchmark\` içinde. Veri seti yaklaşık 2,5 GB ve tekrar ölçüm için korunuyor.

Aynı bilgisayar, 1440×960 / DPR 1, Qt offscreen, film şeridi kapalı. Açılış: klasör seçimi → ilk karenin tamamlanmış çizimi (3 örnek). Geçiş: yönlendirme → tamamlanmış çizim (20 örnek). “Önbelleksiz”, uygulama görüntü ön belleğinin boş olmasıdır; Windows disk ön belleği temizlenmedi. Paket açılışı ilk Qt boyama olayına kadar, 5 ayrı süreçle ölçüldü; her iki sürümde aynı küçük ölçüm kancası kullanıldı.

| Ölçüm | V1 | V1.1 | Hedef / sonuç |
|---|---:|---:|---|
| Klasör → ilk kare, medyan | 276,25 ms | 245,72 ms | <1500 ms ✓ |
| Ön yüklenmiş sonraki kare, medyan | 121,95 ms | **4,97 ms** | <80 ms ✓ |
| Ön yüklenmiş kare, P95 | 159,24 ms | **7,81 ms** | <80 ms ✓ |
| Önbelleksiz kare, medyan / P95 | 259,14 / 360,54 ms | 136,89 / 214,09 ms | Medyan %47 azaldı |
| snapshot(), medyan | 73,67 ms | <0,01 ms | Dosya sistemi taraması yok |
| Seç kararı, medyan | 88,26 ms | 26,26 ms | Günlük ve taşıma dahil |
| RAM: gezinme sonu / süreç tepesi | 84,57 / 103,23 MiB | 69,51 / 114,83 MiB | <600 MB ✓ |
| RAM: %100 zoom süreç tepesi | Yok | **163,44 MiB** | Yaklaşık 171 MB; hedef içinde |
| Paket açılışı, medyan / P95 | 1098,65 / 1548,85 ms | **213,39 / 227,34 ms** | Medyan %81 azaldı |
| Dağıtılan paket, disk boyutu | 45,33 MB, onefile | **65,78 MB, onedir** | Sıkıştırılmış exe ile açık klasör farklı |
| Açılmış runtime dosyaları | 113,05 MB, geçici çıkarım | **63,19 MB, kalıcı** | Yaklaşık %44 daha az |

RAM, Windows GetProcessMemoryInfo ile ölçülen çalışma kümesidir; süreç tepesi önceki açılış/geçişleri de içerir. Zoom yalnızca V1.1'de vardır. Dağıtım boyutu onedir'de büyür; çalışırken V1'in açtığı geçici runtime artık gerekmez. Son exe 2.587.758 bayttır; tek başına dağıtılmaz. Pakette Qt Core/Gui/Widgets ve qjpeg/qico/qwindows/qoffscreen vardır; WebEngine, QML, Quick, PDF, Network, SVG bağımlılıkları ve kullanılmayan yazılım OpenGL DLL'i çıkarıldı.

Ham sonuçlar: [V1](docs/benchmark/v1.json), [V1.1](docs/benchmark/v1.1.json), [V1 paket](docs/benchmark/v1-package.json), [V1.1 paket](docs/benchmark/v1.1-package.json), [veri seti](docs/benchmark/dataset.json).

## Çalışanlar ve doğrulama

**81 pytest testi geçti; önceki 44 testin tamamı korundu.** Yeni testler: indeksin tarama yapmadan güncellenmesi; Retry/çakışma taraması; bayt bazlı LRU; 2 ileri + 1 geri ön yükleme; ölçekli/yönlendirilmiş decode; tam çözünürlük ve pan; EXIF'i piksel çözmeden okuma; seri sınırları; film şeridi durumları/tıklama; solan bilgi ve bildirim; yardım; tur özeti/Explorer düğmesi; beş son klasör; pencere/tam ekran; Türkçe hatalar; kısayolda üzerine yazmama; yeniden paketlemede eski dosyaları koruma/geri dönme. [Test kaydı](docs/test-results.xml).

**Üretilen exe iki ayrı Qt arka ucunda geçti:** offscreen ve gerçek Windows eklentisi. Windows denemesinde pencere ekrana çıkarılmadı. Python ve proje kaynakları süreç arama yolundan çıkarıldı. Hızlı klavye akışındaki okuyucu/taşıma çakışması aynı dosyaya erişim kilidiyle giderildi. [Paket testi](docs/verification.json), [Windows eklentisi testi](docs/verification-windows.json).

**Güvenlik korunuyor:** Önce senkron günlük, sonra dosya işlemi. Hedefin üzerine atomik taşıma çağrısında da yazılmaz. Z tam yolları geri getirir; E ile kaldırılan kopyalar silinmeden `.ayikla_saklanan\` içine taşınır. `_red\` boşaltılmaz. Ayarlar ayrı, sona eklenen günlükte tutulur. Build de önceki paketi silmeden `.tmp\replaced-builds\` içine taşır.

**Görüntüler:** [Galeri](docs/gallery.png) · [%100 zoom](docs/zoom.png) · [EXIF](docs/info.png) · [Film şeridi](docs/filmstrip.png) · [Tur sonu](docs/end.png). Tamamı yapay 24 MP sahneyle, teslim edilen exe'den alındı.

## Sınırlar ve sonraki öneriler

Gerçek R50 çekimi, SD kart/harici disk hızı, monitör renk doğruluğu ve Lightroom/tablet senkronu denenmedi. Süreler bu bilgisayardaki başsız ölçümlerdir; Windows disk ön belleği ve sistem yükü kontrol edilmedi. CR3 çözülmez. Lens/çekim bilgisi eksikse “—”; saat yanlışsa seri ipucu da etkilenir. Seri ipucu, zaman sıralı ardışık kareler arasındaki ≤1 saniye farkını kullanır; grup arayüzü yoktur. EXIF paneli 1,5 s sonra soluklaşır, yardım okunabilmesi için açık kalır. Dışarıdan değişiklikler otomatik izlenmez; Yeniden dene ile taranır. Paket imzasızdır; başka Windows bilgisayarda denenmedi. Masaüstü kısayolu betiği yalnızca geçici test dizininde çalıştırıldı.

**Uygulanmadı:** Yıldız, XMP, bulanıklık tespiti, film taraması, sunucu arşivi ve seri gruplama arayüzü.

**Ek öneriler (yalnızca öneri):** Gerçek bir R50 çekimiyle kısa kabul testi; ICC/renk yönetimini kalibre monitörde kontrol; yüksek DPI/ikinci monitör testi; uzun gerçek çekimde bağımsız yedek ve günlük büyümesi denemesi.
