#!/usr/bin/python

import argparse
import os
import sqlite3
from datetime import datetime, timedelta
import time
from shutil import copyfile
from sqlite3 import Error
import sys
import tty
import termios
import subprocess
from pytz import timezone
import tzlocal
local_tz = tzlocal.get_localzone()


def create_connection(db_file):
    """
    create a database connection to the SQLite database specified by the db_file
    :param db_file: database file
    :return: Connection object or None
    """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)

    return conn


def get_all_memos(conn):
    """
    Query wanted rows in the table ZCLOUDRECORDING
    :param conn: the Connection object
    :return: rows
    """
    cur = conn.cursor()
    cur.execute("SELECT ZDATE, ZDURATION, ZCUSTOMLABEL, ZPATH FROM ZCLOUDRECORDING ORDER BY ZDATE")

    return cur.fetchall()


def main():
    # Define possible default paths
    _possible_db_paths = [
        os.path.expanduser("~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/CloudRecordings.db"),
        os.path.expanduser("~/Library/Containers/com.apple.VoiceMemos/Data/Library/Application Support/com.apple.voicememos/Recordings/CloudRecordings.db"),
        os.path.expanduser("~/Library/Application Support/com.apple.voicememos/Recordings/CloudRecordings.db")
    ]

    _db_path_default = next((p for p in _possible_db_paths if os.path.exists(p)), None)
    _export_path_default = os.path.join(os.path.expanduser("~"), "Voice Memos Export")

    # Setting up arguments and --help
    parser = argparse.ArgumentParser(description='Export audio files from macOS Voice Memo App ' +
                                                 'with right filename and date created.')
    parser.add_argument("-d", "--db_path", type=str,
                        help="define path to database of Voice Memos.app",
                        default=_db_path_default)
    parser.add_argument("-e", "--export_path", type=str,
                        help="define path to folder for exportation",
                        default=_export_path_default)
    parser.add_argument("-a", "--all", action="store_true",
                        help="export everything at once instead of step by step")
    parser.add_argument("--date_in_name", action="store_true",
                        help="include date in file name")
    parser.add_argument("--date_in_name_format", type=str,
                        help="define the format of the date in file name (if --date_in_name active)",
                        default="%Y-%m-%d-%H-%M-%S_")
    parser.add_argument("--no_finder", action="store_true",
                        help="prevent to open finder window to show exported memos")
    args = parser.parse_args()

    # Detect non-TTY environments and fallback to --all mode
    if not sys.stdin.isatty() and not args.all:
        print("⚠️ Non-interactive environment detected, auto-switching to --all mode")
        args.all = True

    # Define name and width of columns
    _cols = [{"n": "Date",
             "w": 19},
            {"n": "Duration",
             "w": 11},
            {"n": "Old Path",
             "w": 32},
            {"n": "New Path",
             "w": 60},
            {"n": "Status",
             "w": 12}]

    # offset between datetime starts to count (1.1.1970) and Apple starts to count (1.1.2001)
    _dt_offset = 978307200.825232

    def getWidth(name):
        """
        get width of column called by name
        :param name: name of column
        :return: width
        """
        for c in _cols:
            if c["n"] == name:
                return c["w"]
        return False

    def helper_str(seperator):
        """
        create a helper string for printing table row
        Example: helper_str(" | ").format(...)
        :param seperator: string to symbol column boundary
        :return: helper string like: "{0:10} | {1:50}"
        """
        return seperator.join(["{" + str(i) + ":" + str(c["w"]) + "}" for i, c in enumerate(_cols)])

    def body_row(content_list):
        """
        create a string for a table body row
        :param content_list: list of cells in this row
        :return: table body row string
        """
        return "│ " + helper_str(" │ ").format(*content_list) + " │"

    # Check permission
    if not os.access(args.db_path, os.R_OK):
        print("No permission to read database file. ({})".format(args.db_path))
        exit()

    # create a database connection and load rows
    conn = create_connection(args.db_path)
    if not conn:
        exit()
    with conn:
        rows = get_all_memos(conn)
    if not rows:
        exit()

    # create export folder if it doesn't exist
    args.export_path = os.path.expanduser(args.export_path)
    os.makedirs(args.export_path, exist_ok=True)

    # Print intro and table header
    print()
    if not args.all:
        print("Press ENTER to export the memo shown in the current row or ESC to go to next memo.")
        print("Do not press other keys.")
        print()
    print("┌─" + helper_str("─┬─").format(*["─" * c["w"] for c in _cols]) + "─┐")
    print("│ " + helper_str(" │ ").format(*[c["n"] for c in _cols]) + " │")
    print("├─" + helper_str("─┼─").format(*["─" * c["w"] for c in _cols]) + "─┤")

    # iterate over memos found in database
    for row in rows:

        # get information from database and modify them for exportation
        date_utc = datetime.fromtimestamp(row[0] + _dt_offset, tz=timezone("UTC"))
        date = date_utc.astimezone(local_tz)
        date_str = date.strftime("%d.%m.%Y %H:%M:%S")
        duration_str = str(timedelta(seconds=row[1]))
        duration_str = duration_str[:duration_str.rfind(".") + 3] if "." in duration_str else duration_str + ".00"
        duration_str = "0" + duration_str if len(duration_str) == 10 else duration_str
        label = row[2].encode('ascii', 'ignore').decode("ascii").replace("/", "_")
        # If label looks like a timestamp (e.g., auto-generated by Voice Memos), discard it to avoid duplication
        if "T" in label and "Z" in label:
            label = "VoiceMemo"
        recordings_dir = os.path.dirname(args.db_path)
        path_old = os.path.join(recordings_dir, row[3]) if row[3] else ""
        if path_old:
            if args.date_in_name:
                local_time_str = date.strftime(args.date_in_name_format)
                path_new = local_time_str + "_" + label + os.path.splitext(path_old)[1]
            else:
                path_new = label + os.path.splitext(path_old)[1]
            path_new = os.path.join(args.export_path, path_new)
        else:
            path_new = ""
        if len(path_old) < getWidth("Old Path") - 3:
            path_old_short = path_old
        else:
            path_old_short = "..." + path_old[-getWidth("Old Path") + 3:]
        if len(path_new) < getWidth("New Path") - 3:
            path_new_short = path_new
        else:
            path_new_short = "..." + path_new[-getWidth("New Path") + 3:]

        # print body row and wait for keys (if needed)
        if not path_old:
            print(body_row((date_str, duration_str, path_old_short, path_new_short, "No File")))
        else:
            if args.all:
                key = 10
            else:
                key = 0
                print(body_row((date_str, duration_str, path_old_short, path_new_short, "Export?")), end="\r")
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                new = termios.tcgetattr(fd)
                new[3] = new[3] & ~termios.ECHO
                termios.tcsetattr(fd, termios.TCSADRAIN, new)
                tty.setcbreak(sys.stdin)
                while key not in (10, 27):
                    try:
                        key = ord(sys.stdin.read(1))
                        # print("Key: {}".format(key))
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old)

            # copy file and modify file times if this memo should be exported
            if key == 10:
                copyfile(path_old, path_new)
                mod_time = time.mktime(date.timetuple())
                os.utime(path_new, (mod_time, mod_time))
                print(body_row((date_str, duration_str, path_old_short, path_new_short, "Exported!")))

            # skip this memo if desired
            elif key == 27:
                print(body_row((date_str, duration_str, path_old_short, path_new_short, "Not Exported")))

    # print bottom table border and closing statement
    print("└─" + helper_str("─┴─").format(*["─" * c["w"] for c in _cols]) + "─┘")
    print()
    print("Done. Memos exported to: {}".format(args.export_path))
    print()

    # open finder if desired
    if not args.no_finder:
        subprocess.Popen(["open", args.export_path])


if __name__ == '__main__':
    main()
