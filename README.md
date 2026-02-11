# BUSY Bar Tools

Command-line (CLI) tools to manage your BUSY Bar device.

- Easy to install by single command.
- Work on Linux and MacOS.
- There are no heavy dependencies.

Available as a Python package on [PyPI](https://pypi.org/project/busybar-tools/). Source code available on [GitHub](https://github.com/lomalkin/busybar-tools).


## Installation and Upgrade

    brew install pipx           # MacOS (Homebrew)
    sudo apt install pipx       # Ubuntu/Debian
    pipx ensurepath             # Optional step to ensure pipx binaries are in PATH
    # If you haven't install `pipx` before, you will NEED to open a new terminal before continuing.

    pipx install busybar-tools

    pipx upgrade busybar-tools  # To upgrade to the latest available version if you have it installed already.

Install in editable mode (for development): `pip install -e .` from the project root directory.


## Usage

To use the tools, simply run the `busybar` command followed by the desired subcommand:

    busybar [options] <subcommand>

### Available commands and options

- `busybar update [branch or tag or URL]`: Update firmware via HTTP API. Default branch is `dev`.
- `busybar cli`: Start interactive CLI terminal session to BUSY Bar.

Options:
- `-d`, `--device DEVICE`   BUSY Bar Device IP address (USB LAN or Wi-Fi)
- `-p`, `--port PORT`       Device Port
- `-t`, `--target {20,21,22}` Target hardware version

## Examples

### Update firmware

> Subcommands `update` and `update-storage` without additional options has the same effect.

- `busybar update` - Update to the latest firmware from the `dev` branch.
- `busybar update 0.5.0` - Update to a specific TAG version (e.g., `0.5.0` release).
- `busybar update factory` - Update to firmware from the desired (e.g., `factory`) branch.
- `busybar -d 10.0.5.20 update porta/remote-control` - Update device with a custom address to the desired branch.
- `busybar update https://update.flipperzero.one/builds/busybar-firmware/0.5.0/` - Update using a direct URL to the folder with build artifacts.

- `busybar -d 10.0.5.20 update` - Specify a custom device IP address.

- `busybar update-storage` - Update via storage.py. This is a more low-level way to update, which allows to update the device even if it's in a broken state.

### CLI terminal

- `busybar cli` - Start a terminal session to the BUSY Bar device. Press `Ctrl+]` to exit the session.
- `busybar -d 10.0.5.20 -p 23 cli` - Start a terminal session to the BUSY Bar device with a custom IP address and port.

### Other operations

- `busybar wait` - Wait for the device to be available. This can be useful for scripting.
- `busybar update-storage --save-as-recovery-only factory` - Write factory bundle to the recovery partition. This is a **DANGEROUS** operation, as it can potentially brick the device. Usage is not recommended for regular users.
- `busybar update-recovery` - Invoke update from the recovery bundle already located in `/bkp/recovery` on the device.

---

# Changelog

## Upcoming features plan
- Easy recovery via DFU from any possible broken state
- Factory reset
- ...create an [issue](https://github.com/lomalkin/busybar-tools/issues) for any feature requests or bug reports!

## 0.3.1
- Fix a bug with device path creation in `busybar update-storage` command.

## 0.3.0
- Fixed CLI `busybar cli`: now it properly works with auto-complete and history navigation with arrow keys.
- Update via storage.py `busybar update-storage`. There is an DANGEROUS option, allows to rewrite the device recovery bundle by using --save-as-recovery-only key.
- Invocation of update from `/bkp/recovery` via `busybar update-recovery` command.
- Wait for device available before any operations.

## 0.2.0 - latest
- CLI terminal session to device available via `busybar cli` command
- Improved file path handling to more reliablely locate update files

## 0.1.0
- Initial release (basic functionality for firmware update)
