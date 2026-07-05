"""
Command-line interface for kernsweep.

Provides argument parsing and orchestrates the kernel cleanup workflow.
"""

import sys
import argparse
from typing import Optional, List

from . import __version__
from .detector import get_running_kernel, get_installed_kernels, get_latest_installed_kernel_version
from .analyzer import analyze_kernels
from .remover import remove_packages, check_sudo, RemovalStatus
from .reporter import Reporter, OutputLevel


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        prog="kernsweep",
        description="Detect and remove obsolete Linux kernels",
        epilog="Example: kernsweep --dry-run  # See what would be removed",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be removed without actually removing anything",
    )
    
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove obsolete kernels (requires sudo)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress non-essential output",
    )
    
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Assume yes to all prompts (use with --remove)",
    )
    
    return parser


def _setup_reporter(args) -> Reporter:
    """
    Set up reporter based on command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Reporter: Configured reporter instance
    """
    if args.quiet:
        output_level = OutputLevel.QUIET
    elif args.verbose:
        output_level = OutputLevel.VERBOSE
    else:
        output_level = OutputLevel.NORMAL
    
    return Reporter(output_level)


def _detect_and_analyze(args, reporter) -> tuple:
    """
    Detect kernels and perform analysis.
    
    Args:
        args: Parsed command-line arguments
        reporter: Reporter instance for output
        
    Returns:
        tuple: (analysis, installed_kernels)
    """
    # Step 1: Detect running kernel
    if args.verbose:
        print("Detecting running kernel...")
    
    running_kernel_version = get_running_kernel()
    
    if args.verbose:
        print(f"Running kernel: {running_kernel_version}")
    
    # Step 2: Detect installed kernels
    if args.verbose:
        print("\nScanning installed kernels...")
    
    installed_kernels = get_installed_kernels()
    
    # Mark the running kernel
    for kernel in installed_kernels:
        if kernel.version == running_kernel_version:
            kernel.is_running = True
            break
    
    if args.verbose:
        print(f"Found {len(installed_kernels)} installed kernel(s)")
    
    # Step 3: Determine the latest installed kernel version
    if args.verbose:
        print("\nDetermining latest installed kernel...")
    
    latest_kernel_version = get_latest_installed_kernel_version()
    
    # Step 4: Analyze kernels
    if args.verbose:
        print("\nAnalyzing kernels...")
    
    analysis = analyze_kernels(installed_kernels, latest_kernel_version)
    
    return analysis, installed_kernels


def _handle_removal(args, reporter, all_obsolete: List[str], analysis) -> int:
    """
    Handle the removal workflow including confirmation and execution.
    
    Args:
        args: Parsed command-line arguments
        reporter: Reporter instance for output
        all_obsolete: List of all obsolete packages
        analysis: Analysis results
        
    Returns:
        int: Exit code
    """
    # For actual removal (not dry-run), verify root privileges FIRST
    if args.remove and not args.dry_run:
        if not check_sudo():
            print("\nError: Root privileges required for package removal.", file=sys.stderr)
            print("Please run with sudo:", file=sys.stderr)
            print("  sudo kernsweep --remove", file=sys.stderr)
            return -1
    
    # Import generate_dnf_command to show what would be executed
    from .remover import generate_dnf_command
    
    # Show the command that would/will be executed
    if args.dry_run or args.remove:
        try:
            cmd = generate_dnf_command(all_obsolete)
            reporter.print_command(cmd, dry_run=args.dry_run)
        except ValueError:
            pass  # Empty package list handled elsewhere
    
    if args.dry_run:
        if not args.quiet:
            print("[DRY RUN] No packages were removed.")
        return 0  # Dry-run found work to do
    
    if not args.remove:
        if not args.quiet:
            print("Run with --dry-run to see what would be removed")
            print("Run with --remove to remove obsolete packages (requires sudo)")
        return 0  # List mode - showed what can be done
    
    # Confirm removal unless --yes is used
    if not args.yes and not args.quiet:
        print(f"\nAbout to remove {len(all_obsolete)} package(s).")
        response = input("Continue? [y/N]: ").strip().lower()
        if response not in ('y', 'yes'):
            print("Aborted.")
            return 0
        print()
    
    # Perform removal
    if not args.quiet:
        print()
        print("Dependencies resolved.")
        print("Removing packages...")
    
    try:
        results = remove_packages(
            all_obsolete,
            dry_run=False,
        )
        
        # Report progress for each package
        for pkg, status in results:
            reporter.print_removal_progress(pkg, status)
        
        # Count successes and failures
        success_count = sum(1 for _, status in results if status == RemovalStatus.SUCCESS)
        failed_count = len(results) - success_count
        
        # Print summary
        reporter.print_summary(success_count, failed_count)
        
        # Check if reboot is needed
        from .utils import needs_reboot
        
        # Reboot needed if: system flag OR running != latest
        reboot_needed = needs_reboot() or analysis.running_kernel != analysis.latest_kernel
        
        if reboot_needed:
            reporter.print_reboot_notice()
        
        if failed_count > 0:
            return -2  # dnf command failed
        
        if reboot_needed:
            return 2  # success but reboot required
        
        return 0  # success, no reboot needed
    
    except PermissionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return -1
    except Exception as e:
        print(f"Error during package removal: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return -2


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.
    
    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])
        
    Returns:
        int: Exit code:
            0 = success (removal completed or dry-run found work)
            1 = nothing to do (no obsolete packages found)
            -1 = insufficient privileges (not root)
            -2 = dnf command failed
            2 = reboot required
    """
    parser = create_parser()
    
    # If no arguments provided, show help
    if argv is None:
        argv = sys.argv[1:]
    
    if not argv:
        parser.print_help()
        return 0
    
    args = parser.parse_args(argv)
    
    # Validate argument combinations
    if args.quiet and args.verbose:
        parser.error("--quiet and --verbose cannot be used together")
        return 1
    
    if args.yes and not args.remove:
        parser.error("--yes can only be used with --remove")
        return 1
    
    # Main workflow
    try:
        # Set up reporter
        reporter = _setup_reporter(args)
        
        if not args.quiet:
            print("KernSweep v{}".format(__version__))
        
        # Detect and analyze kernels
        analysis, _ = _detect_and_analyze(args, reporter)
        
        # Display results
        if not args.quiet:
            print()
        
        reporter.print_analysis(analysis)
        
        # Handle obsolete packages if found
        if analysis.obsolete_kernels:
            return _handle_removal(args, reporter, analysis.obsolete_kernels, analysis)
        
        # No obsolete packages found
        if not args.quiet:
            print("✓ No obsolete kernels found.")
            print("  Your system is clean!")
        return 1  # Nothing to do
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

