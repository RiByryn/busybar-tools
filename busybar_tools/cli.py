import os
import sys
import argparse
import logging
from importlib.metadata import version

from busybar_tools import (
    run_update_via_http,
    run_update_via_storage,
    run_update_from_recovery,
    run_clean,
    run_cli_terminal,
    run_wait_for_device
    
)

from busybar_tools.helpers import (
    setup_logging
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
    
    parser.add_argument("-d", "--device", help="Device IP", type=str, default=DEVICE_IP, action="store")
    parser.add_argument("-p", "--port", help="Device Port", type=int, default=DEVICE_PORT, action="store")
    parser.add_argument("-t", "--target", help="Target hardware", type=int, default=U5_TARGET_HW, action="store", choices=U5_TARGET_HW_OPTIONS)

    parser.parse_known_args()

    subparsers = parser.add_subparsers(
        dest="command", help="Commands to run", required=False
    )

    p_run_update_http = subparsers.add_parser(
        "update", help="Update firmware via HTTP API"
    )
    p_run_update_http.add_argument("branch", help="Branch to update", type=str, default=UPDATE_DEFAULT_BRANCH, nargs='?')
    p_run_update_http.set_defaults(func=run_update_via_http)

    p_run_update_storage = subparsers.add_parser(
        "update-storage", help="Update firmware via storage.py"
    )
    p_run_update_storage.add_argument("branch", help="Branch to update", type=str, default=UPDATE_DEFAULT_BRANCH, nargs='?')
    p_run_update_storage.add_argument("--save-as-recovery-only", help="Save update bundle as recovery bundle on device /bkp (Danger!)", action="store_true", default=False)
    p_run_update_storage.set_defaults(func=run_update_via_storage)

    p_run_update_from_recovery = subparsers.add_parser(
        "update-recovery", help=f"Update firmware via CLI from {DIR_BSB_RECOVERY}"
    )
    p_run_update_from_recovery.set_defaults(func=run_update_from_recovery)

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

    if '--save-as-recovery-only' not in sys.argv and any(arg.startswith('--s') for arg in sys.argv):
        parser.error("Invalid argument abbreviation. Use '--save-as-recovery-only' explicitly.")

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
