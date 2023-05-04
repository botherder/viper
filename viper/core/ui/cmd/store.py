# This file is part of Viper - https://github.com/viper-framework/viper
# See the file 'LICENSE' for copying permission.

import fnmatch
import os
from typing import Any

from viper.common.abstracts import Command
from viper.common.autorun import autorun_module
from viper.common.objects import File
from viper.core.config import cfg
from viper.core.database import Database
from viper.core.sessions import sessions
from viper.core.storage import get_sample_path, store_sample
from viper.core.ui.cmd.open import Open


class Store(Command):
    """
    This command stores the open file in the local repository and tries
    to store details in the database.
    """

    cmd = "store"
    description = "Store the open file to the local repository"
    fs_path_completion = True

    def __init__(self):
        super(Store, self).__init__()

        self.parser.add_argument(
            "-d", "--delete", action="store_true", help="Delete the original file"
        )
        self.parser.add_argument(
            "-f", "--folder", type=str, nargs="+", help="Specify a folder to import"
        )
        self.parser.add_argument(
            "-s", "--file-size", type=int, help="Specify a maximum file size"
        )
        self.parser.add_argument(
            "-y", "--file-type", type=str, help="Specify a file type pattern"
        )
        self.parser.add_argument(
            "-n", "--file-name", type=str, help="Specify a file name pattern"
        )
        self.parser.add_argument(
            "-t",
            "--tags",
            type=str,
            nargs="+",
            help="Specify a list of comma-separated tags",
        )

    def run(self, *args: Any):
        try:
            args = self.parser.parse_args(args)
        except SystemExit:
            return

        if args.folder is not None:
            # Allows to have spaces in the path.
            args.folder = " ".join(args.folder)

        if args.tags is not None:
            # Remove the spaces in the list of tags
            args.tags = "".join(args.tags)

        def add_file(obj, tags=None):
            if get_sample_path(obj.sha256):
                self.log(
                    "warning",
                    f'Skip, file "{obj.name}" appears to be already stored',
                )
                return False

            # Try to store file object into database.
            status = Database().add(obj=obj, tags=tags)
            if status:
                # If succeeds, store also in the local repository.
                # If something fails in the database (for example unicode strings)
                # we don't want to have the binary lying in the repository with no
                # associated database record.
                new_path = store_sample(obj)
                self.log(
                    "success",
                    f'Stored file "{obj.name}" to {new_path}',
                )

            else:
                return False

            # Delete the file if requested to do so.
            if args.delete:
                try:
                    os.unlink(obj.path)
                except Exception as e:
                    self.log("warning", f"Failed deleting file: {e}")

            return True

        # If the user specified the --folder flag, we walk recursively and try
        # to add all contained files to the local repository.
        # This is note going to open a new session.
        # TODO: perhaps disable or make recursion optional?
        if args.folder is not None:
            # Check if the specified folder is valid.
            if os.path.isdir(args.folder):
                # Walk through the folder and subfolders.
                for dir_name, dir_names, file_names in walk(args.folder):
                    # Add each collected file.
                    for file_name in file_names:
                        file_path = os.path.join(dir_name, file_name)

                        if not os.path.exists(file_path):
                            continue
                        # Check if file is not zero.
                        if not os.path.getsize(file_path) > 0:
                            continue

                        # Check if the file name matches the provided pattern.
                        if args.file_name:
                            if not fnmatch.fnmatch(file_name, args.file_name):
                                # self.log('warning', "Skip, file \"{0}\" doesn't match the file name pattern".format(file_path))
                                continue

                        # Check if the file type matches the provided pattern.
                        if args.file_type:
                            if args.file_type not in File(file_path).type:
                                # self.log('warning', "Skip, file \"{0}\" doesn't match the file type".format(file_path))
                                continue

                        # Check if file exceeds maximum size limit.
                        if args.file_size:
                            # Obtain file size.
                            if os.path.getsize(file_path) > args.file_size:
                                self.log(
                                    "warning",
                                    f"Skip, file {file_path} is too big",
                                )
                                continue

                        file_obj = File(file_path)

                        # Add file.
                        add_file(file_obj, args.tags)
                        if add_file and cfg.get("autorun").enabled:
                            autorun_module(file_obj.sha256)
                            # Close the open session to keep the session table clean
                            sessions.close()

            else:
                self.log("error", f"You specified an invalid folder: {args.folder}")
        # Otherwise we try to store the currently open file, if there is any.
        else:
            if sessions.is_set():
                if sessions.current.file.size == 0:
                    self.log(
                        "warning",
                        f'Skip, file "{sessions.current.file.name}" appears to be empty',
                    )
                    return False

                # Add file.
                if add_file(sessions.current.file, args.tags):
                    # TODO: review this. Is there a better way?
                    # Open session to the new file.
                    Open().run(*[sessions.current.file.sha256])
                    if cfg.get("autorun").enabled:
                        autorun_module(sessions.current.file.sha256)
            else:
                self.log(
                    "error", "No open session. This command expects a file to be open."
                )
