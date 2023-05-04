# This file is part of Viper - https://github.com/viper-framework/viper
# See the file 'LICENSE' for copying permission.

from typing import Any

from viper.common.abstracts import Command
from viper.core.database import Database
from viper.core.sessions import sessions
from viper.core.storage import get_sample_path


class Parent(Command):
    """
    This command is used to view or edit the parent child relationship between files.
    """

    cmd = "parent"
    description = "Add or remove a parent file"

    def __init__(self):
        super(Parent, self).__init__()

        self.parser.add_argument(
            "-a", "--add", metavar="SHA256", help="Add parent file by sha256"
        )
        self.parser.add_argument(
            "-d", "--delete", action="store_true", help="Delete Parent"
        )
        self.parser.add_argument(
            "-o", "--open", action="store_true", help="Open The Parent"
        )

    def run(self, *args: Any):
        try:
            args = self.parser.parse_args(args)
        except SystemExit:
            return

        # This command requires a session to be open.
        if not sessions.is_set():
            self.log("error", "No open session! This command expects a file to be open")
            self.parser.print_usage()
            return

        # If no arguments are specified, there's not much to do.
        if args.add is None and args.delete is None and args.open is None:
            self.parser.print_usage()
            return

        db = Database()

        if not db.find(key="sha256", value=sessions.current.file.sha256):
            self.log(
                "error",
                "The open file is not stored in the database! If you want to add it use the `store` command",
            )
            return

        if args.add:
            if not db.find(key="sha256", value=args.add):
                self.log("error", "The parent file is not found in the database. ")
                return
            db.add_parent(sessions.current.file.sha256, args.add)
            self.log("info", "Parent added to the currently open file")

            self.log("info", "Refreshing session to update attributes...")
            sessions.new(sessions.current.file.path)

        if args.delete:
            db.delete_parent(sessions.current.file.sha256)
            self.log("info", "Parent removed from the currently open file")

            self.log("info", "Refreshing session to update attributes...")
            sessions.new(sessions.current.file.path)

        if args.open:
            if sessions.current.file.parent:
                sessions.new(get_sample_path(sessions.current.file.parent[-64:]))
            else:
                self.log("info", "No parent set for this sample")
