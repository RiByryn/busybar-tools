#!/usr/bin/env python3
import os, sys, time
import shutil, platform
import subprocess

import posixpath
from urllib import request
import logging

from urllib.parse import urlparse

from busybar_tools.helpers import (
    fetch_url, print_pretty, file_download, busybar_workdir_get, url_to_dir_name, busybar_api_update, busybar_update_get_index_file_name, busybar_update_url_normalize, busybar_update_parse_index, file_sha256, wait_for_device
)

from busybar_tools.bsb_term import run_session

from busybar_tools.bsb_lite import BSB_Lite

from busybar_tools.config import DIR_BSB_TMP_UPDATE, TCP_TIMEOUT_DEFAULT, DIR_BSB_TMP, DIR_BSB_RECOVERY, UPDATE_MANIFEST_FILE

from busybar_tools.flipper.cli import Cli
from busybar_tools.flipper.storage_socket import FlipperStorage

UNPACKED_DIR_NAME = "unpacked"


def wait_for_device_maybe(args):
    """Wait for the device to be reachable, unless --no-wait was passed."""
    if getattr(args, "no_wait", False):
        logging.info("Skipping device reachability check (--no-wait).")
        return
    wait_for_device(args.device, verbose=getattr(args, "verbose", True))

def busybar_storage_upload_dir_to_device(device, dir_src, dir_dst, unlock_bkp=False):
    def flipper_mkdir_p(storage, path: str):
        """Create directory and parents on Flipper (mkdir -p semantics).

        Uses posix-style path operations so it works correctly for the device.
        """
        # Normalize and ensure absolute-like path
        path = posixpath.normpath(path)
        if not path.startswith("/"):
            path = "/" + path

        # Walk components and create missing directories
        parts = path.split("/")
        cur = ""
        for part in parts:
            if part == "":
                cur = "/"
                continue
            if cur == "/":
                cur = "/" + part
            else:
                cur = cur + "/" + part

            try:
                if not storage.exist_dir(cur):
                    logging.info(f"Creating {cur} on device...")
                    storage.mkdir(cur)
            except Exception as e:
                # Re-raise with context so caller can handle/abort
                raise
    try:
        if unlock_bkp:
            with Cli(device) as cli:
                logging.info("Enabling debug mode...")
                cli.send("sysctl debug 1\r")
                logging.info("Unlocking /bkp...")
                cli.send("sysctl storage_bkp_unlock 1\r")

        with FlipperStorage(device) as storage:
            logging.info(f"Uploading {dir_src} to {dir_dst} @ {device[0]}:{device[1]}...")

            # Ensure target dir and parents exist (mkdir -p semantics)
            flipper_mkdir_p(storage, dir_dst)

            for root, dirs, files in os.walk(dir_src):
                # Create subdirectories
                for dir_name in dirs:
                    local_dir = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(local_dir, dir_src)
                    device_dir = f"{dir_dst}/{rel_path.replace(os.sep, '/')}"

                    flipper_mkdir_p(storage, device_dir)

                # Upload files
                for file_name in files:
                    local_file = os.path.join(root, file_name)
                    rel_path = os.path.relpath(local_file, dir_src)
                    device_file = f"{dir_dst}/{rel_path.replace(os.sep, '/')}"

                    # Make sure parent dir exists before sending file
                    parent = posixpath.dirname(device_file)
                    if parent and parent != "":
                        flipper_mkdir_p(storage, parent)

                    size = os.path.getsize(local_file)
                    logging.info(f"Uploading {device_file} ({size} bytes) to device...")
                    storage.send_file(local_file, device_file)

        return True

    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return False
    finally:
        try:
            if unlock_bkp:
                with Cli(device) as cli:
                    logging.info("Locking /bkp...")
                    cli.send("sysctl storage_bkp_unlock 0\r")
                
                    logging.info("Disabling debug mode...")
                    cli.send("sysctl debug 0\r")
        except Exception:
            pass

