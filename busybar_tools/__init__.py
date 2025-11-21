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

from busybar_tools.helpers import fetch_url, print_pretty, file_download, busybar_workdir_get, url_to_dir_name, busybar_api_update, busybar_update_get_index_file_name, busybar_update_url_normalize, busybar_update_parse_index, file_sha256

from busybar_tools.bsb_lite import BSB_Lite


def bsb_debug_enable(args):
    logging.info("Try to enable debug mode...")

    bsb = BSB_Lite((args.device, args.port))
    bsb.start()
    res = bsb.sysctl_debug(1)
    print_pretty(res)


def run_update_via_http(args):
    logging.info("Running update via HTTP...")
    print_pretty(args)

    base_url = busybar_update_url_normalize(args.branch)
    logging.info(f"URL: {base_url}")

    work_dir = busybar_workdir_get(url_to_dir_name(base_url))
    logging.info(f"Workdir: {work_dir}")

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
        if args.no_action:
            print("No action specified, not uploading.")
            return 0
        bsb_debug_enable(args)
        return busybar_api_update(args.device, file_path)
    else:
        logging.error("No update file found.")
        return 1

def run_clean(args):
    dir = busybar_workdir_get()
    print(f"Cleaning up {dir}...")

    try:
        shutil.rmtree(dir, ignore_errors=True)
    except Exception as e:
        logging.error(f"Error cleaning up {dir}: {e}")
        return 1

    return 0

