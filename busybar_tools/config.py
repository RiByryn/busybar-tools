
PROJECT_NAME = "busybar_tools"

# Network:
UPDATE_SERVER_BASE = "https://update.flipperzero.one/builds/busybar-firmware/"
UPDATE_DEFAULT_BRANCH = "dev"

FETCH_TIMEOUT_DEFAULT = 60  # seconds
TCP_TIMEOUT_DEFAULT = 5  # seconds

# Device:
DEVICE_IP = "10.0.4.20"
DEVICE_IP_REF = "10.0.5.20" # misc
DEVICE_PORT = 23

# Firmware U5 target:
U5_TARGET_HW = 21   # Default, can be overridden by -t / --target option.
U5_TARGET_HW_OPTIONS = [20, 21, 22]
