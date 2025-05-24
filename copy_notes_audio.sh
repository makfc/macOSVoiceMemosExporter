#!/bin/bash

# Define the destination directory
DEST_DIR=~/Library/CloudStorage/OneDrive-個人/NotesAudioExports

# Create the destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

# Find and copy .m4a files with unique filenames
find ~/Library/Group\ Containers/group.com.apple.notes/Accounts/*/Media -type f -name "*.m4a" | while read -r FILE; do
    # Get the file's modification time
    MOD_TIME=$(stat -f "%Sm" -t "%Y-%m-%d_%H-%M-%S" "$FILE")
    # Generate a unique identifier
    UUID=$(uuidgen)
    # Get the file extension
    EXTENSION="${FILE##*.}"
    # Construct the new filename
    NEW_NAME="${MOD_TIME}_${UUID}.${EXTENSION}"
    # Copy the file
    cp "$FILE" "$DEST_DIR/$NEW_NAME"
done