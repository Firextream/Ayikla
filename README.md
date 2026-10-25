# Ayikla

**İyi kareleri ayır. Seçkini hazırla.**

Canon RAW+JPEG çekimleri için sade, klavyeyle kullanılan bir Windows fotoğraf ayıklama uygulaması. Önce saklanacak kareleri, sonra Lightroom'da düzenlenecekleri seç.

**Windows x64 · Türkçe arayüz · Canon JPG/JPEG + CR3 · 1.1.1b1 Beta**

### [Windows için indir · ZIP, 26,6 MB](https://github.com/Firextream/Ayikla/releases/download/v1.1.1b1/Ayikla-1.1.1b1-Windows-x64.zip)

[Sürüm notları](https://github.com/Firextream/Ayikla/releases/tag/v1.1.1b1) · [Kullanım yorumu bırak](https://github.com/Firextream/Ayikla/issues/new?template=feedback.md) · [Hata bildir](https://github.com/Firextream/Ayikla/issues/new?template=bug_report.md)

![Ayikla galerisi: nötr koyu arayüz, geniş fotoğraf alanı ve Sakla / Ele düğmeleri](docs/gallery.png)

*Ekran görüntülerindeki fotoğraflar test için üretilmiştir; gerçek çekim içermez.*

## İlk kullanım

1. Yukarıdaki **Windows için indir** bağlantısından ZIP'i indir ve tamamını bir klasöre çıkar. GitHub'ın “Source code” ZIP'i çalıştırılabilir uygulama değildir.
2. `Ayikla` klasörünün içindeki `Ayikla.exe` dosyasını aç. **Python kurulumu gerekmez; `_internal` klasörü exe'nin yanında kalmalı.**
3. **Klasör aç** ile doğrudan JPG'lerin bulunduğu çekim klasörünü seç. İlk beta denemesini 20–50 çiftin ayrı bir kopyasıyla yap.

Paket imzasızdır; Windows uyarısı çıkabilir. Açılmazsa güvenlik yazılımını kapatmak yerine uyarı metniyle [hata bildir](https://github.com/Firextream/Ayikla/issues/new?template=bug_report.md). İsteğe bağlı masaüstü kısayolu için paketteki `MasaustuKisayolu.ps1` betiği kullanılabilir; mevcut kısayolun üzerine yazmaz.

## Saklamak mı, edit için seçmek mi?

| Tur | Amaç | Dosyalara ne olur? |
|---|---|---|
| **1 · Sakla / Ele** | Hangi kareler saklanacak? | Sakla → `01_secilen`; Ele / Delete → `_red`. JPG ve varsa CR3 birlikte taşınır. |
| **2 · Edit / Lightroom** | Saklananlardan hangileri düzenlenecek? | M ile geç, E ile seç → `02_edit` içine JPG+CR3 **kopyalanır**. |

**Delete kalıcı silmez.** Z son kararı geri alır; uygulamayı kapatıp açtıktan sonra da çalışır. Kararlar anında günlüğe yazılır, ayrıca Kaydet düğmesi yoktur. Lightroom Classic'e `02_edit` içeriğini kendin aktarırsın.

## Klavye

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

## Fotoğrafı incele, dosyaya ulaş

**Dosyalara erişim:** Üstteki **Klasörler** menüsünden çekim klasörünü, **Saklananlar / 01_secilen**, **Edit seçimi / 02_edit** ve **Elenenler / _red** klasörlerini Explorer'da açabilirsin. Menüde güncel adetler görünür. Fotoğrafın altındaki **Klasörde aç ↗** o karenin bulunduğu klasörü açar. Tur sonundaki Saklananlar/Elenenler bağlantıları da aynı işi yapar. Uzun dosya adı kısalır; tam adı fareyi üzerine getirince görünür.

Film şeridi: **yeşil = seçilen, kırmızı = elenen, mor = edit seçimi**. Elenen kare yalnızca önizlenir; karar tuşları devre dışıdır. EXIF saatleri ardışık olarak en fazla 1 saniye aralıktaysa **Seri 2/5** ipucu görünür. EXIF yoksa alanlar “—” olur.

F ile %100 odak kontrolü ve sürükleyerek kaydırma; I ile çekim bilgisi; T ile film şeridi. Normal görünüm ve küçük fotoğraflar ölçekli çözülür; tam çözünürlük yalnızca F ile yüklenir. Son beş klasör ve pencere/tam ekran durumu hatırlanır.

<details>
<summary>Yakınlaştırma, EXIF, film şeridi ve tur sonunu gör</summary>

**%100 odak kontrolü**

![Yüzde yüz yakınlaştırma ve odak kontrolü](docs/zoom.png)

**Çekim bilgileri**

![EXIF bilgi paneli](docs/info.png)

**Film şeridi**

![Durum renkleriyle film şeridi](docs/filmstrip.png)

**Tur sonu ve klasörlere erişim**

![Tur özeti](docs/end.png)

</details>

Tur sonunda sayılar, **2. tura geç** ve **02_edit klasörünü Explorer'da aç** düğmeleri görünür. Lightroom Classic'e `02_edit\` içeriğini kendin içe aktar. CR3'süz JPEG uyarı rozetiyle işlenir. Alt klasörler taranmaz; JPG/JPEG ve harf duyarsız CR3 eşlemesi desteklenir.

`._*`, `Thumbs.db`, `desktop.ini`, `.DS_Store` ve Windows gizli/sistem dosyaları taramada yok sayılır; sayılmaz, gösterilmez, taşınmaz veya kopyalanmaz. Açılışta yok sayılanların sayısı küçük bir satırda görünür. Açılamayan gerçek JPEG'i yine Enter ile seçebilir, X ile eleyebilirsin; bu oturumda açılamayan dosyalar tur özetinde güncel yollarıyla listelenir.

## Dosya güvenliği

Fotoğraf silinmez, üzerine yazılmaz; `_red\` boşaltılmaz. Kaldırılan edit kopyaları `.ayikla_saklanan\` içine taşınır. Bu klasörü ve `ayikla_log.jsonl` günlüğünü sakla. İşlem önce günlüğe yazılır; yarıda kalırsa açılışta kurtarma denenir. **Yeniden dene** yarım işlemi tamamlar ve klasörü yeniden tarar; dışarıdan eklenen dosyalar için de bu düğmeyi kullan. Günlük yazma hatasında disk sorununu giderip uygulamayı yeniden aç. Ana çekimin bağımsız yedeğini koru.

Son klasörler ve pencere ayarı ayrı, yalnızca sona eklenen `ayikla_settings.jsonl` dosyasında tutulur: exe yanında; Python ile çalıştırırken proje kökünde.

Ayar dosyası okunamazsa uygulama varsayılanlarla açılır ve bir bilgi satırı gösterir; çekim günlüğü etkilenmez.

## Kulüp betası: yorumun neyi değiştirecek?

Özellikle **Sakla / Edit ayrımı**, gezinme hızı, odak kontrolü ve klasörlere erişim konusunda yorum arıyoruz. [Kullanım yorumu şablonu](https://github.com/Firextream/Ayikla/issues/new?template=feedback.md) veya [hata bildirimi](https://github.com/Firextream/Ayikla/issues/new?template=bug_report.md) açabilirsin; GitHub hesabı gerekir. Sürümü H yardımında görebilirsin. Fotoğraflarını, kişisel yollarını, ayar dosyanı veya tüm karar günlüğünü paylaşman gerekmez.

**131 otomatik test geçti; paket Windows 11'de doğrulandı.** Başka bilgisayarlar, yüksek DPI/çoklu monitör, gerçek kart bağlantı kaybı ve ICC/renk doğruluğu henüz doğrulanmadı. Minimum pencere 1024×680 mantıksal pikseldir. Bu sürüm bir kulüp betasıdır. CR3 görüntüsü çözülmez; diğer RAW biçimleri ve otomatik Lightroom aktarımı yoktur.

[Beş dakikalık beta denemesi](BETA.md) · [Testler, ölçümler ve bilinen sınırlar](RAPOR.md) · [Kaynak koddan çalıştırma ve paketleme](docs/GELISTIRME.md)

Python 3.12 + PySide6; Pillow yalnızca EXIF için kullanılır. Üçüncü taraf bileşenlerin lisans bildirimleri [licenses](licenses/NOTICE.txt) klasöründe ve uygulama paketinde bulunur.
