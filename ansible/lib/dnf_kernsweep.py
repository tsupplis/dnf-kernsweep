#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dnf_kernsweep
short_description: Detect and remove obsolete Linux kernels
version_added: "0.1.0"
description:
    - Detects obsolete Linux kernel packages on Red Hat / Fedora based systems
      (RHEL, CentOS Stream, Fedora, Rocky Linux, AlmaLinux, ...)
    - Protects running kernel and latest installed kernel
    - Removes old kernel packages to free disk space
    - Provides safety checks to prevent system boot failures
options:
    state:
        description:
            - Whether to remove obsolete kernels or just report them
        type: str
        choices: [ absent, present ]
        default: present
    verbosity:
        description:
            - Output verbosity level
        type: str
        choices: [ quiet, normal, verbose ]
        default: normal
author:
    - KernSweep Contributors
notes:
    - Requires root privileges to remove packages
    - Always protects the running kernel and latest installed kernel
    - Uses dnf remove to remove obsolete kernel packages
    - Only sweeps installonly packages (kernel, kernel-core, kernel-modules,
      kernel-modules-extra). kernel-devel and kernel-headers are excluded
      since they are not stacked/versioned like installonly packages and
      may legitimately trail kernel-core's version without being obsolete.
requirements:
    - python >= 3.7
    - rpm and dnf
'''

EXAMPLES = r'''
# Check what kernels would be removed (check mode)
- name: Check for obsolete kernels
  dnf_kernsweep:
    state: present
  check_mode: yes

# Remove obsolete kernels
- name: Clean up old kernels
  dnf_kernsweep:
    state: absent

# Remove obsolete kernels with verbose output
- name: Clean up old kernels (verbose)
  dnf_kernsweep:
    state: absent
    verbosity: verbose

# Just report status quietly
- name: Check kernel status
  dnf_kernsweep:
    state: present
    verbosity: quiet
'''

RETURN = r'''
changed:
    description: Whether any kernels were removed
    type: bool
    returned: always
    sample: true
failed:
    description: Whether the operation failed
    type: bool
    returned: always
    sample: false
msg:
    description: Human readable message about what happened
    type: str
    returned: always
    sample: "Successfully removed 2 obsolete kernel package(s)"
rc:
    description: Return code from kernsweep (0=success, 1=nothing to do, -1=no root, -2=dnf failed, 2=reboot required)
    type: int
    returned: always
    sample: 0
removed_packages:
    description: List of package names that were removed
    type: list
    elements: str
    returned: when changed
    sample: ["kernel-core-6.8.5-200.fc40.x86_64", "kernel-modules-6.8.5-200.fc40.x86_64"]
obsolete_count:
    description: Number of obsolete packages found
    type: int
    returned: always
    sample: 2
running_kernel:
    description: Currently running kernel version
    type: str
    returned: always
    sample: "6.8.5-200.fc40.x86_64"
latest_kernel:
    description: Latest installed kernel version
    type: str
    returned: always
    sample: "6.8.7-200.fc40.x86_64"
reboot_required:
    description: Whether a reboot is required to use the latest kernel
    type: bool
    returned: always
    sample: true
