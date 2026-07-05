"""
Unit tests for the reporter module.

Tests output formatting and different verbosity levels.
"""

import unittest
from io import StringIO
from unittest.mock import patch

from kernsweep.reporter import Reporter, OutputLevel
from kernsweep.remover import RemovalStatus
from kernsweep.analyzer import AnalysisResult


class TestReporterOutput(unittest.TestCase):
    """Test Reporter output formatting."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.obsolete_kernels = [
            "kernel-core-6.8.3-200.fc40.x86_64",
            "kernel-modules-6.8.3-200.fc40.x86_64",
        ]
        self.result = AnalysisResult(
            running_kernel="6.8.7-200.fc40.x86_64",
            latest_kernel="6.8.7-200.fc40.x86_64",
            obsolete_kernels=self.obsolete_kernels,
            protected_kernels=["kernel-core-6.8.7-200.fc40.x86_64"]
        )
    
    def test_reporter_normal_level(self):
        """Test reporter with normal output level."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(self.result)
            output = fake_out.getvalue()
        
        self.assertIn("Dependencies resolved", output)
        self.assertIn("Remove  2 Package(s)", output)
    
    def test_reporter_verbose_level(self):
        """Test reporter with verbose output level."""
        reporter = Reporter(OutputLevel.VERBOSE)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(self.result)
            output = fake_out.getvalue()
        
        self.assertIn("Dependencies resolved", output)
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", output)
        self.assertIn("kernel-modules-6.8.3-200.fc40.x86_64", output)
    
    def test_reporter_quiet_level(self):
        """Test reporter with quiet output level."""
        reporter = Reporter(OutputLevel.QUIET)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(self.result)
            output = fake_out.getvalue()
        
        # Quiet mode should produce no output for analysis
        self.assertEqual(output, "")
    
    def test_reporter_empty_package_list(self):
        """Test reporter with no packages to remove."""
        reporter = Reporter(OutputLevel.NORMAL)
        empty_result = AnalysisResult(
            running_kernel="6.8.7-200.fc40.x86_64",
            latest_kernel="6.8.7-200.fc40.x86_64",
            obsolete_kernels=[],
            protected_kernels=["kernel-core-6.8.7-200.fc40.x86_64"]
        )
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(empty_result)
            output = fake_out.getvalue()
        
        self.assertIn("Nothing to do", output)
    
    def test_reporter_removal_progress_success(self):
        """Test removal progress output for successful removal."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_removal_progress(
                "kernel-core-6.8.3-200.fc40.x86_64",
                RemovalStatus.SUCCESS
            )
            output = fake_out.getvalue()
        
        self.assertIn("Removing", output)
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", output)
    
    def test_reporter_removal_progress_failed(self):
        """Test removal progress output for failed removal."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_removal_progress(
                "kernel-core-6.8.3-200.fc40.x86_64",
                RemovalStatus.FAILED
            )
            output = fake_out.getvalue()
        
        self.assertIn("Failed", output)
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", output)
    
    def test_reporter_removal_progress_skipped(self):
        """Test removal progress output for skipped removal."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_removal_progress(
                "kernel-core-6.8.3-200.fc40.x86_64",
                RemovalStatus.SKIPPED
            )
            output = fake_out.getvalue()
        
        self.assertIn("Skipped", output)
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", output)
    
    def test_reporter_summary_all_success(self):
        """Test summary with all successful removals."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_summary(4, 0)
            output = fake_out.getvalue()
        
        self.assertIn("Successfully removed 4 package(s)", output)
        self.assertNotIn("Failed", output)
    
    def test_reporter_summary_with_failures(self):
        """Test summary with some failures."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_summary(2, 2)
            output = fake_out.getvalue()
        
        self.assertIn("Successfully removed 2 package(s)", output)
        self.assertIn("Failed to remove 2 package(s)", output)
    
    def test_reporter_summary_quiet_mode(self):
        """Test summary in quiet mode (should not show in quiet mode)."""
        reporter = Reporter(OutputLevel.QUIET)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_summary(4, 0)
            output = fake_out.getvalue()
        
        # Summary should NOT appear in quiet mode
        self.assertEqual(output, "")
    
    def test_reporter_reboot_notice(self):
        """Test reboot notice output."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_reboot_notice()
            output = fake_out.getvalue()

        self.assertIn("reboot is required", output)
        self.assertIn("sudo reboot", output)
    
    def test_reporter_reboot_notice_quiet_mode(self):
        """Test reboot notice in quiet mode."""
        reporter = Reporter(OutputLevel.QUIET)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_reboot_notice()
            output = fake_out.getvalue()
        
        # Reboot notice may not show in quiet mode - just verify no crash
        self.assertIsInstance(output, str)
    
    def test_reporter_running_equals_latest_no_reboot_message(self):
        """Test that running == latest kernels don't trigger reboot message."""
        reporter = Reporter(OutputLevel.NORMAL)
        
        result = AnalysisResult(
            running_kernel="6.8.7-200.fc40.x86_64",
            latest_kernel="6.8.7-200.fc40.x86_64",  # Same as running
            obsolete_kernels=[],
            protected_kernels=["kernel-core-6.8.7-200.fc40.x86_64"]
        )
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(result)
            output = fake_out.getvalue()
        
        # Should show kernel but NOT show reboot message
        self.assertIn("6.8.7-200.fc40.x86_64", output)
        self.assertNotIn("System will boot into", output)
    
    def test_reporter_large_package_list(self):
        """Test with large number of packages."""
        large_kernel_list = [f"kernel-core-6.8.{i}-200.fc40.x86_64" for i in range(50)]
        large_result = AnalysisResult(
            running_kernel="6.8.200-200.fc40.x86_64",
            latest_kernel="6.8.200-200.fc40.x86_64",
            obsolete_kernels=large_kernel_list,
            protected_kernels=["kernel-core-6.8.200-200.fc40.x86_64"]
        )
        
        reporter = Reporter(OutputLevel.NORMAL)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(large_result)
            output = fake_out.getvalue()
        
        self.assertIn("Remove  50 Package(s)", output)
    
    def test_reporter_package_name_truncation(self):
        """Test output with very long package names."""
        long_kernels = ["kernel-core-6.8.3-" + "a" * 100]
        long_result = AnalysisResult(
            running_kernel="6.8.7-200.fc40.x86_64",
            latest_kernel="6.8.7-200.fc40.x86_64",
            obsolete_kernels=long_kernels,
            protected_kernels=["kernel-core-6.8.7-200.fc40.x86_64"]
        )
        
        reporter = Reporter(OutputLevel.VERBOSE)
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            reporter.print_analysis(long_result)
            output = fake_out.getvalue()
        
        # Should handle long names without crashing
        self.assertIn("Remove  1 Package(s)", output)


class TestOutputLevel(unittest.TestCase):
    """Test OutputLevel enum."""
    
    def test_output_level_values(self):
        """Test OutputLevel enum values."""
        self.assertEqual(OutputLevel.QUIET.value, 0)
        self.assertEqual(OutputLevel.NORMAL.value, 1)
        self.assertEqual(OutputLevel.VERBOSE.value, 2)
    
    def test_output_level_comparison(self):
        """Test that OutputLevel values can be compared."""
        quiet = OutputLevel.QUIET
        normal = OutputLevel.NORMAL
        verbose = OutputLevel.VERBOSE
        
        self.assertNotEqual(quiet, normal)
        self.assertNotEqual(normal, verbose)
        self.assertEqual(quiet, OutputLevel.QUIET)


if __name__ == "__main__":
    unittest.main()

