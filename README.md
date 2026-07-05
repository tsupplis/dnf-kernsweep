# KernSweep

A lightweight command-line tool to detect and remove obsolete Linux kernels on Red Hat / Fedora based systems.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python Version](https://img.shields.io/badge/python-3-blue.svg)

## Overview

KernSweep helps keep your RHEL, CentOS Stream, Fedora, Rocky Linux, or AlmaLinux system clean by identifying and removing old kernel packages that are no longer needed, while protecting the currently running kernel and the latest installed kernel.

## Features

- 🔍 Detects currently running kernel
- 📦 Identifies all installed kernel packages (kernel, kernel-core, kernel-modules, kernel-modules-extra)
- 🧹 Safely removes obsolete kernels (keeping running and latest)
- 🛡️ Built-in safety checks to prevent system breakage
- 📊 dnf-style output and reporting
- 🔄 Reboot detection
- 🧪 Dry-run mode for safe testing
- 🐍 Pure Python with no external dependencies

## Installation

### From source

```bash
git clone https://github.com/tsupplis/kernsweep.git
cd kernsweep
pip install -e .
```

### For development

```bash
pip install -e ".[dev]"
```

## Usage

### Show help

```bash
kernsweep
# or
kernsweep --help
```

### Dry run (see what would be removed)

```bash
kernsweep --dry-run
```

### Remove obsolete kernels

```bash
sudo kernsweep --remove
```

### Remove with automatic yes to prompts

```bash
sudo kernsweep --remove --yes
```

### Verbose output

```bash
kernsweep --dry-run --verbose
```

## Command-line Options

- `--dry-run` - Show what would be removed without actually removing anything
- `--remove` - Remove obsolete kernels (requires sudo)
- `-v, --verbose` - Enable verbose output
- `-q, --quiet` - Suppress non-essential output
- `--yes` - Assume yes to all prompts (use with --remove)
- `--version` - Show version information

## Exit Codes

KernSweep uses meaningful exit codes for automation and scripting:

- `0` - Success (removal completed or dry-run found work to do)
- `1` - Nothing to do (no obsolete packages found)
- `-1` - Insufficient privileges (not running as root)
- `-2` - dnf command failed during removal
- `2` - Reboot required (successful removal but system needs restart)

## Safety Features

KernSweep includes multiple safety mechanisms to prevent system breakage:

1. **Protected Kernels**: Never removes the running kernel or the latest installed kernel
2. **Double-Check Validation**: Validates removal list before execution to ensure protected kernels are not included
3. **Minimum Kernel Protection**: Ensures at least one kernel remains on the system after removal
4. **Bulk Removal Warning**: Prevents accidental removal of excessive numbers of kernels (>5)
5. **Reboot Detection**: Detects when system requires reboot after kernel updates
6. **Dry-run Mode**: Test operations before making changes
7. **Confirmation Prompts**: Asks for confirmation before removal (unless `--yes` is used)
8. **Privilege Checks**: Ensures proper permissions before attempting removal
9. **installonly-only sweeping**: Only considers the stacked/versioned kernel packages
   (`kernel`, `kernel-core`, `kernel-modules`, `kernel-modules-extra`). Packages like
   `kernel-devel` and `kernel-headers` are deliberately excluded since they are singleton
   packages that dnf upgrades in place and aren't always released for every kernel-core
   point release.

## Requirements

- Python 3.7 or higher
- Linux system with rpm and dnf (RHEL, CentOS Stream, Fedora, Rocky Linux, AlmaLinux, ...)
- sudo privileges (for removal operations)

## Test Coverage

The project includes comprehensive unit tests covering:
- Kernel detection and analysis (including edge cases)
- Output formatting and reporting
- Package removal operations
- System detection
- Safety validation
- CLI integration
- Utility functions

Coverage by module:
- remover.py
- analyzer.py
- utils.py
- reporter.py
- detector.py
- cli.py

## Ansible Integration

KernSweep includes a self-contained Ansible module for automated kernel cleanup across multiple hosts.

### Building the Ansible Module

```bash
python3 build-ansible-module
```

This creates a self-contained module in `ansible/lib/dnf_kernsweep.py` with all dependencies embedded.

### Using with Ansible

```yaml
- name: Remove obsolete kernels
  hosts: all
  become: yes
  tasks:
    - name: Clean up old kernels
      dnf_kernsweep:
        state: absent
```

Run the playbook:

```bash
ANSIBLE_LIBRARY=ansible/lib ansible-playbook playbooks/simple-cleanup.yml
```

### Module Parameters

- `state` - `present` (report only) or `absent` (remove obsolete kernels)
- `verbosity` - `quiet`, `normal`, or `verbose`

### Module Return Values

- `changed` - Whether any kernels were removed
- `msg` - Human readable status message
- `removed_packages` - List of removed package names
- `obsolete_count` - Number of obsolete packages found
- `running_kernel` - Currently running kernel version
- `latest_kernel` - Latest installed kernel version
- `reboot_required` - Whether a reboot is needed

### Check Mode Support

The module fully supports Ansible's `--check` mode to preview changes without making them.

See `playbooks/cleanup-kernels.yml` for a complete example.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Disclaimer

Always backup your system before removing kernel packages. While KernSweep includes safety checks, kernel management is a critical system operation.

