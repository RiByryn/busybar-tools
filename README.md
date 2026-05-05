# BUSY Bar Tools

Command-line (CLI) tools to manage your BUSY Bar device.

- Easy to install firmware to your BUSY Bar by single command.
- Works on Linux and MacOS.
- There are no heavy dependencies.

Available as a Python package on [PyPI](https://pypi.org/project/busybar-tools/). Source code available on [GitHub](https://github.com/lomalkin/busybar-tools).

> [!WARNING]
> These are unofficial tools that can potentially lead to device bricking if used incorrectly. Use them at your own risk.

## Installation and Upgrade

    brew install pipx           # MacOS (Homebrew)
    sudo apt install pipx       # Ubuntu/Debian
    pipx ensurepath             # Optional step to ensure pipx binaries are in PATH
    # If you haven't install `pipx` before, you will NEED to open a new terminal before continuing.

    pipx install busybar-tools

    pipx upgrade busybar-tools  # To upgrade to the latest available version if you have it installed already.

Install in editable mode (for development): `pip install -e .` from the project root directory. It is recommended to use a virtual environment for that.


## Usage

    busybar [-d DEVICE] [-p PORT] [-t {20,21,22}] {install,cli,wait,clean}

Options:
- `-d`, `--device DEVICE`     BUSY Bar Device IP address (USB LAN or Wi-Fi)
- `-p`, `--port PORT`         Device Port (default: 23)
- `-t`, `--target {20,21,22}` Target hardware version. All the production BUSY Bar devices has at least 22 target.

### `busybar install` options:

    busybar install [Branch | TAG | URL | path/to/local_file.tgz]

#### Options only if the Update server used as a Source

These options affect only the process of selecting which bundle should be used, so it doesn't matter if the update is performed from a local file.

- `--unsigned`: Use unsigned bundles. By default, signed bundles are used, but you can use this option to use unsigned bundles if needed. All production BUSY Bar devices must use only signed bundles.
- `--via-http`: Use HTTP API for update instead of storage.py. It's the official way, but can be unstable during development, so storage.py is used by default.
- `--bkp` - get a special recovery bundle with welcome animations from the update server instead of `--update` (default, regular user firmware). The `--bkp` bundle is intended to be used as a recovery bundle, but can also be installed as regular firmware if needed.

#### Options if the Update server or local file used as a Source (Any source)

- `--save-as-recovery`: Save the update bundle as a recovery bundle on the device instead of direct install. This can be **DANGEROUS** if the bundle is not correct, so use it with caution. The `--bkp` bundle will be used automatically in that case instead of `--update`, but you can actually override it back.
- `--no-invoke-update`: Do not invoke update after uploading the bundle on the device. This option is automatically enabled if `--save-as-recovery` is used, but can be used separately as well to just upload the bundle on the device without invoking update with `--via-storage` (default). Does not work if `--via-http` is used, as HTTP API is used only for direct install.

### Examples:

- `busybar install` - Update to the latest firmware from the `dev` branch. Signed version of the bundle will be used by default.
- `busybar install busybar-f22-bkp_signed-dev-26032026-1e061661.tgz` - Update using a local file. The file can be either `.tar` or `.tgz` format.
- `busybar install --unsigned dev` - Update to firmware from the desired branch using unsigned bundle. This can be useful for testing custom builds, but all production devices must use only signed bundles.
- `busybar install --unsigned 0.7.2` - Update to a specific TAG version (e.g., `0.7.2` release).
- `busybar install --unsigned factory` - Update to firmware from the desired (e.g., `factory`) branch.
- `busybar -d 10.0.5.20 install vanyww/642-clock-app-overlay-effect` - Update device with a custom address to the desired branch.
- `busybar install https://update.flipperzero.one/builds/busybar-firmware/0.7.2/` - Update using a direct URL to the folder with build artifacts.
- `busybar -d 10.0.5.20 update` - Specify a custom device IP address.


### CLI terminal

- `busybar cli` - Start a terminal session to the BUSY Bar device. Press `Ctrl+]` to exit the session.
- `busybar -d 10.0.5.20 -p 23 cli` - Start a terminal session to the BUSY Bar device with a custom IP address and Port.

### Other options:

- `busybar wait`: Wait for the device to be available. This can be useful for scripting.
- `busybar install --save-as-recovery 0.7.2` - Write factory bundle to the recovery partition. This is a **DANGEROUS** operation, as it can potentially brick the device. Usage is not recommended for regular users.

---

# Changelog

## Upcoming features plan
- Easy recovery via DFU from any possible broken state
- Factory reset
- ...create an [issue](https://github.com/lomalkin/busybar-tools/issues) for any feature requests or bug reports!
- Support of OS Windows

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