def busybar_storage_verify_dir_on_device(device, dir_src, dir_dst):
    try:
        with FlipperStorage(device) as storage:
            logging.info(f"Verifying {dir_dst} on device against {dir_src}...")

            # Collect device file info
            device_files = {}
            for root, _, files in storage.walk(dir_dst):
                for file in files:
                    file_path = os.path.join(root, file).replace(os.sep, "/")
                    rel_path = file_path.replace(dir_dst, "").lstrip("/")

                    try:
                        size = storage.size(file_path)
                        device_files[rel_path] = size
                    except Exception:
                        logging.warning(f"Could not get size of {file_path} on device")

            # Compare with local files
            all_match = True
            for root, _, files in os.walk(dir_src):
                for file in files:
                    local_file = os.path.join(root, file)
                    rel_path = os.path.relpath(local_file, dir_src)
                    
                    if rel_path in device_files:
                        device_size = device_files[rel_path]
                        local_size = os.path.getsize(local_file)

                        if local_size == device_size:
                            logging.info(f"✓ {rel_path}: {local_size} bytes")
                        else:
                            logging.error(
                                f"✗ {rel_path}: local={local_size}, device={device_size}"
                            )
                            all_match = False
                    else:
                        logging.error(f"✗ {rel_path}: not found on device")
                        all_match = False

            if all_match:
                logging.info("✓ All files verified successfully!")
                return True
            else:
                logging.error("✗ Some files do not match!")
                return False

    except Exception as e:
        logging.error(f"Verification failed: {e}")
        return False

def bsb_sysctl_debug_enable(device, port):
    logging.info("Try to enable debug mode...")

    try:
        bsb = BSB_Lite((device, port))
        bsb.start()
        res = bsb.sysctl_debug(1)
        print_pretty(res)
        return True
    except Exception as e:
        logging.error(f"Failed to enable debug mode: {e}")
        return False

def bsb_invoke_update(device, port, file_path):
    logging.info("Try to invoke update via API...")

    try:
        bsb = BSB_Lite((device, port))
        bsb.start()
        res = bsb.cmd_oneshot(f"update install {file_path}/{UPDATE_MANIFEST_FILE}", timeout = 3)
        print_pretty(res)
        return True
    except Exception as e:
        logging.error(f"Failed to invoke update: {e}")
        return False

def run_cli_terminal(args):
    logging.info("Running CLI terminal...")

    wait_for_device_maybe(args)

    timeout = TCP_TIMEOUT_DEFAULT

    print(f"Connecting to {args.device}:{args.port} with timeout {timeout}s...")
    print("Press Ctrl+] to exit.")

    run_session(args.device, args.port, tcp_timeout=timeout)

def busybar_get_index_by_url(base_url, target, work_dir):
    index_name = busybar_update_get_index_file_name(target)
    index_url = f"{base_url}{index_name}"

    try:
        index_data = fetch_url(index_url, timeout=10)
        if not index_data:
            raise Exception(f"Failed to fetch index {index_url}")
        else:
            logging.info(f"Fetched index content from {index_url}, length: {len(index_data)} bytes")
    except Exception as e:
        index_data = None
        logging.warning(f"{e}")
        logging.info("Trying to use cached index...")

    index_path = os.path.join(work_dir, index_name)
    if index_data:
        try:
            with open(index_path, 'w') as f:
                f.write(index_data)
            logging.info(f"Index content saved to {index_path}")
        except Exception as e:
            logging.error(f"Error saving index content: {e}")
    else:
        try:
            with open(index_path, 'r') as f:
                index_data = f.read()
            logging.info(f"Loaded index content from cache {index_path}")
        except Exception as e:
            logging.error(f"Error loading index content from cache: {e}")
            return 1

    index_parsed = busybar_update_parse_index(index_data, base_url)
    # print_pretty(index_parsed)
    return index_parsed


def busybar_download_file_by_filetype(source_url, file_type, work_dir, index_parsed):
    logging.info(f"Trying for file_type {file_type}...")

    file_path = None
    for file in index_parsed:
        if file["file_type"] == file_type:
            file_path = os.path.join(work_dir, file['file_name'])
            if file_sha256(file_path) != file["sha256sum"]:
                logging.warning(f"File missing or Hash check failed: {file['file_name']}")

                file_path = file_download(file["file_url"], file['file_name'], work_dir, progress=True)
            
            if file_sha256(file_path) == file["sha256sum"]:
                logging.info(f"Hash check passed: {file['file_name']}: {file['sha256sum']}")
            else:
                logging.error(f"Hash check failed ONCE AGAIN: {file['file_name']}: {file['sha256sum']}")
            break
    if file_path is None:
        logging.error(f"Failed to find file of type {file_type} in index!")
    
    return file_path