'''

from ansible.module_utils.basic import AnsibleModule


# ===== EMBEDDED KERNSWEEP CODE =====
# The following code is embedded from the kernsweep package

import subprocess
import os
import re
from typing import List, Set, Tuple, Optional
from enum import Enum
from dataclasses import dataclass, field


# ===== From kernsweep/utils.py =====

def run_command(cmd: List[str], check: bool = True) -> Tuple[int, str, str]:
    """
    Run a shell command and capture output.
    Args:
        cmd: Command as list of arguments
        check: If True, raise exception on non-zero exit code
    Returns:
        Tuple[int, str, str]: (exit_code, stdout, stderr)
    Raises:
        subprocess.CalledProcessError: If check=True and command fails
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        if check:
            raise
        return e.returncode, e.stdout or "", e.stderr or ""
def parse_package_size(rpm_output: str) -> int:
    """
    Parse package size from rpm output.
    Args:
        rpm_output: Output from rpm -q --qf '%{SIZE}'
    Returns:
        int: Package size in bytes
    """
    # TODO: Implement when needed
    raise NotImplementedError()
def needs_reboot() -> bool:
    """
    Check if a system reboot is needed.
    Uses the 'needs-restart -r' helper (provided by the dnf-utils /
    yum-utils package) which returns a non-zero exit code when the system
    as a whole needs a reboot to fully use updated software (e.g. after a
    kernel or glibc update).
    Returns:
        bool: True if reboot is needed
    """
    try:
        result = subprocess.run(
            ["needs-restart", "-r"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 1
    except (OSError, FileNotFoundError):
        # needs-restart not installed - fall back to no reboot detected
        return False

# ===== From kernsweep/detector.py =====

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

# ===== From kernsweep/analyzer.py =====

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
    # Warn if removing many kernels at once (more than 5)
    if len(kernel_images_to_remove) > 5:
        return False, f"Safety check warning: Attempting to remove {len(kernel_images_to_remove)} kernels at once. This seems excessive."
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

# ===== From kernsweep/remover.py =====

class RemovalStatus(Enum):
    """Status of a package removal operation."""
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
def check_sudo() -> bool:
    """
    Check if the current process has sudo privileges.
    Returns:
        bool: True if running with sudo/root, False otherwise
    """
    try:
        # On Unix systems, root has UID 0
        return os.geteuid() == 0
    except AttributeError:
        # os.geteuid() not available on Windows
        return False
def _execute_dnf_removal(cmd: List[str], packages: List[str]) -> List[Tuple[str, RemovalStatus]]:
    """
    Execute dnf removal command and return results.
    Args:
        cmd: dnf command to execute
        packages: List of package names being removed
    Returns:
        List[Tuple[str, RemovalStatus]]: List of (package, status) tuples
    Raises:
        RuntimeError: If dnf command fails
    """
    try:
        # Execute dnf remove (output visible to user)
        result = subprocess.run(
            cmd,
            check=False,  # Don't raise on non-zero exit
        )
        if result.returncode == 0:
            return [(pkg, RemovalStatus.SUCCESS) for pkg in packages]
        # Failure - mark all as failed
        raise RuntimeError(
            f"dnf remove failed with exit code {result.returncode}"
        )
    except subprocess.SubprocessError as e:
        # Command execution failed
        raise RuntimeError(f"Failed to execute dnf: {e}")
def remove_packages(packages: List[str], dry_run: bool = False) -> List[Tuple[str, RemovalStatus]]:
    """
    Remove packages using dnf.
    Args:
        packages: List of package names to remove
        dry_run: If True, simulate removal without actually removing
    Returns:
        List[Tuple[str, RemovalStatus]]: List of (package, status) tuples
    Raises:
        PermissionError: If not running with sufficient privileges
        RuntimeError: If dnf command fails
    """
    if not packages:
        return []
    # In dry-run mode, just return success for all packages
    if dry_run:
        return [(pkg, RemovalStatus.SUCCESS) for pkg in packages]
    # Check for sudo privileges (not needed for dry-run)
    if not check_sudo():
        raise PermissionError(
            "Root privileges required. Please run with sudo."
        )
    # Generate dnf command and execute
    cmd = generate_dnf_command(packages)
    return _execute_dnf_removal(cmd, packages)
def generate_dnf_command(packages: List[str]) -> List[str]:
    """
    Generate the dnf command to remove packages.
    Uses 'dnf -y remove' to remove the obsolete kernel packages.
    The -y flag is always included to skip dnf's confirmation prompt.
    Args:
        packages: List of package names to remove
    Returns:
        List[str]: Command as list of arguments
    """
    if not packages:
        raise ValueError("No packages provided for removal")
    # Build dnf -y remove command
    cmd = ["dnf", "-y", "remove"]
    # Add packages to remove
    cmd.extend(packages)
    return cmd

# ===== END EMBEDDED KERNSWEEP CODE =====


# Kernsweep is now available (embedded above)
KERNSWEEP_AVAILABLE = True
KERNSWEEP_IMPORT_ERROR = None
  # type: ignore[import-not-found]



def run_module():
    """Main Ansible module execution."""
    module_args = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        verbosity=dict(type='str', default='normal', choices=['quiet', 'normal', 'verbose']),
    )

    result = dict(
        changed=False,
        failed=False,
        msg='',
        rc=0,
        removed_packages=[],
        obsolete_count=0,
        running_kernel='',
        latest_kernel='',
        reboot_required=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Check if kernsweep is available
    if not KERNSWEEP_AVAILABLE:
        result['msg'] = f"Failed to import kernsweep: {KERNSWEEP_IMPORT_ERROR}"
        result['failed'] = True
        module.fail_json(**result)

    # Check for root privileges when not in check mode and state is absent
    if module.params['state'] == 'absent' and not module.check_mode:
        if not check_sudo():
            result['msg'] = "Root privileges required for package removal"
            result['rc'] = -1
            result['failed'] = True
            module.fail_json(**result)

    try:
        # Step 1: Detect running kernel
        running_kernel_version = get_running_kernel()
        result['running_kernel'] = running_kernel_version

        # Step 2: Detect installed kernels
        installed_kernels = get_installed_kernels()

        # Mark the running kernel
        for kernel in installed_kernels:
            if kernel.version == running_kernel_version:
                kernel.is_running = True
                break

        # Step 3: Determine the latest installed kernel version
        latest_kernel_version = get_latest_installed_kernel_version()
        result['latest_kernel'] = latest_kernel_version

        # Step 4: Analyze kernels
        analysis = analyze_kernels(installed_kernels, latest_kernel_version)

        # Check if reboot is required
        result['reboot_required'] = analysis.running_kernel != analysis.latest_kernel

        # Collect obsolete packages
        all_obsolete = analysis.obsolete_kernels
        result['obsolete_count'] = len(all_obsolete)

        if len(all_obsolete) == 0:
            result['msg'] = "No obsolete kernels found"
            # rc: 2 if reboot required, 1 if nothing to do
            result['rc'] = 2 if result['reboot_required'] else 1
            module.exit_json(**result)

        # Handle state logic
        if module.params['state'] == 'present':
            # Just report what's there
            result['msg'] = f"Found {len(all_obsolete)} obsolete package(s)"
            result['rc'] = 0
            result['removed_packages'] = all_obsolete
            module.exit_json(**result)

        # state == 'absent' - remove packages
        if module.check_mode:
            # Check mode - don't actually remove
            result['changed'] = True
            result['msg'] = f"Would remove {len(all_obsolete)} obsolete package(s)"
            result['rc'] = 0
            result['removed_packages'] = all_obsolete
            module.exit_json(**result)

        # Actually remove packages
        results = remove_packages(all_obsolete, dry_run=False)

        # Count successes and failures
        success_count = sum(1 for _, status in results if status == RemovalStatus.SUCCESS)
        failed_count = len(results) - success_count

        if failed_count > 0:
            result['failed'] = True
            result['rc'] = -2
            result['msg'] = f"Failed to remove {failed_count} package(s), successfully removed {success_count}"
            module.fail_json(**result)

        # Success - determine rc based on reboot requirement
        result['changed'] = True
        result['msg'] = f"Successfully removed {success_count} obsolete package(s)"
        result['removed_packages'] = all_obsolete
        
        # Set rc: 2 if reboot required, 0 otherwise
        if result['reboot_required']:
            result['rc'] = 2
        else:
            result['rc'] = 0

        module.exit_json(**result)

    except Exception as e:
        result['failed'] = True
        result['msg'] = f"Error: {str(e)}"
        module.fail_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

