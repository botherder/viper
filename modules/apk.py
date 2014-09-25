# This file is part of Viper - https://github.com/botherder/viper
# See the file 'LICENSE' for copying permission.

import os
import getopt

from viper.common.out import *
from viper.common.abstracts import Module
from viper.core.session import __sessions__

try:
    from androguard.core import *
    from androguard.core.bytecodes.dvm import *
    from androguard.core.bytecodes.apk import *
    from androguard.core.analysis.analysis import *
    from androguard.core.analysis.ganalysis import *
    from androguard.decompiler.decompiler import *
    HAVE_ANDROGUARD = True
except Exception:
    HAVE_ANDROGUARD = False

class AndroidPackage(Module):
    cmd = 'apk'
    description = 'Parse Android Applications'
    authors = ['Kevin Breen']
            
    def run(self):
        def usage():
            print("usage: apk [-hipfad]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--info (-i)\tShow general info")
            print("\t--perm (-p)\tShow APK permissions")
            print("\t--file (-f)\tShow APK file list")
            print("\t--all (-a)\tRun all options excluding dump")
            print("\t--dump (-d)\tExtract all items from archive")
            return

        def analyze_apk(filename, raw=False, decompiler=None) :
            """
            Analyze an android application and setup all stuff for a more quickly analysis !
            
            :param filename: the filename of the android application or a buffer which represents the application
            :type filename: string
            :param raw: True is you would like to use a buffer (optional)
            :type raw: boolean
            :param decompiler: ded, dex2jad, dad (optional)
            :type decompiler: string
            
            :rtype: return the :class:`APK`, :class:`DalvikVMFormat`, and :class:`VMAnalysis` objects
            """
            a = APK(filename, raw)
            d, dx = analyze_dex( a.get_dex(), raw=True, decompiler=decompiler )
            return a, d, dx

        def analyze_dex(filename, raw=False, decompiler=None) :
            """
            Analyze an android dex file and setup all stuff for a more quickly analysis !

            :param filename: the filename of the android dex file or a buffer which represents the dex file
            :type filename: string
            :param raw: True is you would like to use a buffer (optional)
            :type raw: boolean

            :rtype: return the :class:`DalvikVMFormat`, and :class:`VMAnalysis` objects
            """
            d = None
            if raw == False :
                d = DalvikVMFormat( open(filename, "rb").read() )
            else :
                d = DalvikVMFormat( filename )
            d.create_python_export()
            dx = uVMAnalysis( d )
            gx = GVMAnalysis( dx, None )
            d.set_vmanalysis( dx )
            d.set_gvmanalysis( gx )
            run_decompiler( d, dx, decompiler )
            d.create_xref()
            d.create_dref()

            return d, dx

        def run_decompiler(d, dx, decompiler) :
            """
            Run the decompiler on a specific analysis

            :param d: the DalvikVMFormat object
            :type d: :class:`DalvikVMFormat` object
            :param dx: the analysis of the format
            :type dx: :class:`VMAnalysis` object 
            :param decompiler: the type of decompiler to use ("dad", "dex2jad", "ded")
            :type decompiler: string
            """
            if decompiler != None :
              decompiler = decompiler.lower()
              if decompiler == "dex2jad" :
                d.set_decompiler( DecompilerDex2Jad( d, androconf.CONF["PATH_DEX2JAR"], androconf.CONF["BIN_DEX2JAR"], androconf.CONF["PATH_JAD"], androconf.CONF["BIN_JAD"], androconf.CONF["TMP_DIRECTORY"] ) )
              elif decompiler == "ded" :
                d.set_decompiler( DecompilerDed( d, androconf.CONF["PATH_DED"], androconf.CONF["BIN_DED"], androconf.CONF["TMP_DIRECTORY"]) )
              elif decompiler == "dad" :
                d.set_decompiler( DecompilerDAD( d, dx ) )
              else :
                print_info("Unknown decompiler, use DAD decompiler by default")
                d.set_decompiler( DecompilerDAD( d, dx ) )

        # List all files and types
        def andro_file(a):
            print_info("APK Contents")
            rows = []
            for file_name, file_type in a.files.iteritems():
                rows.append([file_name, file_type])
            print(table(header=['File Name', 'File Type'], rows=rows))

        # List general info
        def andro_info(a):
            print_info("APK General Information")
            print_item("Package Name: {0}".format(a.package))
            print_item("Version Code: {0}".format(a.androidversion['Code']))
            print_item("Main Activity: {0}".format(a.get_main_activity()))
            print_info("Other Activities")
            for item in a.get_activities():
                print_item(item)
            print_info("Services")
            for item in a.get_services():
                print_item(item)
            print_info("Receivers")
            for item in a.get_receivers():
                print_item(item)

        # List all the permisisons
        def andro_perm(a):
            print_info("APK Permissions")
            for perms in a.permissions:
                print_item(perms)

        # Decompile and Dump all the methods
        def andro_dump(vm, vmx, dump_path):
            # Export each decompiled method
            for method in vm.get_methods():
                mx = vmx.get_method(method)

                if method.get_code() == None:
                    continue
                ms = decompile.DvMethod(mx)
                ms.process()
                this = ms.get_source()
                with open(dump_path, 'a+') as outfile:
                    outfile.write(str(method.get_class_name()))
                    outfile.write(str(method.get_name())+'\n')
                    outfile.write(ms.get_source())
                    outfile.write('\n')

        def process_apk():
            # Process the APK File
            try:
                print_info("Processing the APK, this may take a moment...")
                APK_FILE = __sessions__.current.file.path
                a, vm, vmx = analyze_apk(APK_FILE, decompiler='dad')
                return a, vm, vmx
            except AttributeError as e:
                print_error("Error: {0}".format(e))
                return False, False, False

        #Check for session
        if not __sessions__.is_set():
            print_error("No session opened")
            return

        # Check for androguard
        if not HAVE_ANDROGUARD:
            print_error("Unable to import AndroGuard")
            print_error("Install https://code.google.com/p/androguard/downloads/detail?name=androguard-1.9.tar.gz")
            return

        # Get args and opts
        try:
            opts, argv = getopt.getopt(self.args, 'hipfad:', ['help', 'info', 'perm', 'files', 'all', 'dump='])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return
            
        arg_dump = None
        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return        
            elif opt in ('-d', '--dump'):
                arg_dump = value
                a, vm, vmx = process_apk()
                if not a:
                    return
                print_info("Decompiling Code")
                andro_dump(vm, vmx, arg_dump)
                print_info("Decompiled code saved to {0}".format(arg_dump))
                return
            elif opt in ('-i', '--info'):
                a, vm, vmx = process_apk()
                if not a:
                    return
                andro_info(a)
                return
            elif opt in ('-p', '--perm'):
                a, vm, vmx = process_apk()
                if not a:
                    return
                andro_perm(a)
                return
            elif opt in ('-f', '--file'):
                a, vm, vmx = process_apk()
                if not a:
                    return
                andro_file(a)
                return
            elif opt in ('-a', '--all'):
                a, vm, vmx = process_apk()
                if not a:
                    return
                andro_info(a)
                andro_perm(a)
                andro_file(a)
                return

        usage()
