"""Actionable Turkish messages for filesystem failures."""
import errno

from .core import AyiklaError, RecoveryError


def error_message(error: Exception) -> str:
    code = getattr(error, "winerror", None)
    if code in (32, 33):
        return "Dosya başka bir uygulamada açık. Lightroom veya fotoğraf görüntüleyiciyi kapatıp Yeniden dene'ye bas."
    if code == 112 or getattr(error, "errno", None) == errno.ENOSPC:
        return "Diskte yeterli boş alan yok. Diskte yer açıp Yeniden dene'ye bas."
    if isinstance(error, FileNotFoundError):
        return "Dosya veya çekim klasörü bulunamadı. Disk bağlantısını ve klasör yolunu kontrol edip Yeniden dene'ye bas."
    if isinstance(error, FileExistsError):
        return "Hedef dosya zaten var; üzerine yazılmadı. Var olan dosyayı başka bir konuma taşıyıp Yeniden dene'ye bas."
    if isinstance(error, PermissionError):
        return "Klasöre erişim izni yok. Yazma iznini ve dosyanın başka uygulamada açık olmadığını kontrol edip Yeniden dene'ye bas."
    if isinstance(error, RecoveryError) and "Günlük" in str(error):
        return str(error) + " Günlüğü değiştirmeden sakla; uygulamayı yeniden aç. Sorun sürerse raporla."
    if isinstance(error, AyiklaError):
        return str(error) + " Dosyaları ve disk bağlantısını kontrol edip Yeniden dene'ye bas."
    return str(error) + " İşlem tamamlanmadı. Disk bağlantısını ve erişim izinlerini kontrol edip Yeniden dene'ye bas."
