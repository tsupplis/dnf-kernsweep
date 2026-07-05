"""
Unit tests for the detector module.

Tests kernel detection functionality with mocked rpm/dnf system calls.
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess

from kernsweep.detector import (
    get_running_kernel,
    get_installed_kernels,
    get_latest_installed_kernel_version,
    KernelInfo,
)


class TestGetRunningKernel(unittest.TestCase):
    """Tests for get_running_kernel function."""
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_running_kernel_success(self, mock_run):
        """Test successful kernel detection."""
        mock_run.return_value = MagicMock(
            stdout="6.8.5-200.fc40.x86_64\n",
            returncode=0,
        )
        
        result = get_running_kernel()
        
        self.assertEqual(result, "6.8.5-200.fc40.x86_64")
        mock_run.assert_called_once_with(
            ["uname", "-r"],
            capture_output=True,
            text=True,
            check=True,
        )
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_running_kernel_empty_output(self, mock_run):
        """Test handling of empty uname output."""
        mock_run.return_value = MagicMock(
            stdout="",
            returncode=0,
        )
        
        with self.assertRaises(RuntimeError) as ctx:
            get_running_kernel()
        
        self.assertIn("empty", str(ctx.exception).lower())
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_running_kernel_command_failure(self, mock_run):
        """Test handling of command execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "uname")
        
        with self.assertRaises(RuntimeError) as ctx:
            get_running_kernel()
        
        self.assertIn("Failed to detect", str(ctx.exception))


class TestGetInstalledKernels(unittest.TestCase):
    """Tests for get_installed_kernels function."""
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_installed_kernels_success(self, mock_run):
        """Test successful kernel package detection."""
        mock_run.return_value = MagicMock(
            stdout=(
                "kernel-core 5.14.0-362.8.1.el9_3.x86_64\n"
                "kernel-modules 5.14.0-362.8.1.el9_3.x86_64\n"
                "kernel-core 5.14.0-362.18.1.el9_3.x86_64\n"
                "kernel-modules 5.14.0-362.18.1.el9_3.x86_64\n"
                "some-other-package 1.0.0-1.el9.x86_64\n"
            ),
            returncode=0,
        )
        
        result = get_installed_kernels()
        
        self.assertEqual(len(result), 4)
        self.assertIsInstance(result[0], KernelInfo)
        
        versions = {k.version for k in result}
        self.assertIn("5.14.0-362.8.1.el9_3.x86_64", versions)
        self.assertIn("5.14.0-362.18.1.el9_3.x86_64", versions)
        
        packages = {k.package_name for k in result}
        self.assertIn("kernel-core-5.14.0-362.8.1.el9_3.x86_64", packages)
        self.assertIn("kernel-modules-5.14.0-362.18.1.el9_3.x86_64", packages)
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_installed_kernels_no_kernels(self, mock_run):
        """Test handling when no kernel packages found (container environment)."""
        mock_run.return_value = MagicMock(
            stdout="some-other-package 1.0.0-1.el9.x86_64\n",
            returncode=0,
        )
        
        # Should return empty list, not raise error (container environment)
        result = get_installed_kernels()
        
        self.assertEqual(len(result), 0)
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_installed_kernels_filters_unrelated_names(self, mock_run):
        """Test that non-kernel packages are filtered out."""
        mock_run.return_value = MagicMock(
            stdout=(
                "kernel-core 5.14.0-362.18.1.el9_3.x86_64\n"
                "kernel-devel 5.14.0-362.18.1.el9_3.x86_64\n"
                "kernel-headers 5.14.0-362.18.1.el9_3.x86_64\n"
            ),
            returncode=0,
        )
        
        result = get_installed_kernels()
        
        # kernel-devel and kernel-headers are deliberately excluded
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].version, "5.14.0-362.18.1.el9_3.x86_64")
        self.assertEqual(result[0].package_name, "kernel-core-5.14.0-362.18.1.el9_3.x86_64")
    
    @patch('kernsweep.detector.subprocess.run')
    def test_get_installed_kernels_all_package_names(self, mock_run):
        """Test detection of all four installonly kernel package names."""
        mock_run.return_value = MagicMock(
            stdout=(
                "kernel 6.8.5-200.fc40.x86_64\n"
                "kernel-core 6.8.5-200.fc40.x86_64\n"
                "kernel-modules 6.8.5-200.fc40.x86_64\n"
                "kernel-modules-extra 6.8.5-200.fc40.x86_64\n"
            ),
            returncode=0,
        )
        
        result = get_installed_kernels()
        
        self.assertEqual(len(result), 4)
        packages = {k.package_name for k in result}
        self.assertIn("kernel-6.8.5-200.fc40.x86_64", packages)
        self.assertIn("kernel-core-6.8.5-200.fc40.x86_64", packages)
        self.assertIn("kernel-modules-6.8.5-200.fc40.x86_64", packages)
        self.assertIn("kernel-modules-extra-6.8.5-200.fc40.x86_64", packages)


class TestGetLatestInstalledKernelVersion(unittest.TestCase):
    """Tests for get_latest_installed_kernel_version function."""
    
    @patch('kernsweep.detector.run_command')
    def test_get_latest_installed_kernel_version_success(self, mock_run_command):
        """Test successful latest kernel detection via rpm --last."""
        mock_run_command.return_value = (
            0,
            "kernel-core-6.8.7-200.fc40.x86_64                 Mon 01 Jan 2024\n"
            "kernel-core-6.8.5-200.fc40.x86_64                 Sun 01 Dec 2023\n",
            "",
        )
        
        result = get_latest_installed_kernel_version()
        
        self.assertEqual(result, "6.8.7-200.fc40.x86_64")
        mock_run_command.assert_called_once_with(
            ["rpm", "-q", "kernel-core", "--last"], check=False
        )
    
    @patch('kernsweep.detector.run_command')
    def test_get_latest_installed_kernel_version_falls_back(self, mock_run_command):
        """Test fallback through package names when the first has no match."""
        def side_effect(cmd, check=False):
            if cmd[2] == "kernel-core":
                return (1, "", "package kernel-core is not installed")
            if cmd[2] == "kernel-modules-extra":
                return (1, "", "package kernel-modules-extra is not installed")
            if cmd[2] == "kernel-modules":
                return (0, "kernel-modules-6.8.5-200.fc40.x86_64    Sun 01 Dec 2023\n", "")
            return (1, "", "")
        
        mock_run_command.side_effect = side_effect
        
        result = get_latest_installed_kernel_version()
        
        self.assertEqual(result, "6.8.5-200.fc40.x86_64")
    
    @patch('kernsweep.detector.run_command')
    def test_get_latest_installed_kernel_version_none_found(self, mock_run_command):
        """Test error when no kernel package can be queried."""
        mock_run_command.return_value = (1, "", "not installed")
        
        with self.assertRaises(RuntimeError) as ctx:
            get_latest_installed_kernel_version()
        
        self.assertIn("Unable to determine", str(ctx.exception))


if __name__ == '__main__':
    unittest.main()

