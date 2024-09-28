#!/bin/bash

# Determine the script's directory
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

# Copy all .rule files to /etc/udev/rules.d/
echo "Copying .rules files to /etc/udev/rules.d/"
cp "$SCRIPT_DIR"/*.rules /etc/udev/rules.d/

# Trigger udev to reload and apply rules
echo "Triggering udev..."
udevadm control --reload-rules && udevadm trigger

# Use $SUDO_USER to get the username of the user who invoked sudo
if [ -z "$SUDO_USER" ]; then
    echo "Script is not run with sudo, using $USER instead."
    TARGET_USER=$USER
else
    TARGET_USER=$SUDO_USER
fi

# Add the invoking user to the plugdev group if not already a member
if ! groups $TARGET_USER | grep -q '\bplugdev\b'; then
    echo "Adding $TARGET_USER to plugdev group..."
    usermod -aG plugdev $TARGET_USER
else
    echo "$TARGET_USER is already a member of plugdev group."
fi
