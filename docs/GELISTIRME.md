# Geliştirme

Windows x64, Python 3.12. PowerShell komutlarını depo kökünde çalıştır:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\run.ps1
.\.venv\Scripts\python.exe -m pytest --basetemp .tmp\pytest-local -q
.\build.ps1
.\.venv\Scripts\python.exe scripts\verify_frozen.py
.\.venv\Scripts\python.exe scripts\verify_frozen.py --windows
.\.venv\Scripts\python.exe scripts\package_release.py
```

Testler üretilmiş dosyalar kullanır; gerçek fotoğraflarla test çalıştırma. Farklı test çalıştırmaları için yeni bir `--basetemp` adı kullan. Projeye özgü geçici dosyaları `.tmp` altında tut.

Build `.venv` Python'unu, yoksa proje içindeki `.tools\python312\tools\python.exe` yolunu kullanır. Yeni paket önce ayrı bir klasöre üretilir; önceki paket silinmeden `.tmp\replaced-builds` içine taşınır. Yerel kullanıcının taşınabilir ayarı yeni `dist\Ayikla` klasörüne kopyalanır.

`package_release.py` paylaşım ZIP'ini üretir: exe, `_internal`, kısayol betiği ve beta kılavuzu. Kişisel ayarları/çekim günlüklerini içermez. Var olan ZIP'in üzerine yazmaz; yeni sürümde uygulama, proje ve Windows dosya sürümlerini birlikte güncelle. `dist` ve geliştirici araçları git'e eklenmez; çalıştırılabilir paket GitHub Releases üzerinden dağıtılır.

Ölçümleri tekrarlamak için `scripts\benchmark.py generate`, ardından `measure <etiket>` ve `startup <etiket> <exe-yolu>` kullan. Generate proje içindeki `.tmp\benchmark` altında yaklaşık 2,5 GB yapay veri üretir. [Ölçüm yöntemi ve önceki sonuçlar](../RAPOR.md).

## Değişiklik sınırları

- Dosya silme ve üzerine yazma yok. Taşıma/kopyalama öncesi dayanıklı günlük zorunlu.
- Geri alma tam yolları korumalı; yeniden açılışta çalışmalı.
- Eşleştirme harf duyarsız; yardımcı/gizli/sistem dosyaları yok sayılır.
- Davranış değişikliklerine regresyon testi ekle. Yeni özellikleri ayrı öneri olarak tartış.
- Hata raporlarında gerçek fotoğraf, kişisel ayar veya tüm çekim günlüğünü isteme.
