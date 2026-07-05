"""
Package removal module.

Provides functionality to remove kernel packages using dnf.
"""

import os
import subprocess
from typing import List, Tuple
from enum import Enum


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

