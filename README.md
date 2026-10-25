# Ayikla 1.1

Canon RAW+JPEG çekimlerini iki turda ayıklar. **Windows x64 · Python 3.12 · PySide6.**

**Başlat:** `dist\Ayikla\Ayikla.exe`. Python kurulumu gerekmez. **Ayikla klasörünü içindeki `_internal\` ile birlikte taşı; exe tek başına çalışmaz.** Çekim klasörünü seç veya açılıştaki son beş klasörden birine tıkla. Pencere/tam ekran durumu hatırlanır.

Masaüstü kısayolu için proje kökünde çalıştır (mevcut kısayolun üzerine yazmaz):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\dist\Ayikla\MasaustuKisayolu.ps1"
```

| Tuş | İşlev |
|---|---|
| → / Enter | 1. tur: **Sakla**; JPG + varsa CR3 → `01_secilen\` |
| ← / X / Delete | 1. tur: **Ele**; çift → `_red\`, Z ile geri alınabilir; dosya silinmez |
| Boşluk / ↓ | Karar vermeden sonraki kare; 2. turun sonunda özet |
| ↑ | Karar vermeden önceki kare |
| Z | Son kararı geri al; uygulama yeniden açılınca da çalışır |
| M | 1. tur / 2. tur arasında geçiş |
| E | 2. tur: JPG + CR3'ü `02_edit\` içine kopyala; tekrar E ile seçimi kaldır |
| F | %100 odak kontrolü / ekrana sığdır |
| Sol tuşla sürükle | %100 görünümde kaydır |
| I | Dosya adı, çekim saati, enstantane, diyafram, ISO, odak uzaklığı ve lens |
| T | Film şeridini göster/gizle; küçük fotoğrafa tıklayarak git |
| H / ? | Klavye yardımını göster/gizle |
| Ctrl+O | Başka çekim klasörü aç |
| F11 | Tam ekranı değiştir |
| Esc | Önce yardımı, sonra yakınlaştırmayı kapat; ardından pencereye dön |

**Neyi seçiyorum?** 1. turda **saklanacak fotoğrafları** ayırırsın: Sakla → `01_secilen\`, Ele / Delete → `_red\`. M ile 2. tura geçip sakladıklarının arasından **edit / Lightroom için olanları** E ile `02_edit\` içine kopyalarsın. Kararlar anında günlüğe kaydedilir; ayrıca Kaydet düğmesine basman gerekmez. Delete, 1. turdaki Ele kısayoludur.

Film şeridi: **yeşil = seçilen, kırmızı = elenen, mor = edit seçimi**. Elenen kare yalnızca önizlenir; karar tuşları devre dışıdır. EXIF saatleri ardışık olarak en fazla 1 saniye aralıktaysa **Seri 2/5** ipucu görünür. EXIF yoksa alanlar “—” olur.

Seri/zoom etiketi ve işlem bildirimi 1,5 saniye sonra solar. Bilgi paneli soluklaşır; I veya fare hareketiyle yeniden belirginleşir. Yardım açık kalır. Normal görünüm ve küçük fotoğraflar ölçekli çözülür; tam çözünürlük yalnızca F ile yüklenir.

Tur sonunda sayılar, **2. tura geç** ve **02_edit klasörünü Explorer'da aç** düğmeleri görünür. Lightroom Classic'e `02_edit\` içeriğini kendin içe aktar. CR3'süz JPEG uyarı rozetiyle işlenir. Alt klasörler taranmaz; JPG/JPEG ve harf duyarsız CR3 eşlemesi desteklenir.

`._*`, `Thumbs.db`, `desktop.ini`, `.DS_Store` ve Windows gizli/sistem dosyaları taramada yok sayılır; sayılmaz, gösterilmez, taşınmaz veya kopyalanmaz. Açılışta yok sayılanların sayısı küçük bir satırda görünür. Açılamayan gerçek JPEG'i yine Enter ile seçebilir, X ile eleyebilirsin; bu oturumda açılamayan dosyalar tur özetinde güncel yollarıyla listelenir.

**Dosya güvenliği:** Fotoğraf silinmez, üzerine yazılmaz; `_red\` boşaltılmaz. Kaldırılan edit kopyaları `.ayikla_saklanan\` içine taşınır. Bu klasörü ve `ayikla_log.jsonl` günlüğünü sakla. İşlem önce günlüğe yazılır; yarıda kalırsa açılışta tamamlanır. **Yeniden dene** yarım işlemi tamamlar ve klasörü yeniden tarar; dışarıdan eklenen dosyalar için de bu düğmeyi kullan. Günlük yazma hatasında disk sorununu giderip uygulamayı yeniden aç.

Son klasörler ve pencere ayarı ayrı, yalnızca sona eklenen `ayikla_settings.jsonl` dosyasında tutulur: exe yanında; Python ile çalıştırırken proje kökünde.

Geliştirme (PowerShell, proje kökünde):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\run.ps1
.\.venv\Scripts\python.exe -m pytest --basetemp .tmp\pytest-local -q
.\build.ps1
.\.venv\Scripts\python.exe scripts\verify_frozen.py
```

Bu bilgisayarda `.tools\python312\tools\python.exe` de hazırdır; betikler otomatik bulur. Build önce yeni bir klasör oluşturur; önceki paketi silmeden `.tmp\replaced-builds\` içine taşır ve taşınabilir ayarını yeni pakete kopyalar. Yerel git deposu, remote yok.

Ölçümleri tekrarlamak için `scripts\benchmark.py generate`, ardından `measure <etiket>` ve `startup <etiket> <exe-yolu>` kullan. Generate yalnızca proje içindeki `.tmp\benchmark\` altında yaklaşık 2,5 GB yapay veri üretir. [Ölçümler ve sınırlar](RAPOR.md).
