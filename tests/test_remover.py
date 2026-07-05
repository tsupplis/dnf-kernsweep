"""
Unit tests for the remover module.

Tests package removal functionality with mocked dnf commands.
"""

import unittest
from unittest.mock import patch, MagicMock
import subprocess

from kernsweep.remover import (
    check_sudo,
    generate_dnf_command,
    remove_packages,
    RemovalStatus,
)


class TestCheckSudo(unittest.TestCase):
    """Tests for check_sudo function."""
    
    @patch('kernsweep.remover.os.geteuid')
    def test_check_sudo_as_root(self, mock_geteuid):
        """Test sudo check when running as root."""
        mock_geteuid.return_value = 0
        
        result = check_sudo()
        
        self.assertTrue(result)
    
    @patch('kernsweep.remover.os.geteuid')
    def test_check_sudo_as_user(self, mock_geteuid):
        """Test sudo check when running as normal user."""
        mock_geteuid.return_value = 1000
        
        result = check_sudo()
        
        self.assertFalse(result)
    
    @patch('kernsweep.remover.os.geteuid')
    def test_check_sudo_attribute_error(self, mock_geteuid):
        """Test sudo check on systems without geteuid (Windows)."""
        mock_geteuid.side_effect = AttributeError()
        
        result = check_sudo()
        
        self.assertFalse(result)


class TestGenerateDnfCommand(unittest.TestCase):
    """Tests for generate_dnf_command function."""
    
    def test_generate_dnf_command_basic(self):
        """Test basic dnf command generation."""
        packages = ["kernel-core-6.8.3-200.fc40.x86_64", "kernel-modules-6.8.3-200.fc40.x86_64"]
        
        result = generate_dnf_command(packages)
        
        self.assertEqual(result[0], "dnf")
        self.assertEqual(result[1], "-y")
        self.assertEqual(result[2], "remove")
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", result)
        self.assertIn("kernel-modules-6.8.3-200.fc40.x86_64", result)
    
    def test_generate_dnf_command_empty_packages(self):
        """Test error handling with empty package list."""
        with self.assertRaises(ValueError) as ctx:
            generate_dnf_command([])
        
        self.assertIn("No packages", str(ctx.exception))
    
    def test_generate_dnf_command_single_package(self):
        """Test command generation with single package."""
        result = generate_dnf_command(["test-package"])
        
        # dnf -y remove test-package
        self.assertEqual(len(result), 4)
        self.assertEqual(result[-1], "test-package")
        self.assertEqual(result[1], "-y")
        self.assertEqual(result[2], "remove")


class TestRemovePackages(unittest.TestCase):
    """Tests for remove_packages function."""
    
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_dry_run(self, mock_sudo):
        """Test dry-run mode (no actual removal)."""
        packages = ["kernel-core-6.8.3-200.fc40.x86_64", "kernel-modules-6.8.3-200.fc40.x86_64"]
        
        results = remove_packages(packages, dry_run=True)
        
        # Dry run should not check sudo
        mock_sudo.assert_not_called()
        
        # All packages should succeed in dry run
        self.assertEqual(len(results), 2)
        for pkg, status in results:
            self.assertEqual(status, RemovalStatus.SUCCESS)
    
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_no_sudo(self, mock_sudo):
        """Test error when running without sudo."""
        mock_sudo.return_value = False
        packages = ["kernel-core-6.8.3-200.fc40.x86_64"]
        
        with self.assertRaises(PermissionError) as ctx:
            remove_packages(packages, dry_run=False)
        
        self.assertIn("Root privileges required", str(ctx.exception))
    
    @patch('kernsweep.remover.subprocess.run')
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_success(self, mock_sudo, mock_run):
        """Test successful package removal."""
        mock_sudo.return_value = True
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Packages removed successfully\n",
            stderr="",
        )
        
        packages = ["kernel-core-6.8.3-200.fc40.x86_64"]
        results = remove_packages(packages, dry_run=False)
        
        # Check dnf was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "dnf")
        self.assertEqual(call_args[1], "-y")
        self.assertEqual(call_args[2], "remove")
        self.assertIn("kernel-core-6.8.3-200.fc40.x86_64", call_args)
        
        # Check results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "kernel-core-6.8.3-200.fc40.x86_64")
        self.assertEqual(results[0][1], RemovalStatus.SUCCESS)
    
    @patch('kernsweep.remover.subprocess.run')
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_dnf_failure(self, mock_sudo, mock_run):
        """Test handling of dnf command failure."""
        mock_sudo.return_value = True
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Unable to find a match\n",
        )
        
        packages = ["nonexistent-package"]
        
        with self.assertRaises(RuntimeError) as ctx:
            remove_packages(packages, dry_run=False)
        
        self.assertIn("dnf remove failed", str(ctx.exception))
        self.assertIn("1", str(ctx.exception))
    
    @patch('kernsweep.remover.subprocess.run')
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_subprocess_error(self, mock_sudo, mock_run):
        """Test handling of subprocess execution error."""
        mock_sudo.return_value = True
        mock_run.side_effect = subprocess.SubprocessError("Command not found")
        
        packages = ["kernel-core-6.8.3-200.fc40.x86_64"]
        
        with self.assertRaises(RuntimeError) as ctx:
            remove_packages(packages, dry_run=False)
        
        self.assertIn("Failed to execute dnf", str(ctx.exception))
    
    def test_remove_packages_empty_list(self):
        """Test removal with empty package list."""
        results = remove_packages([], dry_run=True)
        
        self.assertEqual(len(results), 0)
    
    @patch('kernsweep.remover.subprocess.run')
    @patch('kernsweep.remover.check_sudo')
    def test_remove_packages_multiple(self, mock_sudo, mock_run):
        """Test removal of multiple packages."""
        mock_sudo.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        packages = [
            "kernel-core-6.8.3-200.fc40.x86_64",
            "kernel-core-6.8.1-200.fc40.x86_64",
            "kernel-modules-6.8.3-200.fc40.x86_64",
        ]
        results = remove_packages(packages, dry_run=False)
        
        # All packages should be in single dnf command
        call_args = mock_run.call_args[0][0]
        for pkg in packages:
            self.assertIn(pkg, call_args)
        
        # Check results
        self.assertEqual(len(results), 3)
        for _, status in results:
            self.assertEqual(status, RemovalStatus.SUCCESS)


if __name__ == '__main__':
    unittest.main()

