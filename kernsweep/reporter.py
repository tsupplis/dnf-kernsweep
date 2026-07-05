"""
Output reporting module.

Provides dnf-style formatted output and progress reporting.
"""

from typing import List, Optional
from enum import Enum

from .analyzer import AnalysisResult
from .remover import RemovalStatus


class OutputLevel(Enum):
    """Output verbosity levels."""
    QUIET = 0
    NORMAL = 1
    VERBOSE = 2


class Reporter:
    """
    Handles formatted output for kernsweep operations.
    
    Provides dnf-style output with configurable verbosity.
    """
    
    def __init__(self, level: OutputLevel = OutputLevel.NORMAL):
        """
        Initialize the reporter.
        
        Args:
            level: Output verbosity level
        """
        self.level = level
    
    def print_analysis(self, result: AnalysisResult) -> None:
        """
        Print analysis results in dnf-style format.
        
        Args:
            result: Analysis results to display
        """
        if self.level == OutputLevel.QUIET:
            return
        
        total_obsolete = len(result.obsolete_kernels)
        
        print("Last metadata expiration check.")
        print("Dependencies resolved.")
        print()
        
        # Always show kernel status
        print(f"Running kernel: {result.running_kernel}")
        print(f"Latest kernel:  {result.latest_kernel}")
        
        # Show reboot notice if running kernel is not the latest
        if result.running_kernel != result.latest_kernel:
            print(f"*** System will boot into {result.latest_kernel} after reboot ***")
        
        print()
        
        if total_obsolete > 0:
            print("Removing:")
            
            for pkg in result.obsolete_kernels:
                print(f"  {pkg}")
            
            print()
            print("Transaction Summary")
            print("=" * 40)
            print(f"Remove  {total_obsolete} Package(s)")
        else:
            print("Nothing to do.")
    
    def print_command(self, command: List[str], dry_run: bool = False) -> None:
        """
        Print the command that will be executed.
        
        Args:
            command: Command as list of arguments
            dry_run: Whether this is a dry run
        """
        if self.level == OutputLevel.QUIET:
            return
        
        cmd_str = " ".join(command)
        print()
        if dry_run:
            print(f"[DRY RUN] Would execute: {cmd_str}")
        else:
            print(f"Executing: {cmd_str}")
        print()
    
    def print_removal_progress(self, package: str, status: RemovalStatus) -> None:
        """
        Print removal progress for a single package.
        
        Args:
            package: Package being removed
            status: Current status
        """
        if self.level == OutputLevel.QUIET:
            return
        
        if status == RemovalStatus.SUCCESS:
            print(f"Removing {package} ...")
            if self.level == OutputLevel.VERBOSE:
                print(f"  [✓] {package} removed successfully")
        elif status == RemovalStatus.FAILED:
            print(f"Failed to remove {package}")
        elif status == RemovalStatus.SKIPPED:
            print(f"Skipped {package}")
    
    def print_summary(self, removed: int, failed: int, freed_space: Optional[int] = None) -> None:
        """
        Print final summary statistics.
        
        Args:
            removed: Number of packages successfully removed
            failed: Number of packages that failed to remove
            freed_space: Disk space freed in bytes (optional)
        """
        if self.level == OutputLevel.QUIET:
            return
        
        print()
        if removed > 0:
            print(f"Successfully removed {removed} package(s).")
        
        if failed > 0:
            print(f"Failed to remove {failed} package(s).")
        
        if freed_space is not None and freed_space > 0:
            # Convert bytes to MB
            freed_mb = freed_space / (1024 * 1024)
            print(f"Freed space: {freed_mb:.1f} MB")
        
        if removed > 0 or failed > 0:
            print()
            print("Complete!")
    
    def print_reboot_notice(self) -> None:
        """Print notice that a reboot is recommended."""
        if self.level == OutputLevel.QUIET:
            return
        
        print()
        print("A reboot is required to use the updated kernel.")
        print("Run 'sudo reboot' to restart the system.")

