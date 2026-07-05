"""
Kernel analysis module.

Provides functionality to analyze installed kernels and determine
which ones are obsolete and safe to remove.
"""

from typing import List, Set, Tuple
from dataclasses import dataclass

from .detector import KernelInfo


@dataclass
class AnalysisResult:
    """
    Result of kernel analysis.

    Attributes:
        running_kernel: Version of the currently running kernel
        latest_kernel: Version of the latest installed kernel
        obsolete_kernels: List of kernel packages safe to remove
        protected_kernels: List of kernels that must be kept
    """
    running_kernel: str
    latest_kernel: str
    obsolete_kernels: List[str]
    protected_kernels: List[str]


def analyze_kernels(kernels: List[KernelInfo], latest_kernel_version: str) -> AnalysisResult:
    """
    Analyze installed kernels and identify obsolete ones.

    Identifies the running kernel and marks every installed kernel package
    whose version is neither the running kernel nor the latest installed
    kernel as obsolete. The latest kernel version is determined by rpm
    itself (see detector.get_latest_installed_kernel_version), since RPM
    already knows how to order installed package versions correctly.

    Args:
        kernels: List of installed kernels
        latest_kernel_version: Version-release of the latest installed kernel

    Returns:
        AnalysisResult: Analysis results with removal recommendations

    Raises:
        ValueError: If no running kernel found in the list, or if the
            proposed removal fails a safety check
    """
    if not kernels:
        # No kernels (e.g., container environment) - return empty result
        return AnalysisResult(
            running_kernel="",
            latest_kernel="",
            obsolete_kernels=[],
            protected_kernels=[],
        )

    # Find running kernel
    running_kernel = None
    for kernel in kernels:
        if kernel.is_running:
            running_kernel = kernel
            break

    if not running_kernel:
        raise ValueError("Running kernel not found in installed kernels list")

    # Mark installed packages matching the latest version
    for kernel in kernels:
        if kernel.version == latest_kernel_version:
            kernel.is_latest = True

    # Protect running kernel version and latest kernel version
    protected_versions = {running_kernel.version, latest_kernel_version}

    obsolete_kernels = []
    protected_kernels = []

    for kernel in kernels:
        if kernel.version in protected_versions:
            protected_kernels.append(kernel.package_name)
        else:
            obsolete_kernels.append(kernel.package_name)

    # Final safety validation before returning results
    is_safe, error_msg = validate_removal_safety(
        packages_to_remove=obsolete_kernels,
        running_kernel=running_kernel.version,
        latest_kernel=latest_kernel_version,
        all_kernels=kernels
    )

    if not is_safe:
        raise ValueError(error_msg)

    return AnalysisResult(
        running_kernel=running_kernel.version,
        latest_kernel=latest_kernel_version,
        obsolete_kernels=obsolete_kernels,
        protected_kernels=protected_kernels,
    )


def validate_removal_safety(
    packages_to_remove: List[str],
    running_kernel: str,
    latest_kernel: str,
    all_kernels: List[KernelInfo]
) -> Tuple[bool, str]:
    """
    Validate that the proposed package removal is safe.

    Performs safety checks to ensure:
    - Running kernel is not being removed
    - Latest kernel is not being removed
    - At least one kernel will remain after removal

    Args:
        packages_to_remove: List of packages marked for removal
        running_kernel: Version of the currently running kernel
        latest_kernel: Version of the latest installed kernel
        all_kernels: List of all installed kernels

    Returns:
        Tuple[bool, str]: (is_safe, error_message)
            is_safe: True if removal is safe
            error_message: Description of safety violation (empty if safe)
    """
    # Check if the running kernel's package is in the removal list
    running_pkg = f"kernel-core-{running_kernel}"
    if running_pkg in packages_to_remove:
        return False, f"Safety check failed: Running kernel {running_kernel} is marked for removal"

    # Check if the latest kernel's package is in the removal list
    latest_pkg = f"kernel-core-{latest_kernel}"
    if latest_pkg in packages_to_remove:
        return False, f"Safety check failed: Latest kernel {latest_kernel} is marked for removal"

    # Count how many kernel-core packages will be removed
    kernel_images_to_remove = [pkg for pkg in packages_to_remove if pkg.startswith("kernel-core-")]
    kernel_images_installed = [k for k in all_kernels if k.package_name.startswith("kernel-core-")]
    remaining_kernels = len(kernel_images_installed) - len(kernel_images_to_remove)

    if kernel_images_installed and remaining_kernels < 1:
        return False, "Safety check failed: No kernels would remain after removal"

    return True, ""


def get_protected_packages(running_kernel: str, latest_kernel: str) -> Set[str]:
    """
    Get a set of package names that must never be removed.

    Args:
        running_kernel: Version of the currently running kernel
        latest_kernel: Version of the latest installed kernel

    Returns:
        Set[str]: Set of protected package names
    """
    protected = set()

    for package_name in ("kernel-core", "kernel-modules", "kernel-modules-extra", "kernel"):
        protected.add(f"{package_name}-{running_kernel}")
        protected.add(f"{package_name}-{latest_kernel}")

    return protected

