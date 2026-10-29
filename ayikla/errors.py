"""Actionable English messages for filesystem failures."""
import errno

from .core import AyiklaError, RecoveryError


def error_message(error: Exception) -> str:
    code = getattr(error, "winerror", None)
    if code in (32, 33):
        return "The file is open in another app. Close Lightroom or your photo viewer, then press Rescan folder."
    if code == 112 or getattr(error, "errno", None) == errno.ENOSPC:
        return "Not enough free disk space. Free up space, then press Rescan folder."
    if isinstance(error, FileNotFoundError):
        return "File or shoot folder not found. Check the disk connection and folder path, then press Rescan folder."
    if isinstance(error, FileExistsError):
        return "Destination file already exists; nothing overwritten. Move the existing file elsewhere, then press Rescan folder."
    if isinstance(error, PermissionError):
        return "Folder access denied. Check write permission and close other apps using the file, then press Rescan folder."
    if isinstance(error, RecoveryError) and "journal" in str(error).casefold():
        return str(error) + " Preserve the journal unchanged and reopen the app. Report the problem if it continues."
    if isinstance(error, AyiklaError):
        return str(error) + " Check the files and disk connection, then press Rescan folder."
    return str(error) + " Operation not completed. Check the disk connection and access permissions, then press Rescan folder."
