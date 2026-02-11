#!/usr/bin/env python3
import hashlib
import os, sys, time
import subprocess, argparse
import shutil, platform
import json


import json
import os
import re
from urllib import request
import logging

import http.client
import os
from urllib.parse import urlparse

from busybar_tools.helpers import fetch_url, print_pretty, file_download, busybar_workdir_get, url_to_dir_name, busybar_api_update, busybar_update_get_index_file_name, busybar_update_url_normalize, busybar_update_parse_index, file_sha256, wait_for_device

from busybar_tools.bsb_term import run_session

from busybar_tools.bsb_lite import BSB_Lite

from busybar_tools.config import TCP_TIMEOUT_DEFAULT, DIR_BSB_TMP, DIR_BSB_RECOVERY, UPDATE_MANIFEST_FILE

from busybar_tools.flipper.cli import Cli
from busybar_tools.flipper.storage_socket import FlipperStorage

def busybar_storage_upload_dir_to_device(device, dir_src, dir_dst, unlock_bkp=False):
    try:
        if unlock_bkp:
            with Cli(device) as cli:
                logging.info("Enabling debug mode...")
                cli.send("sysctl debug 1\r")
                logging.info("Unlocking /bkp...")
                cli.send("sysctl storage_bkp_unlock 1\r")

        with FlipperStorage(device) as storage:
            logging.info(f"Uploading {dir_src} to {dir_dst} @ {device[0]}:{device[1]}...")

            # Ensure target dir exists
            if not storage.exist_dir(dir_dst):
                logging.info(f"Creating {dir_dst} on device...")
                storage.mkdir(dir_dst)

            for root, dirs, files in os.walk(dir_src):
                # Create subdirectories
                for dir_name in dirs:
                    local_dir = os.path.join(root, dir_name)
                    rel_path = os.path.relpath(local_dir, dir_src)
                    device_dir = f"{dir_dst}/{rel_path.replace(os.sep, "/")}"

                    if not storage.exist_dir(device_dir):
                        logging.info(f"Creating {device_dir} on device...")
                        storage.mkdir(device_dir)

                # Upload files
                for file_name in files:
                    local_file = os.path.join(root, file_name)
                    rel_path = os.path.relpath(local_file, dir_src)
                    device_file = f"{dir_dst}/{rel_path.replace(os.sep, "/")}"

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

def bsb_sysctl_debug_enable(args):
    logging.info("Try to enable debug mode...")

    try:
        bsb = BSB_Lite((args.device, args.port))
        bsb.start()
        res = bsb.sysctl_debug(1)
        print_pretty(res)
        return True
    except Exception as e:
        logging.error(f"Failed to enable debug mode: {e}")
        return False

def bsb_invoke_update(args, file_path):
    logging.info("Try to invoke update via API...")

    try:
        bsb = BSB_Lite((args.device, args.port))
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

def busybar_get_index_by_url(base_url, work_dir, args):
    index_name = busybar_update_get_index_file_name(args.target)
    index_url = f"{base_url}{index_name}"

    try:
        index_data = fetch_url(index_url, timeout=10)
        if not index_data:
            raise Exception(f"Failed to fetch index {index_url}")
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

def run_update_via_http(args):
    logging.info("Running update via HTTP...")

    wait_for_device(args.device, verbose=args.verbose)

    base_url = busybar_update_url_normalize(args.branch)
    logging.info(f"URL: {base_url}")

    work_dir = busybar_workdir_get(url_to_dir_name(base_url))
    logging.info(f"Workdir: {work_dir}")

    index_parsed = busybar_get_index_by_url(base_url, work_dir, args)

    file_path = None
    for file in index_parsed:
        if file["file_type"] == "update_tar":
            file_path = os.path.join(work_dir, file['file_name'])
            if file_sha256(file_path) != file["sha256sum"]:
                logging.warning(f"File missing or Hash check failed: {file['file_name']}")

                file_path = file_download(file["file_url"], file['file_name'], work_dir)
            
            if file_sha256(file_path) == file["sha256sum"]:
                logging.info(f"Hash check passed: {file['file_name']}: {file['sha256sum']}")
            else:
                logging.error(f"Hash check failed ONCE AGAIN: {file['file_name']}: {file['sha256sum']}")
            break

    if file_path:
        bsb_sysctl_debug_enable(args)
        return busybar_api_update(args.device, file_path)
    else:
        logging.error("No update file found.")
        return 1

def run_update_via_storage(args):
    logging.info("Running update via HTTP...")

    wait_for_device(args.device, verbose=args.verbose)

    base_url = busybar_update_url_normalize(args.branch)
    logging.info(f"URL: {base_url}")

    work_dir = busybar_workdir_get(url_to_dir_name(base_url))
    logging.info(f"Workdir: {work_dir}")

    index_parsed = busybar_get_index_by_url(base_url, work_dir, args)

    file_path = None
    for file in index_parsed:
        if file["file_type"] == "update_tar":
            file_path = os.path.join(work_dir, file['file_name'])
            if file_sha256(file_path) != file["sha256sum"]:
                logging.warning(f"File missing or Hash check failed: {file['file_name']}")

                file_path = file_download(file["file_url"], file['file_name'], work_dir)
            
            if file_sha256(file_path) == file["sha256sum"]:
                logging.info(f"Hash check passed: {file['file_name']}: {file['sha256sum']}")
            else:
                logging.error(f"Hash check failed ONCE AGAIN: {file['file_name']}: {file['sha256sum']}")
            break

    if file_path:
        unpack_dir = os.path.join(work_dir, "unpacked")
        logging.info(f"Unpacking update bundle to {unpack_dir}...")
        shutil.unpack_archive(file_path, unpack_dir)
        logging.info(f"Unpacked: {os.listdir(unpack_dir)}")


        print_pretty(args)
        dir_dst = DIR_BSB_TMP + "/update"
        unlock_bkp = False
        if args.save_as_recovery_only == True:
            logging.warning("Danger! Saving update bundle as recovery bundle on device /bkp!")
            for i in range(3):
                logging.warning(f"You have {3 - i} seconds to cancel (Ctrl+C)...")
                time.sleep(1)
            dir_dst = DIR_BSB_RECOVERY
            unlock_bkp = True
        busybar_storage_upload_dir_to_device((args.device, args.port), unpack_dir, dir_dst, unlock_bkp=unlock_bkp)

        assert busybar_storage_verify_dir_on_device((args.device, args.port), unpack_dir, dir_dst), "Verification failed after upload!"

        if args.save_as_recovery_only == False:
            assert bsb_sysctl_debug_enable(args), "Failed to enable debug mode!"
            assert bsb_invoke_update(args, dir_dst), "Failed to invoke update via CLI!"
            
    else:
        logging.error("No update file found.")
        return 1
    
def run_update_from_recovery(args):
    logging.info("Running update from recovery...")

    wait_for_device(args.device, verbose=args.verbose)

    assert bsb_invoke_update(args, DIR_BSB_RECOVERY), "Failed to invoke update from recovery!"

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

