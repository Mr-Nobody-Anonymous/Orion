from __future__ import annotations

import shutil

from ..models.routing import HardwareProfile


def detect_hardware() -> HardwareProfile:
    ram_gb = 0
    try:
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_uint32),
                ("memory_load", ctypes.c_uint32),
                ("total", ctypes.c_uint64),
                ("available", ctypes.c_uint64),
                ("page", ctypes.c_uint64),
                ("avail_page", ctypes.c_uint64),
                ("virtual", ctypes.c_uint64),
                ("avail_virtual", ctypes.c_uint64),
                ("extended", ctypes.c_uint64),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        ram_gb = round(status.total / (1024 ** 3))
    except (AttributeError, OSError, TypeError):
        ram_gb = 0
    return HardwareProfile(ram_gb=ram_gb, gpu_name=None, cuda_available=shutil.which("nvidia-smi") is not None)
