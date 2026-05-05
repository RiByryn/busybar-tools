import os
import sys
import argparse
import logging
from importlib.metadata import version

from busybar_tools import (
    run_update_from_storage,
    run_update_from_recovery,
    run_clean,
    run_cli_terminal,
    run_update_local,
    run_wait_for_device,
    run_install,
)

from busybar_tools.helpers import (
    setup_logging,
    print_pretty,
)

from busybar_tools.config import (
    DEVICE_IP,
    DEVICE_IP_REF,
    DEVICE_PORT,
    DIR_BSB_RECOVERY,
    U5_TARGET_HW,
    U5_TARGET_HW_OPTIONS,
    UPDATE_DEFAULT_BRANCH
)

__version__ = "unknown"
try:
    __version__ = version("busybar-tools")
except Exception:
    __version__ = "unknown"


def busybar_main():
    logging.debug(f"cwd: {os.getcwd()}")

    parser = argparse.ArgumentParser(description="Runner")
    parser.add_argument("--version", action="version", version=f"busybar-tools {__version__}")
    # parser.add_argument("-v", "--verbose", help="Verbose", action="store_true")   # Always True currently
    
    parser.add_argument("-d", "--device", help=f"Device IP, default: {DEVICE_IP}", type=str, default=DEVICE_IP, action="store")
    parser.add_argument("-p", "--port", help=f"Device Port, default: {DEVICE_PORT}", type=int, default=DEVICE_PORT, action="store")
    parser.add_argument("-t", "--target", help=f"Target hardware, default: {U5_TARGET_HW}", type=int, default=U5_TARGET_HW, action="store", choices=U5_TARGET_HW_OPTIONS)

    parser.parse_known_args()

    subparsers = parser.add_subparsers(
        dest="command", help="Commands to run", required=False
    )

    p_install = subparsers.add_parser(
        "install", help="Install firmware on device"
    )
    p_install.add_argument("source", help="Branch, tag, URL or local file path", type=str, default=UPDATE_DEFAULT_BRANCH, nargs='?')

    # Update bundle security: signed vs unsigned
    sign_group = p_install.add_mutually_exclusive_group()
    sign_group.add_argument("--signed", dest="signed", action="store_true", help="Use signed firmware (default)")
    sign_group.add_argument("--unsigned", dest="signed", action="store_false", help="Use unsigned firmware")

    # Update bundle type: update vs bkp
    update_bundle_type_group = p_install.add_mutually_exclusive_group()
    update_bundle_type_group.add_argument("--update", dest="update_bundle_type", action="store_const", const="update", help="Regular update bundle (default)")
    update_bundle_type_group.add_argument("--bkp", dest="update_bundle_type", action="store_const", const="bkp", help="Use bkp bundle instead of update (default: update)")
    p_install.set_defaults(update_bundle_type="update")

    # Transport: storage vs http
    transport_group = p_install.add_mutually_exclusive_group()
    transport_group.add_argument("--via-storage", dest="via_storage", action="store_true", help="Use storage.py transport (default)")
    transport_group.add_argument("--via-http", dest="via_storage", action="store_false", help="Use HTTP transport")

    p_install.add_argument("--save-as-recovery", dest="save_as_recovery", action="store_true", help="Save update bundle as recovery bundle on device (danger!)")

    p_install.add_argument("--no-invoke-update", dest="invoke_update", action="store_false", help="Do not invoke update after saving the bundle on device (use with --save-as-recovery)")

    p_install.add_argument("--download-only", dest="download_only", action="store_true", help="Only download the firmware bundle, do not save or install it")
    p_install.add_argument("--unpack-only", dest="unpack_only", action="store_true", help="Only unpack the firmware bundle, do not save or install it (implies --download-only)")

    p_install.add_argument("--recovery-timeout", dest="recovery_timeout", type=int, default=3, help="Time to wait for device to appear in recovery mode (seconds)")

    p_install.set_defaults(func=run_install, signed=True, via_storage=True)

    p_update = subparsers.add_parser(
        "update", help="Run update from BSB local storage"
    )
    p_update.add_argument("source_dir", help="Source directory on the device", type=str, default="", nargs='?')
    p_update.add_argument("--recovery", dest="from_recovery", action="store_true", help="Run update from recovery partition instead of storage")
    p_update.set_defaults(func=run_update_local)

    # p_write_recovery = subparsers.add_parser(
    #     "write-recovery", help="Write firmware bundle to /bkp/recovery on device"
    # )
    # p_write_recovery.add_argument("source", help="Branch, tag, URL or local file path", type=str, default=UPDATE_DEFAULT_BRANCH, nargs='?')
    # sign_group_wr = p_write_recovery.add_mutually_exclusive_group()
    # sign_group_wr.add_argument("--signed", dest="signed", action="store_true", help="Use signed firmware (default)")
    # sign_group_wr.add_argument("--unsigned", dest="signed", action="store_false", help="Use unsigned firmware")
    # p_write_recovery.add_argument("--via-http", dest="via_http", action="store_true", default=False, help="Use HTTP transport instead of storage (default: storage)")
    # p_write_recovery.add_argument("--update-bundle", dest="update_bundle", action="store_true", default=False, help="Use update artifact type instead of bkp")
    # p_write_recovery.set_defaults(func=run_dummy, signed=True)

    p_run_cli = subparsers.add_parser(
        "cli", help="CLI terminal session to device"
    )
    p_run_cli.set_defaults(func=run_cli_terminal)

    p_run_wait = subparsers.add_parser(
        "wait", help="Just wait for device to be reachable via ping, nothing else"
    )
    p_run_wait.set_defaults(func=run_wait_for_device)

    p_clean = subparsers.add_parser(
        "clean", help="Clean package's tmp directory"
    )
    p_clean.set_defaults(func=run_clean)

    # p_flash_u5_dfu = subparsers.add_parser(
    #     "flash-u5-dfu", help="Flash U5 firmware via DFU"
    # )
    # p_flash_u5_dfu.add_argument("-d", "--device_ip", help="Device IP", type=str, default=DEVICE_IP)
    # p_flash_u5_dfu.add_argument("-p", "--device_port", help="Device Port", type=int, default=DEVICE_PORT)
    # p_flash_u5_dfu.set_defaults(func=run_flash_u5_dfu)


    args = parser.parse_args()

    if args.device.lower() in ["r", "ref"]:
        args.device = DEVICE_IP_REF

    args.verbose = True

    if args.command is not None:
        return args.func(args)
    else:
        parser.print_help()


def main():
    setup_logging()

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