def resolve_source(args):
    """Determine the firmware source and download it if needed.

    Priority order (first match wins):
      1. existing local file       -> (source_file, None)
      2. existing local directory  -> (None, source_dir)   # already-unpacked bundle
      3. otherwise treat the string as a URL / tag / branch of the update server,
         build the URL and download the matching bundle -> (source_file, None)

    An explicit http/https URL naturally lands in branch 3, since it is neither a
    local file nor a local dir. Exactly one of the returned values is set.
    Raises RuntimeError if a remote bundle could not be found/downloaded.
    """
    if os.path.isfile(args.source):
        source_file = os.path.abspath(args.source)
        logging.info(f"Considering source as FILE: {args.source} -> {source_file}")
        return source_file, None

    if os.path.isdir(args.source):
        source_dir = os.path.abspath(args.source)
        logging.info(f"Considering source as DIR: {args.source} -> {source_dir}")
        return None, source_dir

    # URL / tag / branch of the update server.
    args.source_url = busybar_update_url_normalize(args.source)
    logging.info(f"Considering source as URL/tag/branch: {args.source} -> {args.source_url}")

    # Craft file_type, "(update|bkp)[_signed]_(tgz|tar)"
    file_type = f"{args.update_bundle_type}"
    if args.signed:
        file_type += "_signed"

    if getattr(args, "save_as_recovery", False) and args.update_bundle_type != "bkp":
        logging.warning(
            f"--save-as-recovery is normally used with --bkp (the bundle type designed for the "
            f"recovery partition); proceeding with '{args.update_bundle_type}' bundle anyway."
        )

    work_dir = busybar_workdir_get(url_to_dir_name(args.source_url))
    index_parsed = busybar_get_index_by_url(args.source_url, args.target, work_dir)

    source_file = None
    try:
        source_file = busybar_download_file_by_filetype(args.source_url, f"{file_type}_tgz", work_dir, index_parsed)
    except Exception as e:
        logging.error(f"Failed to get file by type {file_type}_tgz: {e}")
    # Fallback to _tar if _tgz not found
    if source_file is None:
        try:
            source_file = busybar_download_file_by_filetype(args.source_url, f"{file_type}_tar", work_dir, index_parsed)
        except Exception as e:
            logging.error(f"Failed to get file by type {file_type}_tar: {e}")

    if source_file is None:
        raise RuntimeError(f"No suitable update file ({file_type}_tgz/_tar) found in index for {args.source_url}")

    return source_file, None


def unpack_bundle(source_file):
    """Unpack a bundle archive into a clean work dir; return the unpacked dir path."""
    work_dir = busybar_workdir_get("local_file")
    unpacked_bundle_dir = os.path.join(work_dir, UNPACKED_DIR_NAME)
    # Clean up work dir before unpack to avoid confusion with old files
    shutil.rmtree(unpacked_bundle_dir, ignore_errors=True)
    assert bundle_unpack(source_file, unpacked_bundle_dir) == 0
    return unpacked_bundle_dir


def _place_result(src_path, output):
    """Copy a fetched file/dir to `output` (a dir or a file path); return the final path.

    If `output` is falsy, leave the result in the cache and return src_path as-is.
    """
    if not output:
        return src_path

    output = os.path.abspath(os.path.expanduser(output))

    if os.path.isdir(src_path):
        os.makedirs(output, exist_ok=True)
        shutil.copytree(src_path, output, dirs_exist_ok=True)
        return output

    # src is a file: treat trailing-slash / existing dir as a destination directory.
    if output.endswith(("/", os.sep)) or os.path.isdir(output):
        os.makedirs(output, exist_ok=True)
        dst = os.path.join(output, os.path.basename(src_path))
    else:
        parent = os.path.dirname(output)
        if parent:
            os.makedirs(parent, exist_ok=True)
        dst = output
    shutil.copy2(src_path, dst)
    return dst


def run_install(args, verbose=False):
    if verbose:
        for arg, value in vars(args).items():
            print(f"\t{arg}: {value}")

    source_file, source_dir = resolve_source(args)
    args.source_file = source_file
    args.source_dir = source_dir

    if source_file:
        # HTTP transport installs the archive directly, without a local unpack.
        if args.via_storage == False:
            return run_update_via_http(args)
        source_dir = unpack_bundle(source_file)
        args.source_dir = source_dir

    if source_dir:
        return _install_from_dir(args, source_dir)

    return 0


def _install_from_dir(args, source_dir):
    invoke_update = args.invoke_update
    if args.save_as_recovery == True:
        logging.warning("Saving unpacked bundle as recovery bundle on device /bkp! This can be dangerous if the bundle is not correct!")
        invoke_update = False

    if invoke_update == False:
        logging.warning("Will NOT invoke update after uploading the bundle on device!")

    bsb_update_dst_dir = busybar_storage_upload_auto(args, source_dir, save_as_recovery=args.save_as_recovery, warning_timeout=args.recovery_timeout)

    if invoke_update:
        return run_update_from_storage(args, bsb_update_dst_dir)
    return 0


