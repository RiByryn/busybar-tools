# BUSY Bar Tools
[![PyPI](https://img.shields.io/pypi/v/busybar-tools.svg)](https://pypi.org/project/busybar-tools/) [![Python Versions](https://img.shields.io/pypi/pyversions/busybar-tools.svg)](https://pypi.org/project/busybar-tools/)

Command-line (CLI) tools to manage your BUSY Bar device.

- Easy to install firmware to your BUSY Bar by single command.
- Works on Linux, MacOS and Windows.
- There are no heavy dependencies.

Available as a Python package on [PyPI](https://pypi.org/project/busybar-tools/). Source code available on [GitHub](https://github.com/lomalkin/busybar-tools).

> [!WARNING]
> These are unofficial tools that can potentially lead to device bricking if used incorrectly. Use them at your own risk.

## Installation and Upgrade

    sudo apt install pipx       # Ubuntu/Debian
    brew install pipx           # MacOS (Homebrew, https://brew.sh/)
    scoop install pipx          # Windows (Scoop, https://scoop.sh/)

    pipx ensurepath             # Optional step to ensure pipx binaries are in PATH, for all OS.
    # If you haven't install `pipx` before, you will NEED to open a new terminal before continuing.

    pipx install busybar-tools

    pipx upgrade busybar-tools  # To upgrade to the latest available version if you have it installed already.

Install in editable mode (for development): `pip install -e .` from the project root directory. It is recommended to use a virtual environment for that.


## Usage

    busybar <command> [options]

    commands:
      auto-install     Automatic install for regular users (autodetects target & signing)
      install          Install firmware on the device (explicit, low-level)
      fetch            Download (and optionally unpack) a firmware bundle locally
      install-onboard  Install firmware already staged on the device
      write-recovery   Write a firmware bundle into the recovery partition (no install)
      cli              CLI terminal session to the device
      wait             Wait for the device to be reachable
      storage          Run the embedded storage.py utility on the device
      clean            Clean the package's tmp/cache directory

**Most users want [`busybar auto-install`](#busybar-auto-install)** — it detects everything and just
works. `install` / `fetch` / `write-recovery` are explicit, low-level tools and **require an explicit
`source`** (no `dev` default).

Options are scoped to the command they affect, so they go **after** the command
(e.g. `busybar install -t 21 0.10.2`, not `busybar -t 21 install`).
Run `busybar <command> --help` for the full list of options for a command.

Device-facing commands (`auto-install`, `install`, `install-onboard`, `cli`, `wait`, `storage`) accept:
- `-d`, `--device DEVICE` — device IP address (USB LAN or Wi-Fi). `r`/`ref` selects the reference device.
- `-p`, `--port PORT` — device TCP port (default: 23).
- `--no-wait` — skip the device reachability (ping) check that normally runs before the operation
  (available on every device-facing command except `wait`).

### `busybar auto-install`

The recommended path for regular users. It connects to the device, reads its info, **autodetects the
hardware target and whether signed firmware is required**, then fetches the matching regular update
bundle and installs it — finally waiting for the reboot and reporting the version change.

    busybar auto-install [--via-storage | --via-http] [--no-wait] [--no-wait-after]
                         [-d DEVICE] [-p PORT] [source]

- `source` — an update-server tag/branch or URL (default: `dev`). Local files/directories are **not**
  accepted here, since the right bundle is chosen automatically from the server for the detected
  target/signing — use `install` for a local source.
- No firmware-selection flags (`-t`, `--signed`, `--bkp`, …): target and signing are autodetected
  from the device. For manual control use `install`.
- `--via-storage` | `--via-http` — delivery transport (default `--via-storage`), same as `install`.
- `--no-wait` — skip the reachability check **before** reading the device.
- `--no-wait-after` — skip waiting for the device to reboot and come back **after** install (by
  default it waits and reports the version change; with this flag it returns right after install).

Examples:
- `busybar auto-install` — install the latest `dev` firmware appropriate for the device.
- `busybar auto-install 0.10.2` — install a specific tag, autodetecting target and signing.
- `busybar auto-install -d 10.0.5.20` — target a device with a custom IP.
- `busybar auto-install --via-http --no-wait-after dev` — install over HTTP, don't wait for the reboot.

### `busybar install`

    busybar install [--update | --bkp] [--signed | --unsigned] [--via-storage | --via-http]
                    [--no-invoke-update] [-t TARGET] [-d DEVICE] [-p PORT] source

For bracketed pairs, **the first option is the default**.

**`source`** (required) — what firmware to install. Accepted forms, resolved in this priority order:
1. an explicit URL (`http://` / `https://`) to a folder with build artifacts;
2. a path to a local bundle file (`.tgz` / `.tar`);
3. a path to a local directory (an already-unpacked bundle);
4. otherwise a tag or branch on the update server.

#### Firmware selection (update server only)

These options choose **which bundle to take from the update server**; they are ignored when
the source is a local file or directory.

- `-t`, `--target TARGET` — target hardware version (default: `22`; all production devices are at least `22`). Any integer is accepted; it must exist on the update server.
- `--update` | `--bkp` — bundle type. `--update` (default) is the regular user firmware; `--bkp`
  is a recovery bundle (with welcome animations). A `--bkp` bundle can also be installed as regular firmware.
- `--signed` | `--unsigned` — bundle signature. Signed is the default; production devices must use only signed bundles.

#### Delivery / transport

- `--via-storage` | `--via-http` — how to deliver the bundle to the device. `--via-storage` (default)
  uploads via the storage.py protocol. `--via-http` uses the HTTP API and performs a **direct install only**.
- `--no-invoke-update` — upload the bundle to the staging directory but do not invoke installation
  (useful for staging; install it later with `busybar install-onboard`). Requires `--via-storage`.

> To write a bundle into the recovery partition (without installing it), use
> [`busybar write-recovery`](#busybar-write-recovery) instead.

#### Examples

- `busybar install` — install the latest signed firmware from the `dev` branch.
- `busybar install --unsigned dev` — install an unsigned bundle from a branch (custom builds; not for production).
- `busybar install --unsigned 0.10.2` — install a specific tag/release.
- `busybar install -t 21 0.10.2` — install for hardware target 21.
- `busybar install ./busybar-f22-update_signed-dev-18062026-74507667.tgz` — install from a local bundle file.
- `busybar install -d 10.0.5.20 vanyww/some-branch-name --unsigned` — install an unsigned bundle from a branch onto a device with a custom IP.
- `busybar install https://update.flipperzero.one/builds/busybar-firmware/0.10.2/` — install from a direct URL.

### `busybar fetch`

Download (and optionally unpack) a firmware bundle **locally, without touching the device**.
Accepts the same `source` and firmware-selection options as `install` (`-t`, `--update/--bkp`, `--signed/--unsigned`).

    busybar fetch [--update | --bkp] [--signed | --unsigned] [-t TARGET]
                  [--unpack] [-o OUTPUT] source

- `--unpack` — also unpack the downloaded bundle.
- `-o`, `--output DEST` — destination directory or file path. If omitted, the result stays in the package
  cache. The final path is printed to stdout.

Examples:
- `busybar fetch dev` — download the bundle into the cache and print its path.
- `busybar fetch 0.10.2 -o ~/fw/` — download the bundle into a directory.
- `busybar fetch dev -o ./my-bundle.tgz` — download the bundle to a specific file name.
- `busybar fetch dev --unpack -o ./out/` — download and unpack into a directory.

### `busybar install-onboard`

Install firmware that is **already staged on the device** (no download/upload), by invoking installation
from an on-device path.

    busybar install-onboard [-d DEVICE] [-p PORT] [device_path]

- `device_path` — path on the device to install from (default: the staged update directory),
  or the literal `recovery` to install from the recovery partition (`/bkp/recovery`).

Examples:
- `busybar install-onboard` — install from the staged update directory.
- `busybar install-onboard recovery` — install from the recovery partition.
- `busybar install-onboard /ext/tmp/update` — install from a specific on-device path.

### `busybar write-recovery`

Acquire a firmware bundle (same `source` and firmware-selection options as `install`) and write it into
the device recovery partition (`/bkp`), **without installing it**. This is the bundle that gets applied on a
factory reset. **DANGER**: an incorrect bundle here can brick the device — not recommended for regular users.

    busybar write-recovery [--bkp | --update] [--signed | --unsigned] [-t TARGET]
                           [-d DEVICE] [-p PORT] [--no-wait] [--confirm-timeout SECONDS] source

- Defaults to the `--bkp` bundle type (purpose-built for the recovery partition). Using `--update` is
  allowed but logs a warning.
- `--confirm-timeout SECONDS` — countdown (default: 3) before overwriting the recovery partition.
- Always uses the storage transport (there is no `--via-http` here).

Examples:
- `busybar write-recovery` — write the signed `bkp` `dev` bundle into recovery.
- `busybar write-recovery 0.10.2` — write a specific tag's bundle into recovery.
- `busybar write-recovery -d 10.0.5.20 factory` — write onto a device with a custom IP.
- `busybar write-recovery ./bundle.tgz` — write a local bundle into recovery.

To install *from* the recovery partition afterwards, use `busybar install-onboard recovery`.

### `busybar cli`

A terminal session to the device, or non-interactive command execution.

    busybar cli [-i] [--timeout SECONDS] [-d DEVICE] [-p PORT] [-- COMMAND ...]

- `busybar cli` — interactive session. Press `Ctrl+]` to exit.
- `busybar cli -d 10.0.5.20 -p 23` — connect to a custom IP address and port.
- `busybar cli -- device_info` — run a single command (everything after `--`) and exit.
- `busybar cli -i -- device_info` — run the command, then **stay** in the interactive session
  (same connection; `-i` only applies to the `--` form, which needs a real terminal).
- `echo device_info | busybar cli` — run commands from stdin (one per line) and exit.
- `busybar cli < script.txt` — run a multi-line command list and exit.
- `--timeout SECONDS` — per-command response wait cap for the non-interactive runs (default: 5).

### `busybar storage`

Work with the device storage via the embedded storage.py tool. Pass the storage sub-command and its
arguments after `--`; the device is selected with the usual `-d`/`-p`.

- `busybar storage -d 10.0.4.20 -- list /ext`
- `busybar storage -- send ./local.bin /ext/local.bin`

Available storage sub-commands: `mkdir`, `format_ext`, `remove`, `read`, `size`, `receive`, `send`, `list`.

### `busybar wait` / `busybar clean`

- `busybar wait` — wait until the device is reachable (useful for scripting).
- `busybar clean` — clean the package's local tmp/cache directory.

---

# Changelog

## Upcoming features plan
- Easy recovery via DFU from any possible broken state
- Factory reset
- ...create an [issue](https://github.com/lomalkin/busybar-tools/issues) for any feature requests or bug reports!

## Unreleased
- New `busybar auto-install` command — the recommended path for regular users: it reads the device
  info, autodetects the hardware target and whether signed firmware is required, fetches the matching
  update bundle, installs it, and reports the version change. Accepts only an update-server tag/branch/URL.
  Supports `--via-storage`/`--via-http`, `--no-wait` (skip the pre-check) and `--no-wait-after`
  (skip waiting for the reboot afterwards).
- `install` / `fetch` / `write-recovery` now **require an explicit `source`** (the `dev` default was
  removed; it now lives in `auto-install`).
- `-t/--target` is no longer restricted to a fixed list — it accepts any integer target supported by
  the update server (default still `22`).
- `busybar cli` can now run commands non-interactively: from arguments (`cli -- device_info`) or from
  stdin (`echo device_info | busybar cli`, one command per line). With `-i`, an argument command runs
  and then drops into the interactive session on the same connection.
- CLI restructure for clarity and consistency (**breaking change**):
    - Options are now scoped to the command they affect and go **after** the command
      (e.g. `busybar install -t 21 dev` instead of `busybar -t 21 install`). `-d`/`-p`/`-t` are no longer global.
    - `--download-only` / `--unpack-only` are removed from `install` and replaced by a dedicated `busybar fetch`
      command (with `--unpack` and `-o/--output` to choose where to place the result).
    - `busybar update` is renamed to `busybar install-onboard` (install firmware already staged on the device);
      the recovery partition is now selected with the `recovery` positional keyword instead of a `--recovery` flag.
    - Writing a bundle into the recovery partition is now a dedicated `busybar write-recovery` command
      (defaults to `--bkp`); the `install --save-as-recovery` / `--install` / `--confirm-timeout` options are removed.
    - `--recovery-timeout` is renamed to `--confirm-timeout`.
    - Invalid combinations now fail with a clear error (e.g. `--via-http` with `--no-invoke-update`).
    - `busybar storage` now selects the device consistently via `-d`/`-p` (pass storage sub-commands after `--`).
    - Added `--no-wait` to skip the device reachability (ping) check on device-facing commands (except `wait`).
    - `write-recovery` logs a warning when used with `--update` instead of `--bkp` (the intended bundle type for recovery).

## 0.7.0
- Windows support (cli, install, storage)

## 0.6.1
- Embedded storage.py tool to manage storage of your device from any terminal with `busybar storage <storage.py args>` command. You can use following commands directly: mkdir, format_ext, remove, read, size, receive, send, list.

## 0.6.0
- Default U5_TARGET_HW is 22, that corresponds to the production BUSY Bar devices. Default firmware bundle is `--update` and `--signed`.

## 0.5.2
- Fix a bug with installing from local dir.

## 0.5.1
- Support of Directory as a Source.
- `--download-only` and `--unpack-only` options for `busybar install` command to just download or unpack the bundle without invoking update. The `--download-only` option is only applicable if the Update server used as a Source, while `--unpack-only` can be used with any source.
- Return back invokation of the update from the recovery bundle already located in `/bkp/recovery` on the device with `--recovery` arg.

## 0.5.0
- `busybar update` and `busybar update-storage` commands now changed to `busybar install` (breaking change):
    - Support for both signed and unsigned bundles. By default, signed bundles are used, but you can use the `--unsigned` option to use unsigned bundles if needed. All production BUSY Bar devices must use only signed bundles.
    - Progress bar when downloading update files from the update server.
    - Using storage.py transport by default, but can be overridden with `--via-http` option.
    - Default bundle is `--update` (regular user firmware), but can be overridden with `--bkp` (recovery bundle, with welcome animations).
    - Added `--save-as-recovery` option to save the update bundle as a recovery bundle. Both `--update` and `--bkp` bundles can be saved as recovery; intentionally only `--bkp` is meant to be used as a recovery bundle.
    - `.tar` and `.tgz` formats are supported for update bundles now, with fallback to `.tar` if `.tgz` is not available in the source.
    - You can use any locally saved update bundles as a source now. It is actually possible to install it as regular firmware or as a recovery bundle with `--save-as-recovery`.

## 0.4.0
- Python 3.8 compatibility. Python 3.8 is the minimum required version now.
- wait_for_device(): now in single line, calc seconds.

## 0.3.2
- Force enable debug mode before invoking update from recovery. Useful if the device does not allow to start update from recovery due to low battery level. This can potentially lead to bricking the device, so use it with caution.

## 0.3.1
- Fix a bug with device path creation in `busybar update-storage` command.

## 0.3.0
- Fixed CLI `busybar cli`: now it properly works with auto-complete and history navigation with arrow keys.
- Update via storage.py `busybar update-storage`. There is a DANGEROUS option that allows rewriting the device recovery bundle by using the `--save-as-recovery-only` key.
- Invocation of update from `/bkp/recovery` via `busybar update-recovery` command.
- Wait for device available before any operations.

## 0.2.0
- CLI terminal session to device available via `busybar cli` command
- Improved file path handling to more reliably locate update files

## 0.1.0
- Initial release (basic functionality for firmware update)

