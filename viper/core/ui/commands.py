# This file is part of Viper - https://github.com/botherder/viper
# See the file 'LICENSE' for copying permission.

import os
import getopt
import fnmatch
import tempfile

from viper.common.out import *
from viper.common.objects import File
from viper.common.colors import bold, cyan, white
from viper.common.network import download
from viper.core.session import __session__
from viper.core.plugins import __modules__
from viper.core.database import Database
from viper.core.storage import store_sample, get_sample_path

class Commands(object):

    def __init__(self):
        # Open connection to the database.
        self.db = Database()

        # Map commands to their related functions.
        self.commands = dict(
            help=dict(obj=self.cmd_help, description="Show this help message"),
            open=dict(obj=self.cmd_open, description="Open a file"),
            close=dict(obj=self.cmd_close, description="Close the current session"),
            info=dict(obj=self.cmd_info, description="Show information on the opened file"),
            clear=dict(obj=self.cmd_clear, description="Clear the console"),
            store=dict(obj=self.cmd_store, description="Store the opened file to the local repository"),
            delete=dict(obj=self.cmd_delete, description="Delete the opened file"),
            find=dict(obj=self.cmd_find, description="Find a file"),
            tags=dict(obj=self.cmd_tags, description="Modify tags of the opened file"),
	    latest=dict(obj=self.cmd_latest, description="Show the latest files (default: 5)"),
        )

    ##
    # CLEAR
    #
    # This command simply clears the shell.
    def cmd_clear(self, *args):
        os.system('clear')

    ##
    # HELP
    #
    # This command simply prints the help message.
    # It lists both embedded commands and loaded modules.
    def cmd_help(self, *args):
        print(bold("Commands:"))

        rows = []
        for command_name, command_item in self.commands.items():
            rows.append([command_name, command_item['description']])

        rows = sorted(rows, key=lambda entry: entry[0])

        print(table(['Command', 'Description'], rows))       
        print("")
        print(bold("Modules:"))

        rows = []
        for module_name, module_item in __modules__.items():
            rows.append([module_name, module_item['description']])

        rows = sorted(rows, key=lambda entry: entry[0])

        print(table(['Command', 'Description'], rows))

    ##
    # OPEN
    #
    # This command is used to open a session on a given file.
    # It either can be an external file path, or a SHA256 hash of a file which
    # has been previously imported and stored.
    # While the session is active, every operation and module executed will be
    # run against the file specified.
    def cmd_open(self, *args):
        def usage():
            print("usage: open [-h] [-f] [-u] [-t] <target>")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--file (-f)\tThe target is a file")
            print("\t--url (-u)\tThe target is a URL")
            print("\t--tor (-t)\tDownload the file through Tor")
            print("")
            print("You can also specify a SHA256 hash to a previously stored")
            print("file in order to open a session on it.")
            print("")

        try:
            opts, argv = getopt.getopt(args, 'hfut', ['help', 'file', 'url', 'tor'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_is_file = False
        arg_is_url = False
        arg_use_tor = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-f', '--file'):
                arg_is_file = True
            elif opt in ('-u', '--url'):
                arg_is_url = True
            elif opt in ('-t', '--tor'):
                arg_use_tor = True

        if len(argv) == 0:
            usage()
            return
        else:
            target = argv[0]

        # If it's a file path, open a session on it.
        if arg_is_file:
            target = os.path.expanduser(target)

            if not os.path.exists(target) or not os.path.isfile(target):
                print_error("File not found")
                return

            __session__.set(target)
        # If it's a URL, download it and open a session on the temporary
        # file.
        elif arg_is_url:
            data = download(url=target, tor=arg_use_tor)

            if data:
                tmp = tempfile.NamedTemporaryFile(delete=False)
                tmp.write(data)
                tmp.close()

                __session__.set(tmp.name)
        # Otherwise we assume it's an hash of an previously stored sample.
        else:
            target = argv[0].strip().lower()
            path = get_sample_path(target)
            if path:
                __session__.set(path)

    ##
    # CLOSE
    #
    # This command resets the open session.
    # After that, all handles to the opened file should be closed and the
    # shell should be restored to the default prompt.
    def cmd_close(self, *args):
        __session__.clear()

    ##
    # INFO
    #
    # This command returns information on the open session. It returns details
    # on the file (e.g. hashes) and other information that might available from
    # the database.
    def cmd_info(self, *args):
        if __session__.is_set():
            print(table(
                ['Key', 'Value'],
                [
                    ('Name', __session__.file.name),
                    ('Tags', __session__.file.tags),
                    ('Path', __session__.file.path),
                    ('Size', __session__.file.size),
                    ('Type', __session__.file.type),
                    ('MD5', __session__.file.md5),
                    ('SHA1', __session__.file.sha1),
                    ('SHA256', __session__.file.sha256),
                    ('SHA512', __session__.file.sha512),
                    ('SSdeep', __session__.file.ssdeep),
                    ('CRC32', __session__.file.crc32)
                ]
            ))

    ##
    # STORE
    #
    # This command stores the opened file in the local repository and tries
    # to store details in the database.
    def cmd_store(self, *args):
        def usage():
            print("usage: store [-h] [-d] [-f <path>] [-s <size>] [-y <type>] [-n <name>] [-t]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--delete (-d)\tDelete the original file")
            print("\t--folder (-f)\tSpecify a folder to import")
            print("\t--file-size (-s)\tSpecify a maximum file size")
            print("\t--file-type (-y)\tSpecify a file type pattern")
            print("\t--file-name (-n)\tSpecify a file name pattern")
            print("\t--tags (-t)\tSpecify a list of comma-separated tags")
            print("")

        try:
            opts, argv = getopt.getopt(args, 'hdf:s:y:n:t:', ['help', 'delete', 'folder=', 'file-size=', 'file-type=', 'file-name=', 'tags='])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_delete = False
        arg_folder = False
        arg_file_size = None
        arg_file_type = None
        arg_file_name = None
        arg_tags = None

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-d', '--delete'):
                arg_delete = True
            elif opt in ('-f', '--folder'):
                arg_folder = value
            elif opt in ('-s', '--file-size'):
                arg_file_size = value
            elif opt in ('-y', '--file-type'):
                arg_file_type = value
            elif opt in ('-n', '--file-name'):
                arg_file_name = value
            elif opt in ('-t', '--tags'):
                arg_tags = value

        def add_file(obj, tags=None):
            if get_sample_path(obj.sha256):
                print_warning("Skip, file \"{0}\" appears to be already stored".format(obj.name))
                return False

            # Store file to the local repository.
            new_path = store_sample(obj)
            if new_path:
                # Add file to the database.
                status = self.db.add(obj=obj, tags=tags)
                print_success("Stored file \"{0}\" to {1}".format(obj.name, new_path))

            # Delete the file if requested to do so.
            if arg_delete:
                try:
                    os.unlink(obj.path)
                except Exception as e:
                    print_warning("Failed deleting file: {0}".format(e))

            return True

        # If the user specified the --folder flag, we walk recursively and try
        # to add all contained files to the local repository.
        # This is note going to open a new session.
        # TODO: perhaps disable or make recursion optional?
        if arg_folder:
            # Check if the specified folder is valid.
            if os.path.isdir(arg_folder):
                # Walk through the folder and subfolders.
                for dir_name, dir_names, file_names in os.walk(arg_folder):
                    # Add each collected file.
                    for file_name in file_names:
                        file_path = os.path.join(dir_name, file_name)

                        if not os.path.exists(file_path):
                            continue

                        # Check if the file name matches the provided pattern.
                        if arg_file_name:
                            if not fnmatch.fnmatch(file_name, arg_file_name):
                                #print_warning("Skip, file \"{0}\" doesn't match the file name pattern".format(file_path))
                                continue

                        # Check if the file type matches the provided pattern.
                        if arg_file_type:
                            if arg_file_type not in File(file_path).type:
                                #print_warning("Skip, file \"{0}\" doesn't match the file type".format(file_path))
                                continue

                        # Check if file exceeds maximum size limit.
                        if arg_file_size:
                            # Obtain file size.
                            if os.path.getsize(file_path) > arg_file_size:
                                print_warning("Skip, file \"{0}\" is too big".format(file_path))
                                continue

                        file_obj = File(file_path)

                        # Add file.
                        add_file(file_obj, arg_tags)
            else:
                print_error("You specified an invalid folder: {0}".format(arg_folder))
        # Otherwise we try to store the currently opened file, if there is any.
        else:
            if __session__.is_set():
                # Add file.
                if add_file(__session__.file, arg_tags):
                    # Open session to the new file.
                    self.cmd_open(*[__session__.file.sha256])
            else:
                print_error("No session opened")

    ##
    # DELETE
    #
    # This commands deletes the currenlty opened file (only if it's stored in
    # the local repository) and removes the details from the database
    def cmd_delete(self, *args):
        if __session__.is_set():
            while True:
                choice = raw_input("Are you sure you want to delete this binary? Can't be reverted! [y/n] ")
                if choice == 'y':
                    break
                elif choice == 'n':
                    return

            rows = self.db.find('sha256', __session__.file.sha256)
            if rows:
                malware_id = rows[0].id
                if self.db.delete(malware_id):
                    print_success("File deleted")
                else:
                    print_error("Unable to delete file")

            os.remove(__session__.file.path)
            __session__.clear()
        else:
            print_error("No session opened")

    ##
    # FIND
    #
    # This command is used to search for files in the database.
    def cmd_find(self, *args):
        def usage():
            print("usage: find [-h] [-t] <name|md5|sha256|tag> <value>")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--tags (-t)\tList tags")
            print("")

        try:
            opts, argv = getopt.getopt(args, 'ht', ['help', 'tags'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_list_tags = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-t', '--tags'):
                arg_list_tags = True

        # One of the most useful search terms is by tag. With the --tags
        # argument we first retrieve a list of existing tags and the count
        # of files associated with each of them.
        if arg_list_tags:
            # Retrieve list of tags.
            tags = self.db.list_tags()

            if tags:
                rows = []
                # For each tag, retrieve the count of files associated with it.
                for tag in tags:
                    count = len(self.db.find('tag', tag.tag))
                    rows.append([tag.tag, count])

                # Generate the table with the results.
                header = ['Tag', '# Entries']
                print(table(header=header, rows=rows))
            else:
                print("No tags available")

            return

        # At this point, if there are no search terms specified, return.
        if len(args) == 0:
            usage()
            return

        # The first argument is the search term (or "key").
        key = args[0]
        try:
            # The second argument is the search value.
            value = args[1]
        except IndexError:
            # If the user didn't specify any value, just set it to None.
            # Mostly pointless for now, but might have some useful cases
            # in the future.
            value = None

        # Search all the files matching the given parameters.
        items = self.db.find(key, value)
        if not items:
            return

        # Populate the list of search results.
        rows = []
        for item in items:
            rows.append([item.name, item.type, item.sha256])

        # Generate a table with the results.
        print(table(['Name', 'Type',  'SHA256'], rows))

    ##
    # TAGS
    #
    # This command is used to modify the tags of the opened file.
    def cmd_tags(self, *args):
        def usage():
            print("usage: tags [-h] [-a=tags] [-d=tag]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--add (-a)\tAdd tags to the opened file (comma separated)")
            print("\t--delete (-d)\tDelete a tag from the opened file")
            print("")

        try:
            opts, argv = getopt.getopt(args, 'ha:d:', ['help', 'add=', 'delete='])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_add = None
        arg_delete = None

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-a', '--add'):
                arg_add = value
            elif opt in ('-d', '--delete'):
                arg_delete = value

        # This command requires a session to be opened.
        if not __session__.is_set():
            print_error("No session opened")
            return

        # If no arguments are specified, there's not much to do.
        # However, it could make sense to also retrieve a list of existing
        # tags from this command, and not just from the "find" command alone.
        if not arg_add and not arg_delete:
            print_error("You need to specify an option, either add or delete [-a=tags] [-d=tag]")
            return

        if arg_add:
            # Add specified tags to the database's entry belonging to
            # the opened file.
            db = Database()
            db.add_tags(__session__.file.sha256, arg_add)
            print_info("Tags added to the currently opened file")

            # We refresh the opened session to update the attributes.
            # Namely, the list of tags returned by the "info" command
            # needs to be re-generated, or it wouldn't show the new tags
            # until the existing session is closed a new one is opened.
            print_info("Refreshing session to update attributes...")
            __session__.set(__session__.file.path)

        if arg_delete:
            # TODO
            pass

    ##
    # LATEST
    #
    # This command is used to display the latest files in the database.
    def cmd_latest(self, *args):
        def usage():
            print("usage: latest [-h] [-n] <number>")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--number (-n)\tnumber of entries to be shown")
            print("")

        try:
            opts, argv = getopt.getopt(args, 'hn:', ['help', 'number'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_number = 7 

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-n', '--number'):
                arg_number = value 
		print(arg_number)
        # One of the most useful search terms is by tag. With the --tags
        # argument we first retrieve a list of existing tags and the count
        # of files associated with each of them.
        
		# Retrieve list of latest.
		items = self.db.list_latest_malware(arg_number)

		if items:
			rows = []
			for item in items:
				rows.append([item.name, item.type,item.created_at,item.sha256])

        		# Generate a table with the results.
        		print(table(['Name', 'Type','created', 'SHA256'], rows))
		else:
			print("No latest available")

		return

        # At this point, if there are no search terms specified, return.
        if len(args) == 0:
            usage()
            return
