"""
Setup configuration for kernsweep.

Installs kernsweep as a command-line tool.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read version from __init__.py
init_file = Path(__file__).parent / "kernsweep" / "__init__.py"
version = {}
with open(init_file) as f:
    for line in f:
        if line.startswith("__version__"):
            exec(line, version)
            break

# Read long description from README
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="kernsweep",
    version=version.get("__version__", "0.1.0"),
    author="KernSweep Contributors",
    description="A lightweight tool to detect and remove obsolete Linux kernels on Red Hat / Fedora based systems",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/kernsweep",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Systems Administration",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "kernsweep=kernsweep.cli:main",
        ],
    },
    keywords="kernel linux dnf rpm redhat fedora rhel cleanup administration",
    project_urls={
        "Bug Reports": "https://github.com/yourusername/kernsweep/issues",
        "Source": "https://github.com/yourusername/kernsweep",
    },
)
