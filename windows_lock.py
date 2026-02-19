import ctypes
import platform

def lock_windows():
    """
    Locks the Windows workstation (same as Win+L).
    Works only on Windows OS.
    """
    if platform.system() != "Windows":
        print("Lock not supported on this OS")
        return

    try:
        ctypes.windll.user32.LockWorkStation()
    except Exception as e:
        print("Failed to lock workstation:", e)
