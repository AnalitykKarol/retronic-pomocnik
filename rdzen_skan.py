"""Filtr stworów: jeden przebieg C; identyczny NumPy jako fallback.

Bibliotekę buduje jawnie narzedzia/zbuduj_skan.sh. Import i RPC nigdy nie kompilują.
RETRONIC_SKAN_NATIVE=0 przed startem procesu wymusza stary filtr.
"""

import ctypes
import os
from pathlib import Path
import platform
import sys
import warnings

import numpy as np


def kandydaci_numpy(bufor):
    """Oryginalny filtr, zachowany jako wzorzec i zgodna ścieżka awaryjna."""
    n = len(bufor) // 4
    if n < 12:
        return []
    a = np.frombuffer(bufor, "<u4", count=n)
    jeden = a == 0x3F800000
    k = n - 11
    m = jeden[:k] & jeden[1:k + 1] & jeden[2:k + 2] & jeden[3:k + 3]
    idx = np.nonzero(m)[0]
    if len(idx) == 0:
        return []
    ident = a[idx + 4] >> 24
    rozmiar = a[idx + 9]
    dobre = ((ident >= 0x10) & (ident <= 0x4F) & (a[idx + 10] == 15)
             & (rozmiar >= 1) & (rozmiar <= 15))
    return ((idx[dobre] + 5) * 4).tolist()


def _zaladuj():
    if os.environ.get("RETRONIC_SKAN_NATIVE") == "0":
        return None
    try:
        if (sys.byteorder != "little" or ctypes.sizeof(ctypes.c_size_t) != 8
                or platform.machine().lower() not in ("x86_64", "amd64")):
            raise OSError("nieobsługiwana platforma skanera natywnego")
        lib = ctypes.CDLL(str(Path(__file__).resolve().parent / "native/skan_stworow.so"))
        lib.skan_abi.argtypes = []
        lib.skan_abi.restype = ctypes.c_uint32
        if lib.skan_abi() != 1:
            raise OSError("niezgodne ABI skanera natywnego")
        lib.scan.argtypes = [ctypes.c_void_p, ctypes.c_size_t,
                             ctypes.POINTER(ctypes.POINTER(ctypes.c_uint64)),
                             ctypes.POINTER(ctypes.c_size_t)]
        lib.scan.restype = ctypes.c_int
        lib.release.argtypes = [ctypes.c_void_p]
        lib.release.restype = None
        return lib
    except (OSError, AttributeError) as e:
        warnings.warn(f"Skaner: fallback NumPy ({e}); uruchom narzedzia/zbuduj_skan.sh",
                      RuntimeWarning, stacklevel=2)
        return None


_native = _zaladuj()
NATIVE_AVAILABLE = _native is not None


def kandydaci(bufor):
    """Przesunięcia rosnąco; zapisywalny bufor musi mieć wyłącznego właściciela."""
    if len(bufor) < 48:
        return []
    if _native is None:
        return kandydaci_numpy(bufor)
    # c_char_p retains bytes; from_buffer retains the exporting memoryview.
    # Both live until scan returns (CDLL releases the GIL while in C).
    if isinstance(bufor, bytes):
        owner = ctypes.c_char_p(bufor)
    else:
        view = memoryview(bufor)
        if view.readonly or not view.c_contiguous:
            return kandydaci_numpy(bufor)
        owner = (ctypes.c_ubyte * view.nbytes).from_buffer(view)
    ptr = ctypes.POINTER(ctypes.c_uint64)()
    count = ctypes.c_size_t()
    try:
        status = _native.scan(owner, len(bufor), ctypes.byref(ptr), ctypes.byref(count))
        if status != 0:
            raise MemoryError("skaner natywny: nie udało się zaalokować listy trafień")
        return list(ptr[:count.value])
    finally:
        _native.release(ptr)
