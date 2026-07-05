"""
Kernel detection module.

Provides functionality to detect the currently running kernel and
discover all installed kernels on Red Hat / Fedora based systems
(RHEL, CentOS Stream, Fedora, Rocky Linux, AlmaLinux, ...).
"""

import subprocess
from typing import List
from dataclasses import dataclass

from .utils import run_command


# Only package names that Fedora/RHEL actually keep installed in multiple
# side-by-side versions ("installonly" packages) belong here. kernel-devel
# and kernel-headers are deliberately excluded: they are singleton packages
# that dnf upgrades in place, and kernel-headers in particular is not always
# rebuilt/released for every kernel-core point release, so its version can
# permanently trail kernel-core's without ever being "obsolete". Comparing
# its version against the latest kernel-core version can flag the only
# installed copy for removal even though nothing is actually stale, which
# then cascades into removing kernel-devel and the entire build toolchain
# that exists only to support it (gcc, clang, rust, systemtap, etc.) as
# unrelated collateral damage.
KERNEL_PACKAGE_NAMES = (
    "kernel-core",
    "kernel-modules-extra",
    "kernel-modules",
    "kernel",
)


@dataclass
class KernelInfo:
    """
    Information about an installed kernel.

    Attributes:
        version: Full kernel version-release string (e.g., '6.8.5-200.fc40.x86_64')
        package_name: Package name (e.g., 'kernel-core-6.8.5-200.fc40.x86_64')
        is_running: True if this is the currently running kernel
        is_latest: True if this is the latest installed kernel
    """
    version: str
    package_name: str
    is_running: bool = False
    is_latest: bool = False


def get_running_kernel() -> str:
    """
    Detect the currently running kernel version.

    Returns:
        str: Running kernel version string (e.g., '6.8.5-200.fc40.x86_64')

    Raises:
        RuntimeError: If unable to detect the running kernel
    """
    try:
        # Use uname -r to get the kernel release version
        result = subprocess.run(
            ["uname", "-r"],
            capture_output=True,
            text=True,
            check=True,
        )
        kernel_version = result.stdout.strip()

        if not kernel_version:
            raise RuntimeError("uname returned empty kernel version")

        return kernel_version

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to detect running kernel: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error detecting running kernel: {e}")


def get_installed_kernels() -> List[KernelInfo]:
    """
    Get list of all installed kernel packages.

    Queries rpm for the installonly kernel packages (kernel, kernel-core,
    kernel-modules, kernel-modules-extra).

    Returns:
        List[KernelInfo]: List of installed kernels with metadata

    Raises:
        RuntimeError: If unable to query installed packages
    """
    try:
        result = subprocess.run(
            ["rpm", "-qa", "--qf", "%{NAME} %{VERSION}-%{RELEASE}.%{ARCH}\n"],
            capture_output=True,
            text=True,
            check=True,
        )

        kernels: List[KernelInfo] = []
        allowed_names = set(KERNEL_PACKAGE_NAMES)

        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            name, version = parts[0], parts[1]
            if name in allowed_names:
                kernels.append(KernelInfo(version=version, package_name=f"{name}-{version}"))

        # Return empty list if no kernels found (e.g., container environment)
        return kernels

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to query installed kernels: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error querying installed kernels: {e}")


def get_latest_installed_kernel_version() -> str:
    """
    Determine the version-release of the most recently installed kernel.

    Uses 'rpm -q <package> --last' so that rpm itself resolves the install
    order, rather than re-implementing RPM version comparison rules.

    Returns:
        str: Latest installed kernel version-release string

    Raises:
        RuntimeError: If unable to determine the latest installed kernel
    """
    for package_name in KERNEL_PACKAGE_NAMES:
        rc, stdout, _ = run_command(["rpm", "-q", package_name, "--last"], check=False)
        if rc != 0 or not stdout.strip():
            continue
        first_line = stdout.splitlines()[0].strip()
        first_token = first_line.split()[0]
        prefix = f"{package_name}-"
        if first_token.startswith(prefix):
            return first_token[len(prefix):]

    raise RuntimeError("Unable to determine latest installed kernel")
