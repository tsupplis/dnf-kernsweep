"""
Utility functions.

Shared helper functions used across kernsweep modules.
"""

import subprocess
from typing import List, Tuple


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
