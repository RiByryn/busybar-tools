import os
import sys
import argparse
import logging
from importlib.metadata import version

from busybar_tools import (
    run_clean,
    run_cli_terminal,
    run_update_local,
    run_wait_for_device,
    run_auto_install,
    run_install,
    run_fetch,
    run_write_recovery,
    run_storage,
)

from busybar_tools.helpers import (
    setup_logging,
)

from busybar_tools.config import (
    DEVICE_IP,
    DEVICE_IP_REF,
    DEVICE_PORT,
    U5_TARGET_HW,
    U5_TARGET_HW_OPTIONS,
    UPDATE_DEFAULT_BRANCH
)

__version__ = "unknown"
try:
    __version__ = version("busybar-tools")
except Exception:
    __version__ = "unknown"


TOP_EPILOG = """\
examples:
  busybar auto-install                     recommended: autodetect & install latest dev firmware
  busybar auto-install 0.10.2              autodetect target/signing, install a specific tag
  busybar install -t 21 --unsigned 0.10.2  low-level: install a specific tag for hw target 21
  busybar write-recovery 0.10.2            store a bkp bundle into the recovery partition
  busybar fetch 0.10.2 -o ~/fw/            download a bundle into a local directory
  busybar install-onboard recovery         install firmware already on the device's recovery
  busybar cli -d 10.0.5.20                 open a CLI terminal session to the device
  busybar storage -d 10.0.4.20 -- list /ext

Most users want `busybar auto-install`. The other commands are explicit/low-level.
Options that affect a command are placed on that command (e.g. `busybar install -t 21 0.10.2`).
Use `busybar <command> --help` for command-specific options.
"""

# `source` accepts (resolved in this priority order):
SOURCE_HELP = (
    "Firmware source (required). Accepted forms (priority order): "
    "explicit URL (http/https) | local bundle file | local directory | "
    "update-server tag/branch."
)


def _make_device_opts():
    """Parent parser: which device to talk to. Shared by device-facing commands."""
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("device")
    g.add_argument("-d", "--device", help=f"Device IP (or 'r'/'ref' for the reference device), default: {DEVICE_IP}", type=str, default=DEVICE_IP)
    g.add_argument("-p", "--port", help=f"Device port, default: {DEVICE_PORT}", type=int, default=DEVICE_PORT)
    return p


def _make_no_wait_opts():
    """Parent parser: opt out of the device reachability (ping) check.

    Attached to device-facing commands except `wait` (whose whole purpose is to wait).
    """
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--no-wait", dest="no_wait", action="store_true", help="Skip the device reachability (ping) check before the operation")
    return p