def run_fetch(args):
    """Fetch a firmware bundle locally without touching the device.

    Reuses resolve_source (+ unpack_bundle) shared with install.
    Without --unpack: download only. With --unpack: download and unpack.
    Result is placed into --output if given, otherwise left in the cache.
    The final path is printed to stdout.
    """
    source_file, source_dir = resolve_source(args)

    if getattr(args, "unpack", False):
        # A directory source is already unpacked; otherwise unpack the bundle file.
        result = unpack_bundle(source_file) if source_file is not None else source_dir
    else:
        # Download-only: prefer the bundle file; a directory source has nothing to fetch.
        result = source_file if source_file is not None else source_dir

    output = getattr(args, "output", None)
    result = _place_result(result, output)
    if output:
        action = "Fetched and unpacked" if getattr(args, "unpack", False) else "Fetched"
        logging.info(f"{action} '{args.source}' to: {result}")
    print(result)
    return 0

def run_update_via_http(args):
    logging.info("Using HTTP transport for update...")
    wait_for_device_maybe(args)
    bsb_sysctl_debug_enable(args.device, args.port)
    return busybar_api_update(args.device, args.source_file)

def run_update_from_storage(args, update_dir):
    logging.info(f"Running update via storage from {update_dir}...")

    wait_for_device_maybe(args)

    assert bsb_sysctl_debug_enable(args.device, args.port), "Failed to enable debug mode!"
    assert bsb_invoke_update(args.device, args.port, update_dir), "Failed to invoke update via CLI!"

    return 0

def run_update_from_recovery(args):
    return run_update_from_storage(args, DIR_BSB_RECOVERY)

def run_update_local(args):
    target = args.device_path
    if target == "recovery":
        return run_update_from_recovery(args)
    if not target:
        target = DIR_BSB_TMP_UPDATE
    return run_update_from_storage(args, target)

def bundle_unpack(source_file, unpack_dir):
    logging.info(f"Unpacking update bundle {source_file} to {unpack_dir}...")
    try:
        shutil.unpack_archive(source_file, unpack_dir)
        logging.info(f"Unpacked: {os.listdir(unpack_dir)}")
        return 0
    except Exception as e:
        logging.error(f"Failed to unpack bundle: {e}")
        return 1

def busybar_storage_upload_auto(args, unpacked_bundle_dir, save_as_recovery=False, warning_timeout=3):
    logging.info("Running update via storage...")

    dir_dst = DIR_BSB_TMP_UPDATE
    unlock_bkp = False
    if save_as_recovery == True:
        logging.warning("Danger! Saving update bundle as recovery bundle on device /bkp!")
        for i in range(warning_timeout):
            logging.warning(f"You have {warning_timeout - i} seconds to Cancel (Ctrl+C)...")
            time.sleep(1)
        dir_dst = DIR_BSB_RECOVERY
        unlock_bkp = True
    
    wait_for_device_maybe(args)

    busybar_storage_upload_dir_to_device((args.device, args.port), unpacked_bundle_dir, dir_dst, unlock_bkp=unlock_bkp)

    assert busybar_storage_verify_dir_on_device((args.device, args.port), unpacked_bundle_dir, dir_dst), "Verification failed after upload!"

    return dir_dst

def run_storage(args):
    wait_for_device_maybe(args)
    # storage.py located in current package.
    # we invoke it as external command and pass all args to it, so it can handle the storage operations.
    # Use sys.executable so the same interpreter (and its installed deps) is used —
    # critical when busybar is installed via pipx into an isolated venv, since plain
    # `python3` would resolve to the system interpreter without our dependencies.
    # `-m` resolves the module via sys.path, so this is independent of the current working directory.
    # print_pretty(args)
    # Map busybar device selection onto storage.py: --device -> --host, --port -> -p (TCP port).
    # These must precede the storage.py sub-command, so prepend them and drop a leading "--".
    device_args = [
        "--host", args.device,
        "-p", str(args.port),
    ]
    storage_args = list(args.storage_args)
    if storage_args and storage_args[0] == "--":
        storage_args = storage_args[1:]
    cmd = [sys.executable, "-m", "busybar_tools.storage"] + device_args + storage_args
    logging.info(f"Invoking command: {' '.join(cmd)}")
    return subprocess.call(cmd)

def run_wait_for_device(args):
    wait_for_device_maybe(args)

def run_clean(args):
    dir = busybar_workdir_get()
    print(f"Cleaning up {dir}...")

    try:
        shutil.rmtree(dir, ignore_errors=True)
    except Exception as e:
        logging.error(f"Error cleaning up {dir}: {e}")
        return 1

    return 0

