"""
Integration tests for the CLI.

Tests the complete workflow with mocked system calls.
"""

import unittest
from unittest.mock import patch, MagicMock, call
from io import StringIO

from kernsweep.cli import main


def _rpm_qa_output(*name_version_pairs):
    """Build fake 'rpm -qa --qf' output from (name, version) pairs."""
    return "".join(f"{name} {version}\n" for name, version in name_version_pairs)


def _rpm_last(cmd, latest_by_name):
    """Simulate 'rpm -q <name> --last' for the given package name."""
    package_name = cmd[2]
    version = latest_by_name.get(package_name)
    if not version:
        return MagicMock(returncode=1, stdout="", stderr="package is not installed")
    return MagicMock(
        returncode=0,
        stdout=f"{package_name}-{version}    Mon 01 Jan 2024\n",
        stderr="",
    )


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for the CLI workflow."""
    
    @patch('kernsweep.detector.subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_dry_run_with_obsolete_kernels(self, mock_stdout, mock_run):
        """Test dry-run mode with obsolete kernels present."""
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --dry-run
        exit_code = main(["--dry-run"])
        
        # Check results
        self.assertEqual(exit_code, 0)
        output = mock_stdout.getvalue()
        
        # Verify key information in output
        self.assertIn("6.8.1-200.fc40.x86_64", output)  # Obsolete kernel version
        self.assertIn("Remove", output)  # dnf-style message
        self.assertIn("DRY RUN", output)
    
    @patch('kernsweep.detector.subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_no_obsolete_kernels(self, mock_stdout, mock_run):
        """Test when system is clean with no obsolete kernels."""
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.7-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(("kernel-core", "6.8.7-200.fc40.x86_64")),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI
        exit_code = main(["--dry-run"])

        # Check results - exit code 1 means nothing to do
        self.assertEqual(exit_code, 1)
        output = mock_stdout.getvalue()
        
        # Verify clean system message
        self.assertIn("No obsolete", output)
        self.assertIn("clean", output.lower())
    
    @patch('kernsweep.detector.subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_verbose_mode(self, mock_stdout, mock_run):
        """Test verbose output mode."""
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --verbose
        exit_code = main(["--dry-run", "--verbose"])

        # Check results - exit code 1 means nothing to do (both kernels protected)
        self.assertEqual(exit_code, 1)
        output = mock_stdout.getvalue()
        
        # Verify verbose messages
        self.assertIn("Detecting running kernel", output)
        self.assertIn("Scanning installed kernels", output)
        self.assertIn("Analyzing kernels", output)
    
    @patch('kernsweep.detector.subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_quiet_mode(self, mock_stdout, mock_run):
        """Test quiet output mode."""
        latest_by_name = {"kernel-core": "6.8.3-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(("kernel-core", "6.8.3-200.fc40.x86_64")),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --quiet
        exit_code = main(["--dry-run", "--quiet"])

        # Check results - exit code 1 means nothing to do
        self.assertEqual(exit_code, 1)
        output = mock_stdout.getvalue()
        
        # Verify minimal output
        self.assertEqual(output.strip(), "")
    
    @patch('kernsweep.detector.subprocess.run')
    def test_cli_running_is_latest(self, mock_run):
        """Test when running kernel is the latest."""
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.7-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI
        exit_code = main(["--dry-run"])
        
        # Should succeed and identify 2 obsolete kernels, no reboot required
        self.assertEqual(exit_code, 0)
    
    @patch('kernsweep.cli.check_sudo')
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_remove_without_sudo(self, mock_stdout, mock_run, mock_sudo):
        """Test --remove without sudo privileges."""
        mock_sudo.return_value = False
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --remove
        exit_code = main(["--remove"])

        # Should fail with permission error - exit code -1
        self.assertEqual(exit_code, -1)
        # dnf should not have been called (only uname and rpm)
        calls = [str(c) for c in mock_run.call_args_list]
        self.assertNotIn("dnf", str(calls))
    
    @patch('builtins.input')
    @patch('kernsweep.remover.check_sudo')
    @patch('kernsweep.cli.check_sudo')
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_remove_with_confirmation_yes(self, mock_stdout, mock_run, mock_cli_sudo, mock_remover_sudo, mock_input):
        """Test --remove with user confirmation (yes)."""
        mock_cli_sudo.return_value = True
        mock_remover_sudo.return_value = True
        mock_input.return_value = "y"
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
            elif cmd[0] == "dnf":
                return MagicMock(returncode=0, stdout="", stderr="")
            elif cmd[0] == "needs-restart":
                return MagicMock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --remove
        exit_code = main(["--remove"])

        # Should succeed with exit code 2 (reboot required since running != latest)
        self.assertEqual(exit_code, 2)
        # User should be prompted
        mock_input.assert_called_once()
        
        # dnf should have been called
        calls = [str(c) for c in mock_run.call_args_list]
        self.assertIn("dnf", str(calls))
    
    @patch('builtins.input')
    @patch('kernsweep.cli.check_sudo')
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_remove_with_confirmation_no(self, mock_stdout, mock_run, mock_sudo, mock_input):
        """Test --remove with user confirmation (no/abort)."""
        mock_sudo.return_value = True
        mock_input.return_value = "n"
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --remove
        exit_code = main(["--remove"])
        
        # Should succeed (user aborted)
        self.assertEqual(exit_code, 0)
        
        # User should be prompted
        mock_input.assert_called_once()
        
        # dnf should NOT have been called (only uname and rpm)
        calls = [str(c) for c in mock_run.call_args_list]
        self.assertNotIn("dnf", str(calls))
        
        # Check for "Aborted" message
        output = mock_stdout.getvalue()
        self.assertIn("Aborted", output)
    
    @patch('kernsweep.remover.check_sudo')
    @patch('kernsweep.cli.check_sudo')
    @patch('subprocess.run')
    @patch('sys.stdout', new_callable=StringIO)
    def test_cli_remove_with_yes_flag(self, mock_stdout, mock_run, mock_cli_sudo, mock_remover_sudo):
        """Test --remove --yes (no confirmation prompt)."""
        mock_cli_sudo.return_value = True
        mock_remover_sudo.return_value = True
        latest_by_name = {"kernel-core": "6.8.7-200.fc40.x86_64"}
        
        def mock_subprocess(cmd, **kwargs):
            if cmd[0] == "uname":
                return MagicMock(stdout="6.8.3-200.fc40.x86_64\n", returncode=0)
            elif cmd[0] == "rpm" and cmd[1] == "-qa":
                return MagicMock(
                    stdout=_rpm_qa_output(
                        ("kernel-core", "6.8.1-200.fc40.x86_64"),
                        ("kernel-core", "6.8.3-200.fc40.x86_64"),
                        ("kernel-core", "6.8.7-200.fc40.x86_64"),
                        ("kernel-modules", "6.8.1-200.fc40.x86_64"),
                    ),
                    returncode=0,
                )
            elif cmd[0] == "rpm" and cmd[1] == "-q":
                return _rpm_last(cmd, latest_by_name)
            elif cmd[0] == "dnf":
                return MagicMock(returncode=0, stdout="", stderr="")
            elif cmd[0] == "needs-restart":
                return MagicMock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = mock_subprocess
        
        # Run CLI with --remove --yes
        exit_code = main(["--remove", "--yes"])

        # Should succeed with exit code 2 (reboot required)
        self.assertEqual(exit_code, 2)
        # dnf should have been called with -y flag
        dnf_calls = [c for c in mock_run.call_args_list if c[0][0][0] == "dnf"]
        self.assertEqual(len(dnf_calls), 1)
        call_args = dnf_calls[0][0][0]
        self.assertIn("-y", call_args)
        self.assertIn("kernel-core-6.8.1-200.fc40.x86_64", call_args)
        self.assertIn("kernel-modules-6.8.1-200.fc40.x86_64", call_args)


if __name__ == '__main__':
    unittest.main()

