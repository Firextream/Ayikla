# Ayikla 1.1.1b1 · Fotoğraf kulübü betası

Canon RAW+JPEG çekimlerinde önce saklanacak kareleri, sonra Lightroom'da düzenlenecekleri seçmek için. Windows x64; bu paket Windows 11'de doğrulandı. Python kurulumu gerekmez.

## Başlangıç

1. ZIP'in tamamını yazabildiğin bir klasöre çıkar. `Ayikla.exe` ile `_internal` birlikte kalmalı. ZIP içinden çalıştırma.
2. İlk denemeyi 20–50 JPG+CR3 çiftinin **ayrı bir kopyasında** yap. Ana çekimin yedeğini ayrı tut. Uygulama seçtiğin klasördeki dosyaları taşır.
3. `Ayikla.exe` → **Klasör aç**. Doğrudan JPG'lerin bulunduğu klasörü seç; alt klasörler taranmaz.

Paket imzasızdır; Windows uyarısı çıkabilir. Güvenlik yazılımını kapatma. Açılmazsa uyarının metnini ve paket sürümünü bildir.

## İki tur

| İşlem | Tuş | Sonuç |
|---|---|---|
| Sakla | → / Enter | JPG + varsa CR3 → `01_secilen` |
| Ele | ← / X / Delete | Çift → `_red`; **kalıcı silme değildir** |
| Son kararı geri al | Z | Dosyalar tam eski yollarına döner; yeniden açınca da çalışır |
| Kararsız geç / geri git | Boşluk / ↓ / ↑ | Dosyaları değiştirmez |
| Edit turuna geç | M | Saklananlar arasından seçim |
| Edit için seç / kaldır | E | `02_edit` içine JPG+CR3 kopyalar; kaldırınca kopyaları arşive taşır |
| Odak kontrolü | F; sürükle | %100 yakınlaştır / kaydır; tekrar F ile sığdır |
| Bilgi / film şeridi / yardım | I / T / H | Paneli aç veya kapat |
| Tam ekran | F11 | Pencere / tam ekran |

Kararlar otomatik kaydedilir. **Klasörler** menüsü saklanan, elenen ve edit dosyalarını açar. Lightroom'a `02_edit` içeriğini kendin aktar.

`_red`, `.ayikla_saklanan` ve `ayikla_log.jsonl` dosya/klasörlerini koru. Uygulama fotoğraf silmez ve var olan hedefin üzerine yazmaz. Harici değişiklikten sonra **Yeniden dene** ile tara. macOS `._` yardımcı dosyaları yok sayılır. Bozuk gerçek JPEG seçilebilir/elenebilir; karşılaşılan açılma hataları tur özetinde listelenir.

## Beş dakikalık deneme ve geri bildirim

İki kareyi sakla, birini ele, Z ile geri al. Kapatıp aynı klasörü aç; kararlar ve Z çalışıyor mu? M → E ile bir kareyi edite ayır; `02_edit` içindeki JPG+CR3 kopyalarını kontrol et. F ile odak, I ile EXIF ve T ile film şeridini dene.

Geri bildirimde şunlar yeterli:

- Sürüm: **1.1.1b1** (H yardımında da görünür).
- Windows sürümü, ekran çözünürlüğü ve ölçekleme (%100/%125/%150).
- Kamera; fotoğraf sayısı; dahili disk / harici disk / SD kart.
- Ne yaptın? Ne bekledin? Ne oldu? Tekrar oluşuyor mu?
- Kullanım yorumu: Sakla ile Edit ayrımı net mi? Hangi adım yavaş veya kafa karıştırıcı?

İlk raporda fotoğraflarını, `ayikla_settings.jsonl` veya tüm karar günlüğünü paylaşma. Ekran görüntüsündeki özel yolları/adları gizle. Gerekirse yalnızca hatayı üreten yapay örnek veya izin verdiğin bir örnek istenir.

## Beta sınırları

Şu an yalnızca JPG/JPEG + Canon CR3 eşlemesi var; RAW görüntüsü çözülmez. Otomatik Lightroom aktarımı yoktur. Başka bilgisayar, yüksek DPI/ikinci monitör, SD kartın çıkarılması ve gerçek elektrik kesintisi saha testleri tamamlanmadı. En küçük pencere 1024×680 mantıksal pikseldir; ekran ölçeklemesi kullanılabilir alanı azaltır. Renk doğruluğu/ICC doğrulaması yapılmadı; bu sürüm renk düzenleme aracı değildir. Sonuçlar küçük kulüp betası için, genel kararlı sürüm iddiası taşımaz.