def _make_firmware_opts():
    """Parent parser: which firmware to take. Shared by install and fetch."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("source", help=SOURCE_HELP, type=str)

    g = p.add_argument_group("firmware selection (update server only)")
    g.add_argument("-t", "--target", help=f"Target hardware version, default: {U5_TARGET_HW}", type=int, default=U5_TARGET_HW, choices=U5_TARGET_HW_OPTIONS)

    # Bundle type: update (default) vs bkp. Canonical build-server artifact names.
    bundle_type = g.add_mutually_exclusive_group()
    bundle_type.add_argument("--update", dest="update_bundle_type", action="store_const", const="update", help="Regular update bundle (default)")
    bundle_type.add_argument("--bkp", dest="update_bundle_type", action="store_const", const="bkp", help="Recovery (bkp) bundle instead of update")

    # Signature: signed (default) vs unsigned.
    sign = g.add_mutually_exclusive_group()
    sign.add_argument("--signed", dest="signed", action="store_true", help="Use signed firmware (default)")
    sign.add_argument("--unsigned", dest="signed", action="store_false", help="Use unsigned firmware")

    p.set_defaults(signed=True, update_bundle_type="update")
    return p


def busybar_main():
    logging.debug(f"cwd: {os.getcwd()}")

    device_opts = _make_device_opts()
    firmware_opts = _make_firmware_opts()
    no_wait_opts = _make_no_wait_opts()

    parser = argparse.ArgumentParser(
        prog="busybar",
        description="Firmware installer and tooling for BUSY Bar devices.",
        epilog=TOP_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"busybar-tools {__version__}")

    subparsers = parser.add_subparsers(
        dest="command", help="Commands to run", required=False
    )

    # auto-install -----------------------------------------------------------
    p_auto = subparsers.add_parser(
        "auto-install",
        parents=[device_opts],
        help="Automatic install for regular users (autodetects target & signing)",
        description="Read the device info, autodetect the hardware target and whether signed "
                    "firmware is required, then fetch and install the matching update bundle and "
                    "report the version change. The source must be an update-server tag/branch or URL.",
    )
    p_auto.add_argument("source", help=f"Update-server tag/branch or URL (default: {UPDATE_DEFAULT_BRANCH})", type=str, default=UPDATE_DEFAULT_BRANCH, nargs="?")
    p_auto.set_defaults(func=run_auto_install)

    # install ----------------------------------------------------------------
    p_install = subparsers.add_parser(
        "install",
        parents=[firmware_opts, device_opts, no_wait_opts],
        help="Install firmware on the device",
        description="Resolve a firmware source, deliver it to the device and install it.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Transport: storage (default) vs http.
    transport_group = p_install.add_argument_group("delivery / transport")
    transport_mx = transport_group.add_mutually_exclusive_group()
    transport_mx.add_argument("--via-storage", dest="via_storage", action="store_true", help="Deliver via storage.py protocol (default)")
    transport_mx.add_argument("--via-http", dest="via_storage", action="store_false", help="Deliver via HTTP API (direct install only)")

    p_install.add_argument("--no-invoke-update", dest="invoke_update", action="store_false", help="Upload the bundle to the staging dir but do not invoke installation (--via-storage only)")

    p_install.set_defaults(func=run_install, via_storage=True)

    # write-recovery ---------------------------------------------------------
    p_write_recovery = subparsers.add_parser(
        "write-recovery",
        parents=[firmware_opts, device_opts, no_wait_opts],
        help="Write a firmware bundle into the device recovery partition (without installing)",
        description="Resolve a firmware source and store it into the recovery partition (/bkp), "
                    "WITHOUT installing it. Defaults to the --bkp bundle type (purpose-built for "
                    "recovery). DANGER: an incorrect bundle here can brick the device.",
    )
    p_write_recovery.add_argument("--confirm-timeout", dest="recovery_timeout", metavar="SECONDS", type=int, default=3, help="Countdown (seconds) before overwriting the recovery partition")
    # The recovery partition expects a bkp-type bundle, so default to --bkp here.
    p_write_recovery.set_defaults(func=run_write_recovery, update_bundle_type="bkp")

    # fetch ------------------------------------------------------------------
    p_fetch = subparsers.add_parser(
        "fetch",
        parents=[firmware_opts],
        help="Download (and optionally unpack) a firmware bundle locally",
        description="Fetch a firmware bundle without touching the device.",
    )
    p_fetch.add_argument("--unpack", dest="unpack", action="store_true", help="Also unpack the downloaded bundle")
    p_fetch.add_argument("-o", "--output", dest="output", type=str, default=None, help="Destination directory or file path; if omitted, the package cache is used")
    p_fetch.set_defaults(func=run_fetch)

    # install-onboard --------------------------------------------------------
    p_onboard = subparsers.add_parser(
        "install-onboard",
        parents=[device_opts, no_wait_opts],
        help="Install firmware already staged on the device",
        description="Invoke installation from a bundle already present on the device storage.",
    )
    p_onboard.add_argument("device_path", help="Path on the device to install from, or the literal 'recovery' for the recovery partition (default: the staged update dir)", type=str, default="", nargs="?")
    p_onboard.set_defaults(func=run_update_local)

    # cli --------------------------------------------------------------------
    p_run_cli = subparsers.add_parser(
        "cli", parents=[device_opts, no_wait_opts], help="CLI terminal session to the device"
    )
    p_run_cli.set_defaults(func=run_cli_terminal)

    # wait -------------------------------------------------------------------
    p_run_wait = subparsers.add_parser(
        "wait", parents=[device_opts], help="Wait for the device to be reachable via ping, nothing else"
    )
    p_run_wait.set_defaults(func=run_wait_for_device)

    # clean ------------------------------------------------------------------
    p_clean = subparsers.add_parser(
        "clean", help="Clean the package's tmp/cache directory"
    )
    p_clean.set_defaults(func=run_clean)

    # storage ----------------------------------------------------------------
    p_storage = subparsers.add_parser(
        "storage", parents=[device_opts, no_wait_opts], help="Run the embedded storage.py utility on the device"
    )
    p_storage.add_argument("storage_args", nargs=argparse.REMAINDER, help="Sub-command and arguments passed to storage.py (e.g. -- list /ext)")
    p_storage.set_defaults(func=run_storage)

    args = parser.parse_args()

    if hasattr(args, "device") and args.device.lower() in ["r", "ref"]:
        args.device = DEVICE_IP_REF

    # --via-http is a direct-install transport: it cannot stage without installing.
    if args.command == "install" and not args.via_storage and not args.invoke_update:
        p_install.error("--no-invoke-update requires --via-storage (not available with --via-http)")

    args.verbose = True

    if args.command is not None:
        return args.func(args)
    else:
        parser.print_help()


def main():
    setup_logging()

    if sys.platform == "win32":
        from busybar_tools.bsb_term import _enable_windows_vt_mode
        _enable_windows_vt_mode()

    try:
        ret = busybar_main()
        print("RET: ", ret)
        if ret and ret != 0:
            print("Run: Exiting with error code", ret, file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        print("Run: Exited", file=sys.stderr)
        sys.exit(2)
    # except subprocess.CalledProcessError as e:
    #     sys.exit(e.returncode)
    except Exception as e:
        print(f"Run: Error: {e}", file=sys.stderr)
        sys.exit(3)


# if __name__ == "__main__":
#     main()
