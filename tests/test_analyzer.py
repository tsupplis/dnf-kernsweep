"""
Unit tests for the analyzer module.

Tests kernel obsolescence analysis logic.
"""

import unittest

from kernsweep.analyzer import (
    analyze_kernels,
    AnalysisResult,
)
from kernsweep.detector import KernelInfo


class TestAnalyzeKernels(unittest.TestCase):
    """Tests for analyze_kernels function."""
    
    def test_analyze_kernels_basic(self):
        """Test basic kernel analysis with running and latest different."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", is_running=True),
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64"),
            KernelInfo("6.8.3-200.fc40.x86_64", "kernel-core-6.8.3-200.fc40.x86_64"),
        ]
        
        result = analyze_kernels(kernels, "6.8.7-200.fc40.x86_64")
        
        self.assertEqual(result.running_kernel, "6.8.5-200.fc40.x86_64")
        self.assertEqual(result.latest_kernel, "6.8.7-200.fc40.x86_64")
        self.assertEqual(len(result.obsolete_kernels), 1)
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", result.obsolete_kernels)
        self.assertEqual(len(result.protected_kernels), 2)
    
    def test_analyze_kernels_running_is_latest(self):
        """Test when running kernel is also the latest."""
        kernels = [
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64", is_running=True),
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64"),
            KernelInfo("6.8.3-200.fc40.x86_64", "kernel-core-6.8.3-200.fc40.x86_64"),
        ]
        
        result = analyze_kernels(kernels, "6.8.7-200.fc40.x86_64")
        
        self.assertEqual(result.running_kernel, "6.8.7-200.fc40.x86_64")
        self.assertEqual(result.latest_kernel, "6.8.7-200.fc40.x86_64")
        self.assertEqual(len(result.obsolete_kernels), 2)
        self.assertEqual(len(result.protected_kernels), 1)
    
    def test_analyze_kernels_only_two_kernels(self):
        """Test with only running and one other kernel."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", is_running=True),
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64"),
        ]
        
        result = analyze_kernels(kernels, "6.8.7-200.fc40.x86_64")
        
        self.assertEqual(len(result.obsolete_kernels), 0)
        self.assertEqual(len(result.protected_kernels), 2)
    
    def test_analyze_kernels_no_running_kernel(self):
        """Test error handling when no running kernel is marked."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64"),
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64"),
        ]
        
        with self.assertRaises(ValueError) as ctx:
            analyze_kernels(kernels, "6.8.7-200.fc40.x86_64")
        
        self.assertIn("Running kernel not found", str(ctx.exception))
    
    def test_analyze_kernels_empty_list(self):
        """Test handling of empty kernel list (e.g., container environment)."""
        result = analyze_kernels([], "")
        
        # Should return empty result, not raise an error
        self.assertEqual(result.running_kernel, "")
        self.assertEqual(result.latest_kernel, "")
        self.assertEqual(len(result.obsolete_kernels), 0)
        self.assertEqual(len(result.protected_kernels), 0)
    
    def test_analyze_kernels_all_same_version(self):
        """Test when all kernels have the same version (e.g., kernel + kernel-core)."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", is_running=True),
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-modules-6.8.5-200.fc40.x86_64"),
        ]
        
        result = analyze_kernels(kernels, "6.8.5-200.fc40.x86_64")
        
        # Both should be protected (running and latest are the same)
        self.assertEqual(result.running_kernel, "6.8.5-200.fc40.x86_64")
        self.assertEqual(result.latest_kernel, "6.8.5-200.fc40.x86_64")
        self.assertEqual(len(result.obsolete_kernels), 0)
    
    def test_analyze_kernels_many_obsolete(self):
        """Test with many obsolete kernels - all should be removable in one run."""
        kernels = [
            KernelInfo("6.8.100-200.fc40.x86_64", "kernel-core-6.8.100-200.fc40.x86_64", is_running=True),
        ] + [
            KernelInfo(f"6.8.{i}-200.fc40.x86_64", f"kernel-core-6.8.{i}-200.fc40.x86_64")
            for i in range(50, 60)
        ]
        
        # No bulk-removal cap - all 10 obsolete kernels should be reported
        result = analyze_kernels(kernels, "6.8.100-200.fc40.x86_64")
        
        self.assertEqual(len(result.obsolete_kernels), 10)
    
    def test_analyze_kernels_single_kernel_only(self):
        """Test with only one kernel (running and latest)."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", is_running=True),
        ]
        
        result = analyze_kernels(kernels, "6.8.5-200.fc40.x86_64")
        
        self.assertEqual(result.running_kernel, "6.8.5-200.fc40.x86_64")
        self.assertEqual(result.latest_kernel, "6.8.5-200.fc40.x86_64")
        self.assertEqual(len(result.obsolete_kernels), 0)
    
    def test_analyze_kernels_marks_latest_flag(self):
        """Test that installed packages matching the latest version are flagged."""
        kernels = [
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", is_running=True),
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64"),
        ]
        
        analyze_kernels(kernels, "6.8.7-200.fc40.x86_64")
        
        self.assertTrue(kernels[1].is_latest)
        self.assertFalse(kernels[0].is_latest)


if __name__ == '__main__':
    unittest.main()

