#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2025
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: dnf_kernsweep
short_description: Detect and remove obsolete Linux kernels
version_added: "0.1.0"
description:
    - Detects obsolete Linux kernel packages on Red Hat / Fedora based systems
      (RHEL, CentOS Stream, Fedora, Rocky Linux, AlmaLinux, ...)
    - Protects running kernel and latest installed kernel
    - Removes old kernel packages to free disk space
    - Provides safety checks to prevent system boot failures
options:
    state:
        description:
            - Whether to remove obsolete kernels or just report them
        type: str
        choices: [ absent, present ]
        default: present
    verbosity:
        description:
            - Output verbosity level
        type: str
        choices: [ quiet, normal, verbose ]
        default: normal
author:
    - KernSweep Contributors
notes:
    - Requires root privileges to remove packages
    - Always protects the running kernel and latest installed kernel
    - Uses dnf remove to remove obsolete kernel packages
    - Only sweeps installonly packages (kernel, kernel-core, kernel-modules,
      kernel-modules-extra). kernel-devel and kernel-headers are excluded
      since they are not stacked/versioned like installonly packages and
      may legitimately trail kernel-core's version without being obsolete.
requirements:
    - python >= 3.7
    - rpm and dnf
'''

EXAMPLES = r'''
# Check what kernels would be removed (check mode)
- name: Check for obsolete kernels
  dnf_kernsweep:
    state: present
  check_mode: yes

# Remove obsolete kernels
- name: Clean up old kernels
  dnf_kernsweep:
    state: absent

# Remove obsolete kernels with verbose output
- name: Clean up old kernels (verbose)
  dnf_kernsweep:
    state: absent
    verbosity: verbose

# Just report status quietly
- name: Check kernel status
  dnf_kernsweep:
    state: present
    verbosity: quiet
'''

RETURN = r'''
changed:
    description: Whether any kernels were removed
    type: bool
    returned: always
    sample: true
failed:
    description: Whether the operation failed
    type: bool
    returned: always
    sample: false
msg:
    description: Human readable message about what happened
    type: str
    returned: always
    sample: "Successfully removed 2 obsolete kernel package(s)"
rc:
    description: Return code from kernsweep (0=success, 1=nothing to do, -1=no root, -2=dnf failed, 2=reboot required)
    type: int
    returned: always
    sample: 0
removed_packages:
    description: List of package names that were removed
    type: list
    elements: str
    returned: when changed
    sample: ["kernel-core-6.8.5-200.fc40.x86_64", "kernel-modules-6.8.5-200.fc40.x86_64"]
obsolete_count:
    description: Number of obsolete packages found
    type: int
    returned: always
    sample: 2
running_kernel:
    description: Currently running kernel version
    type: str
    returned: always
    sample: "6.8.5-200.fc40.x86_64"
latest_kernel:
    description: Latest installed kernel version
    type: str
    returned: always
    sample: "6.8.7-200.fc40.x86_64"
reboot_required:
    description: Whether a reboot is required to use the latest kernel
    type: bool
    returned: always
    sample: true
'''

from ansible.module_utils.basic import AnsibleModule  # type: ignore[import-not-found]

# Import kernsweep - it should be installed as a package
try:
    from kernsweep.detector import get_running_kernel, get_installed_kernels, get_latest_installed_kernel_version
    from kernsweep.analyzer import analyze_kernels
    from kernsweep.remover import remove_packages, check_sudo, RemovalStatus
    KERNSWEEP_AVAILABLE = True
except ImportError as e:
    KERNSWEEP_AVAILABLE = False
    KERNSWEEP_IMPORT_ERROR = str(e)


def run_module():
    """Main Ansible module execution."""
    module_args = dict(
        state=dict(type='str', default='present', choices=['present', 'absent']),
        verbosity=dict(type='str', default='normal', choices=['quiet', 'normal', 'verbose']),
    )

    result = dict(
        changed=False,
        failed=False,
        msg='',
        rc=0,
        removed_packages=[],
        obsolete_count=0,
        running_kernel='',
        latest_kernel='',
        reboot_required=False,
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    # Check if kernsweep is available
    if not KERNSWEEP_AVAILABLE:
        result['msg'] = f"Failed to import kernsweep: {KERNSWEEP_IMPORT_ERROR}"
        result['failed'] = True
        module.fail_json(**result)

    # Check for root privileges when not in check mode and state is absent
    if module.params['state'] == 'absent' and not module.check_mode:
        if not check_sudo():
            result['msg'] = "Root privileges required for package removal"
            result['rc'] = -1
            result['failed'] = True
            module.fail_json(**result)

    try:
        # Step 1: Detect running kernel
        running_kernel_version = get_running_kernel()
        result['running_kernel'] = running_kernel_version

        # Step 2: Detect installed kernels
        installed_kernels = get_installed_kernels()

        # Mark the running kernel
        for kernel in installed_kernels:
            if kernel.version == running_kernel_version:
                kernel.is_running = True
                break

        # Step 3: Determine the latest installed kernel version
        latest_kernel_version = get_latest_installed_kernel_version()
        result['latest_kernel'] = latest_kernel_version

        # Step 4: Analyze kernels
        analysis = analyze_kernels(installed_kernels, latest_kernel_version)

        # Check if reboot is required
        result['reboot_required'] = analysis.running_kernel != analysis.latest_kernel

        # Collect obsolete packages
        all_obsolete = analysis.obsolete_kernels
        result['obsolete_count'] = len(all_obsolete)

        if len(all_obsolete) == 0:
            result['msg'] = "No obsolete kernels found"
            # rc: 2 if reboot required, 1 if nothing to do
            result['rc'] = 2 if result['reboot_required'] else 1
            module.exit_json(**result)

        # Handle state logic
        if module.params['state'] == 'present':
            # Just report what's there
            result['msg'] = f"Found {len(all_obsolete)} obsolete package(s)"
            result['rc'] = 0
            result['removed_packages'] = all_obsolete
            module.exit_json(**result)

        # state == 'absent' - remove packages
        if module.check_mode:
            # Check mode - don't actually remove
            result['changed'] = True
            result['msg'] = f"Would remove {len(all_obsolete)} obsolete package(s)"
            result['rc'] = 0
            result['removed_packages'] = all_obsolete
            module.exit_json(**result)

        # Actually remove packages
        results = remove_packages(all_obsolete, dry_run=False)

        # Count successes and failures
        success_count = sum(1 for _, status in results if status == RemovalStatus.SUCCESS)
        failed_count = len(results) - success_count

        if failed_count > 0:
            result['failed'] = True
            result['rc'] = -2
            result['msg'] = f"Failed to remove {failed_count} package(s), successfully removed {success_count}"
            module.fail_json(**result)

        # Success - determine rc based on reboot requirement
        result['changed'] = True
        result['msg'] = f"Successfully removed {success_count} obsolete package(s)"
        result['removed_packages'] = all_obsolete
        
        # Set rc: 2 if reboot required, 0 otherwise
        if result['reboot_required']:
            result['rc'] = 2
        else:
            result['rc'] = 0

        module.exit_json(**result)

    except Exception as e:
        result['failed'] = True
        result['msg'] = f"Error: {str(e)}"
        module.fail_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()

