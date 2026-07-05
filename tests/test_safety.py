"""
Unit tests for safety validation functions.
"""

import unittest
from kernsweep.analyzer import validate_removal_safety, get_protected_packages
from kernsweep.detector import KernelInfo


class TestValidateRemovalSafety(unittest.TestCase):
    """Test safety validation logic."""
    
    def setUp(self):
        """Set up test kernels."""
        self.all_kernels = [
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64", True, False),
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", False, False),
            KernelInfo("6.8.3-200.fc40.x86_64", "kernel-core-6.8.3-200.fc40.x86_64", False, False),
            KernelInfo("6.8.1-200.fc40.x86_64", "kernel-core-6.8.1-200.fc40.x86_64", False, False),
        ]
        self.running_kernel = "6.8.7-200.fc40.x86_64"
        self.latest_kernel = "6.8.7-200.fc40.x86_64"
    
    def test_safe_removal(self):
        """Test that safe removal passes validation."""
        packages_to_remove = [
            "kernel-core-6.8.5-200.fc40.x86_64",
            "kernel-core-6.8.3-200.fc40.x86_64",
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            self.running_kernel,
            self.latest_kernel,
            self.all_kernels
        )
        
        self.assertTrue(is_safe)
        self.assertEqual(error_msg, "")
    
    def test_running_kernel_protection(self):
        """Test that running kernel cannot be removed."""
        packages_to_remove = [
            "kernel-core-6.8.7-200.fc40.x86_64",  # Running kernel
            "kernel-core-6.8.5-200.fc40.x86_64",
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            self.running_kernel,
            self.latest_kernel,
            self.all_kernels
        )
        
        self.assertFalse(is_safe)
        self.assertIn("Running kernel", error_msg)
        self.assertIn("6.8.7-200.fc40.x86_64", error_msg)
    
    def test_latest_kernel_protection(self):
        """Test that latest kernel cannot be removed."""
        # Make running != latest
        all_kernels = [
            KernelInfo("6.8.9-200.fc40.x86_64", "kernel-core-6.8.9-200.fc40.x86_64", False, True),
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64", True, False),
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", False, False),
        ]
        
        packages_to_remove = [
            "kernel-core-6.8.9-200.fc40.x86_64",  # Latest kernel
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            "6.8.7-200.fc40.x86_64",
            "6.8.9-200.fc40.x86_64",
            all_kernels
        )
        
        self.assertFalse(is_safe)
        self.assertIn("Latest kernel", error_msg)
        self.assertIn("6.8.9-200.fc40.x86_64", error_msg)
    
    def test_minimum_kernel_protection(self):
        """Test that at least one kernel must remain."""
        # Only two kernels, both protected
        all_kernels = [
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64", True, True),
            KernelInfo("6.8.5-200.fc40.x86_64", "kernel-core-6.8.5-200.fc40.x86_64", False, False),
        ]
        
        # Try to remove the non-protected one (would leave only protected)
        packages_to_remove = [
            "kernel-core-6.8.5-200.fc40.x86_64",
        ]
        
        # This should actually pass - we're left with 1 kernel
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            "6.8.7-200.fc40.x86_64",
            "6.8.7-200.fc40.x86_64",
            all_kernels
        )
        
        self.assertTrue(is_safe)
    
    def test_no_kernels_remaining(self):
        """Test that removal fails if no kernels would remain."""
        # Only one kernel
        all_kernels = [
            KernelInfo("6.8.7-200.fc40.x86_64", "kernel-core-6.8.7-200.fc40.x86_64", True, True),
        ]
        
        # Try to remove it (shouldn't be possible but let's test the check)
        packages_to_remove = [
            "kernel-core-6.8.7-200.fc40.x86_64",
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            "6.8.7-200.fc40.x86_64",
            "6.8.7-200.fc40.x86_64",
            all_kernels
        )
        
        # Should fail on running kernel check first
        self.assertFalse(is_safe)
        self.assertIn("Running kernel", error_msg)
    
    def test_bulk_removal_warning(self):
        """Test that removing many kernels triggers warning."""
        # Create 8 kernels
        all_kernels = [
            KernelInfo(f"6.8.{90+i}-200.fc40.x86_64", f"kernel-core-6.8.{90+i}-200.fc40.x86_64",
                      i == 7, i == 7)
            for i in range(8)
        ]
        
        # Try to remove 6 of them
        packages_to_remove = [
            f"kernel-core-6.8.{90+i}-200.fc40.x86_64" for i in range(6)
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            "6.8.97-200.fc40.x86_64",
            "6.8.97-200.fc40.x86_64",
            all_kernels
        )
        
        self.assertFalse(is_safe)
        self.assertIn("6 kernels", error_msg)
        self.assertIn("excessive", error_msg)
    
    def test_kernel_modules_in_removal_list(self):
        """Test that kernel-modules packages don't interfere with safety checks."""
        packages_to_remove = [
            "kernel-core-6.8.5-200.fc40.x86_64",
            "kernel-modules-6.8.5-200.fc40.x86_64",
            "kernel-core-6.8.3-200.fc40.x86_64",
            "kernel-modules-6.8.3-200.fc40.x86_64",
        ]
        
        is_safe, error_msg = validate_removal_safety(
            packages_to_remove,
            self.running_kernel,
            self.latest_kernel,
            self.all_kernels
        )
        
        # Should be safe - only 2 kernel-core packages being removed, not excessive
        self.assertTrue(is_safe)
        self.assertEqual(error_msg, "")


class TestGetProtectedPackages(unittest.TestCase):
    """Test protected package identification."""
    
    def test_same_kernel_running_and_latest(self):
        """Test when running kernel is also latest."""
        protected = get_protected_packages(
            "6.8.7-200.fc40.x86_64",
            "6.8.7-200.fc40.x86_64"
        )
        
        expected = {
            "kernel-core-6.8.7-200.fc40.x86_64",
            "kernel-modules-6.8.7-200.fc40.x86_64",
            "kernel-modules-extra-6.8.7-200.fc40.x86_64",
            "kernel-6.8.7-200.fc40.x86_64",
        }
        
        self.assertEqual(protected, expected)
    
    def test_different_kernels(self):
        """Test when running and latest are different."""
        protected = get_protected_packages(
            "6.8.5-200.fc40.x86_64",
            "6.8.7-200.fc40.x86_64"
        )
        
        expected = {
            "kernel-core-6.8.5-200.fc40.x86_64",
            "kernel-modules-6.8.5-200.fc40.x86_64",
            "kernel-modules-extra-6.8.5-200.fc40.x86_64",
            "kernel-6.8.5-200.fc40.x86_64",
            "kernel-core-6.8.7-200.fc40.x86_64",
            "kernel-modules-6.8.7-200.fc40.x86_64",
            "kernel-modules-extra-6.8.7-200.fc40.x86_64",
            "kernel-6.8.7-200.fc40.x86_64",
        }
        
        self.assertEqual(protected, expected)


if __name__ == "__main__":
    unittest.main()

