#!/usr/bin/env python3
import hashlib
import os, sys, time
import subprocess, argparse
import shutil, platform
import json


import json
import os
import posixpath
import re
from urllib import request
import logging

import http.client
import os
from urllib.parse import urlparse

from busybar_tools.helpers import (
    fetch_url, print_pretty, file_download, busybar_workdir_get, url_to_dir_name, busybar_api_update, busybar_update_get_index_file_name, busybar_update_url_normalize, busybar_update_parse_index, file_sha256, wait_for_device
)

from busybar_tools.bsb_term import run_session

from busybar_tools.bsb_lite import BSB_Lite

from busybar_tools.config import TCP_TIMEOUT_DEFAULT, DIR_BSB_TMP, DIR_BSB_RECOVERY, UPDATE_MANIFEST_FILE

from busybar_tools.flipper.cli import Cli
from busybar_tools.flipper.storage_socket import FlipperStorage

UNPACKED_DIR_NAME = "unpacked"

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

    wait_for_device(args.device, verbose=args.verbose)

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


def busybar_get_file_by_filetype(source_url, file_type, work_dir, index_parsed):
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

def run_install(args, verbose=False):
    if verbose:
        for arg, value in vars(args).items():
            print(f"\t{arg}: {value}")
    
    args.source_file = None
    if os.path.isfile(args.source):
        args.source_file = os.path.abspath(args.source)
        logging.info(f"Consdering Source as FILE: {args.source}, absolute path: {args.source_file}")
    else:
        args.source_url = busybar_update_url_normalize(args.source)
        logging.info(f"Consdering Source as URL: {args.source}, normalized URL: {args.source_url}")

        # Craft file_type, "(update|bkp)[_signed]_(tar|tgz)"
        file_type = f"{args.update_bundle_type}"
        if args.save_as_recovery == True:
            file_type = "bkp"
        if args.signed:
            file_type += "_signed" 

        work_dir = busybar_workdir_get(url_to_dir_name(args.source_url))

        index_parsed = busybar_get_index_by_url(args.source_url, args.target, work_dir)

        try:
            args.source_file = busybar_get_file_by_filetype(args.source_url, f"{file_type}_tgz", work_dir, index_parsed)
        except Exception as e:
            logging.error(f"Failed to get file by type {file_type}_tgz: {e}")
        # Fallback to _tar if _tgz not found
        if args.source_file is None:
            try:
                args.source_file = busybar_get_file_by_filetype(args.source_url, f"{file_type}_tar", work_dir, index_parsed)
            except Exception as e:
                logging.error(f"Failed to get file by type {file_type}_tar: {e}")
                logging.error("No suitable update file found in index!")
                return 1
            
    if args.source_file:
        print(f"Source file: {args.source_file}")

        work_dir = busybar_workdir_get("local_file")
        unpacked_dir = os.path.join(work_dir, UNPACKED_DIR_NAME)
        # Clean up work dir before update to avoid confusion with old files
        try:
            shutil.rmtree(unpacked_dir, ignore_errors=True)
        except Exception as e:
            logging.error(f"Error cleaning up {unpacked_dir}: {e}")
            return 1
        # sys.exit(0)

        if args.via_storage == True:
            save_as_recovery = False
            invoke_update = True
            if args.save_as_recovery == True:
                logging.warning("Will save the update bundle as recovery bundle on device /bkp! This can be dangerous if the bundle is not correct!")
                save_as_recovery = True
                invoke_update = False
            if args.invoke_update == False:
                invoke_update = False
            
            if invoke_update == False:
                logging.warning("Will NOT invoke update after uploading the bundle on device!")
            return run_update_via_storage(args, work_dir, save_as_recovery=save_as_recovery, invoke_update=invoke_update)
        else:
            return run_update_via_http(args)
    else:
        logging.error("No source file available for update!")
        return 1

def run_update_via_http(args):
    logging.info("Using HTTP transport for update...")
    wait_for_device(args.device, verbose=args.verbose)
    bsb_sysctl_debug_enable(args.device, args.port)
    return busybar_api_update(args.device, args.source_file)


def run_update_via_storage(args, work_dir, save_as_recovery=False, invoke_update=True):
    logging.info("Running update via storage...")

    unpack_dir = os.path.join(work_dir, UNPACKED_DIR_NAME)

    logging.info(f"Unpacking update bundle to {unpack_dir}...")
    shutil.unpack_archive(args.source_file, unpack_dir)
    logging.info(f"Unpacked: {os.listdir(unpack_dir)}")

    dir_dst = DIR_BSB_TMP + "/update"
    unlock_bkp = False
    if save_as_recovery == True:
        logging.warning("Danger! Saving update bundle as recovery bundle on device /bkp!")
        for i in range(3):
            logging.warning(f"You have {3 - i} seconds to Cancel (Ctrl+C)...")
            time.sleep(1)
        dir_dst = DIR_BSB_RECOVERY
        unlock_bkp = True
    
    wait_for_device(args.device, verbose=args.verbose)

    busybar_storage_upload_dir_to_device((args.device, args.port), unpack_dir, dir_dst, unlock_bkp=unlock_bkp)

    assert busybar_storage_verify_dir_on_device((args.device, args.port), unpack_dir, dir_dst), "Verification failed after upload!"

    if invoke_update == True:
        assert bsb_sysctl_debug_enable(args.device, args.port), "Failed to enable debug mode!"
        assert bsb_invoke_update(args.device, args.port, dir_dst), "Failed to invoke update via CLI!"
        
    
def run_update_from_recovery(args):
    logging.info("Running update from recovery...")

    wait_for_device(args.device, verbose=args.verbose)

    assert bsb_sysctl_debug_enable(args.device, args.port), "Failed to enable debug mode!"
    assert bsb_invoke_update(args.device, args.port, DIR_BSB_RECOVERY), "Failed to invoke update from recovery!"

def run_wait_for_device(args):
    wait_for_device(args.device, verbose=args.verbose)

def run_clean(args):
    dir = busybar_workdir_get()
    print(f"Cleaning up {dir}...")

    try:
        shutil.rmtree(dir, ignore_errors=True)
    except Exception as e:
        logging.error(f"Error cleaning up {dir}: {e}")
        return 1

    return 0

