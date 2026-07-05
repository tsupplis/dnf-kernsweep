"""
KernSweep - Linux Kernel Cleanup Tool

A lightweight command-line utility to detect and remove obsolete Linux
kernels on Red Hat / Fedora based systems (RHEL, CentOS Stream, Fedora,
Rocky Linux, AlmaLinux, ...), keeping only the running and latest kernels.
"""

__version__ = "0.1.0"
__author__ = "KernSweep Contributors"
__license__ = "MIT"

from .cli import main

__all__ = ["main"]
