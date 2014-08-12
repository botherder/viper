# This file is part of Viper - https://github.com/botherder/viper
# See the file 'LICENSE' for copying permission.

import re
import getopt
import datetime
import tempfile

try:
    import pefile
    import peutils
    HAVE_PEFILE = True
except ImportError:
    HAVE_PEFILE = False

from viper.common.out import *
from viper.common.objects import File
from viper.common.abstracts import Module
from viper.common.utils import get_type, get_md5
from viper.core.database import Database
from viper.core.storage import get_sample_path
from viper.core.session import __sessions__

class PE(Module):
    cmd = 'pe'
    description = 'Extract information from PE32 headers'
    authors = ['nex']

    def __init__(self):
        self.pe = None

    def __check_session(self):
        if not __sessions__.is_set():
            print_error("No session opened")
            return False

        if not self.pe:
            try:
                self.pe = pefile.PE(__sessions__.current.file.path)
            except pefile.PEFormatError as e:
                print_error("Unable to parse PE file: {0}".format(e))
                return False

        return True

    def imports(self):
        if not self.__check_session():
            return

        if hasattr(self.pe, 'DIRECTORY_ENTRY_IMPORT'):
            for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
                try:
                    print_info("DLL: {0}".format(entry.dll))
                    for symbol in entry.imports:
                        print_item("{0}: {1}".format(hex(symbol.address), symbol.name), tabs=1)
                except:
                    continue
    
    def exports(self):
        if not self.__check_session():
            return
        
        print_info("Exports:")
        if hasattr(self.pe, 'DIRECTORY_ENTRY_EXPORT'):
            for symbol in self.pe.DIRECTORY_ENTRY_EXPORT.symbols:
                print_item("{0}: {1} ({2})".format(hex(self.pe.OPTIONAL_HEADER.ImageBase + symbol.address), symbol.name, symbol.ordinal), tabs=1)

    def compiletime(self):

        def usage():
            print("usage: pe compiletime [-s] [-w=minutes]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--scan (-s)\tScan the repository for common compile time")
            print("\t--window (-w)\tSpecify an optional time window in minutes")
            print("")

        def get_compiletime(pe):
            return datetime.datetime.fromtimestamp(pe.FILE_HEADER.TimeDateStamp)

        try:
            opts, argv = getopt.getopt(self.args[1:], 'hsw:', ['help', 'scan', 'window='])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_scan = False
        arg_window = None

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-s', '--scan'):
                arg_scan = True
            elif opt in ('-w', '--window'):
                arg_window = int(value)

        if not self.__check_session():
            return

        compile_time = get_compiletime(self.pe)
        print_info("Compile Time: {0}".format(bold(compile_time)))

        if arg_scan:
            print_info("Scanning the repository for matching samples...")

            db = Database()
            samples = db.find(key='all')

            matches = []
            for sample in samples:
                if sample.sha256 == __sessions__.current.file.sha256:
                    continue

                sample_path = get_sample_path(sample.sha256)
                if not os.path.exists(sample_path):
                    continue

                try:
                    cur_pe = pefile.PE(sample_path)
                    cur_compile_time = get_compiletime(cur_pe)
                except:
                    continue

                if compile_time == cur_compile_time:
                    matches.append([sample.name, sample.sha256, cur_compile_time])
                else:
                    if arg_window:
                        if cur_compile_time > compile_time:
                            delta = (cur_compile_time - compile_time)
                        elif cur_compile_time < compile_time:
                            delta = (compile_time - cur_compile_time)

                        delta_minutes = int(delta.total_seconds()) / 60
                        if delta_minutes <= arg_window:
                            matches.append([sample.name, sample.sha256, cur_compile_time])

            print_info("{0} relevant matches found".format(bold(len(matches))))

            if len(matches) > 0:
                print(table(header=['Name', 'SHA256', 'Compile Time'], rows=matches))

    def peid(self):

        def usage():
            print("usage: pe peid [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--scan (-s)\tScan the repository for PEiD signatures")
            print("")

        def get_signatures():
            with file('data/peid/UserDB.TXT', 'rt') as f:
                sig_data = f.read()

            signatures = peutils.SignatureDatabase(data=sig_data)

            return signatures

        def get_matches(pe, signatures):
            matches = signatures.match_all(pe, ep_only=True)
            return matches

        try:
            opts, argv = getopt.getopt(self.args[1:], 'hsf', ['help', 'scan'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_scan = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-s', '--scan'):
                arg_scan = True

        if not self.__check_session():
            return

        signatures = get_signatures()
        peid_matches = get_matches(self.pe, signatures)

        if peid_matches:
            print_info("PEiD Signatures:")
            for sig in peid_matches:
                if type(sig) is list:
                    print_item(sig[0])
                else:
                    print_item(sig)
        else:
            print_info("No PEiD signatures matched.")

        if arg_scan and peid_matches:
            print_info("Scanning the repository for matching samples...")

            db = Database()
            samples = db.find(key='all')

            matches = []
            for sample in samples:
                if sample.sha256 == __sessions__.current.file.sha256:
                    continue

                sample_path = get_sample_path(sample.sha256)
                if not os.path.exists(sample_path):
                    continue

                try:
                    cur_pe = pefile.PE(sample_path)
                    cur_peid_matches = get_matches(cur_pe, signatures)
                except:
                    continue

                if peid_matches == cur_peid_matches:
                    matches.append([sample.name, sample.sha256])

            print_info("{0} relevant matches found".format(bold(len(matches))))

            if len(matches) > 0:
                print(table(header=['Name', 'SHA256'], rows=matches))

    def resources(self):

        def usage():
            print("usage: pe resources [-d=folder] [-o=resource number] [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--dump (-d)\tDestination directory to store resource files in")
            print("\t--open (-o)\tOpen a session on the specified resource")
            print("\t--scan (-s)\tScan the repository for common resources")
            print("")

        # Use this function to retrieve resources for the given PE instance.
        # Returns all the identified resources with indicators and attributes.
        def get_resources(pe):
            resources = []
            if hasattr(pe, 'DIRECTORY_ENTRY_RESOURCE'):
                count = 1
                for resource_type in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                    try:
                        resource = {}

                        if resource_type.name is not None:
                            name = str(resource_type.name)
                        else:
                            name = str(pefile.RESOURCE_TYPE.get(resource_type.struct.Id))

                        if name == None:
                            name = str(resource_type.struct.Id)

                        if hasattr(resource_type, 'directory'):
                            for resource_id in resource_type.directory.entries:
                                if hasattr(resource_id, 'directory'):
                                    for resource_lang in resource_id.directory.entries:
                                        data = pe.get_data(resource_lang.data.struct.OffsetToData, resource_lang.data.struct.Size)
                                        filetype = get_type(data)
                                        md5 = get_md5(data)
                                        language = pefile.LANG.get(resource_lang.data.lang, None)
                                        sublanguage = pefile.get_sublang_name_for_lang(resource_lang.data.lang, resource_lang.data.sublang)
                                        offset = ('%-8s' % hex(resource_lang.data.struct.OffsetToData)).strip()
                                        size = ('%-8s' % hex(resource_lang.data.struct.Size)).strip()

                                        resource = [count, name, offset, md5, size, filetype, language, sublanguage]

                                        # Dump resources if requested to and if the file currently being
                                        # processed is the opened session file.
                                        # This is to avoid that during a --scan all the resources being
                                        # scanned are dumped as well.
                                        if (arg_open or arg_dump) and pe == self.pe:
                                            if arg_dump:
                                                folder = arg_dump
                                            else:
                                                folder = tempfile.mkdtemp()

                                            resource_path = os.path.join(folder, '{0}_{1}_{2}'.format(__sessions__.current.file.md5, offset, name))
                                            resource.append(resource_path)

                                            with open(resource_path, 'wb') as resource_handle:
                                                resource_handle.write(data)

                                        resources.append(resource)

                                        count += 1
                    except Exception as e:
                        print_error(e)
                        continue
            
            return resources

        try:
            opts, argv = getopt.getopt(self.args[1:], 'ho:d:s', ['help', 'open=', 'dump=', 'scan'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_open = None
        arg_dump = None
        arg_scan = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-o', '--open'):
                arg_open = int(value)
            elif opt in ('-d', '--dump'):
                arg_dump = value
            elif opt in ('-s', '--scan'):
                arg_scan = True

        if not self.__check_session():
            return

        # Obtain resources for the currently opened file.
        resources = get_resources(self.pe)

        if not resources:
            print_warning("No resources found")
            return

        headers = ['#', 'Name', 'Offset', 'MD5', 'Size', 'File Type', 'Language', 'Sublanguage']
        if arg_dump or arg_open:
            headers.append('Dumped To')

        print table(headers, resources)

        # If instructed, open a session on the given resource.
        if arg_open:
            for resource in resources:
                if resource[0] == arg_open:
                    __sessions__.new(resource[8])
                    return
        # If instructed to perform a scan across the repository, start looping
        # through all available files.
        elif arg_scan:
            print_info("Scanning the repository for matching samples...")

            # Retrieve list of samples stored locally and available in the
            # database.
            db = Database()
            samples = db.find(key='all')

            matches = []
            for sample in samples:
                # Skip if it's the same file.
                if sample.sha256 == __sessions__.current.file.sha256:
                    continue

                # Obtain path to the binary.
                sample_path = get_sample_path(sample.sha256)
                if not os.path.exists(sample_path):
                    continue

                # Open PE instance.
                try:
                    cur_pe = pefile.PE(sample_path)
                except:
                    continue

                # Obtain the list of resources for the current iteration.
                cur_resources = get_resources(cur_pe)
                matched_resources = []
                # Loop through entry's resources.
                for cur_resource in cur_resources:
                    # Loop through opened file's resources.
                    for resource in resources:
                        # If there is a common resource, add it to the list.
                        if cur_resource[3] == resource[3]:
                            matched_resources.append(resource[3])

                # If there are any common resources, add the entry to the list
                # of matched samples.
                if len(matched_resources) > 0:
                    matches.append([sample.name, sample.sha256, '\n'.join(r for r in matched_resources)])

            print_info("{0} relevant matches found".format(bold(len(matches))))

            if len(matches) > 0:
                print(table(header=['Name', 'SHA256', 'Resource MD5'], rows=matches))

    def imphash(self):

        def usage():
            print("usage: pe imphash [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--scan (-s)\tScan for all samples with same imphash")
            print("\t--cluster (-c)\tCluster repository by imphash (careful, could be massive)")
            print("")

        try:
            opts, argv = getopt.getopt(self.args[1:], 'hsc', ['help', 'scan', 'cluster'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_scan = False
        arg_cluster = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-s', '--scan'):
                arg_scan = True
            elif opt in ('-c', '--cluster'):
                arg_cluster = True

        if arg_scan and arg_cluster:
            print_error("You selected two exclusive options, pick one")
            return

        if arg_cluster:
            print_info("Clustering all samples by imphash...")

            db = Database()
            samples = db.find(key='all')

            cluster = {}
            for sample in samples:
                sample_path = get_sample_path(sample.sha256)
                if not os.path.exists(sample_path):
                    continue

                try:
                    cur_imphash = pefile.PE(sample_path).get_imphash()
                except:
                    continue

                if cur_imphash not in cluster:
                    cluster[cur_imphash] = []

                cluster[cur_imphash].append([sample.sha256, sample.name])

            for key, value in cluster.items():
                # Skipping clusters with only one entry.
                if len(value) == 1:
                    continue

                print_info("Imphash cluster {0}".format(bold(key)))

                for entry in value:
                    print_item("{0} [{1}]".format(entry[0], entry[1]))

                print("")

            return

        if self.__check_session():
            try:
                imphash = self.pe.get_imphash()
            except AttributeError:
                print_error("No imphash support, upgrade pefile to a version >= 1.2.10-139 (`pip install --upgrade pefile`)")
                return

            print_info("Imphash: {0}".format(bold(imphash)))

            if arg_scan:
                print_info("Scanning the repository for matching samples...")

                db = Database()
                samples = db.find(key='all')

                matches = []
                for sample in samples:
                    if sample.sha256 == __sessions__.current.file.sha256:
                        continue

                    sample_path = get_sample_path(sample.sha256)
                    if not os.path.exists(sample_path):
                        continue

                    try:
                        cur_imphash = pefile.PE(sample_path).get_imphash()
                    except:
                        continue

                    if imphash == cur_imphash:
                        matches.append([sample.name, sample.sha256])

                print_info("{0} relevant matches found".format(bold(len(matches))))

                if len(matches) > 0:
                    print(table(header=['Name', 'SHA256'], rows=matches))

    def security(self):

        def usage():
            print("usage: pe security [-d=folder] [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--dump (-d)\tDestination directory to store digital signature in")
            print("\t--scan (-s)\tScan the repository for common certificates")
            print("")

        def get_certificate(pe):
            # TODO: this only extract the raw list of certificate data.
            # I need to parse them, extract single certificates and perhaps return
            # the PEM data of the first certificate only.
            pe_security_dir = pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_SECURITY']
            address = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pe_security_dir].VirtualAddress
            size = pe.OPTIONAL_HEADER.DATA_DIRECTORY[pe_security_dir].Size

            if address:
                return pe.write()[address+8:]
            else:
                return None

        try:
            opts, argv = getopt.getopt(self.args[1:], 'hd:s', ['help', 'dump=', 'scan'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_folder = None
        arg_scan = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-d', '--dump'):
                arg_folder = value
            elif opt in ('-s', '--scan'):
                arg_scan = True

        if not self.__check_session():
            return

        cert_data = get_certificate(self.pe)

        if not cert_data:
            print_warning("No certificate found")
            return

        cert_md5 = get_md5(cert_data)

        print_info("Found certificate with MD5 {0}".format(bold(cert_md5)))

        if arg_folder:
            cert_path = os.path.join(arg_folder, '{0}.crt'.format(__sessions__.current.file.sha256))
            with open(cert_path, 'wb+') as cert_handle:
                cert_handle.write(cert_data)

            print_info("Dumped certificate to {0}".format(cert_path))
            print_info("You can parse it using the following command:\n\t" + 
                       bold("openssl pkcs7 -inform DER -print_certs -text -in {0}".format(cert_path)))

        # TODO: do scan for certificate's serial number.
        if arg_scan:
            print_info("Scanning the repository for matching samples...")

            db = Database()
            samples = db.find(key='all')

            matches = []
            for sample in samples:
                # Skip if it's the same file.
                if sample.sha256 == __sessions__.current.file.sha256:
                    continue

                # Obtain path to the binary.
                sample_path = get_sample_path(sample.sha256)
                if not os.path.exists(sample_path):
                    continue

                # Open PE instance.
                try:
                    cur_pe = pefile.PE(sample_path)
                except:
                    continue

                cur_cert_data = get_certificate(cur_pe)

                if not cur_cert_data:
                    continue

                cur_cert_md5 = get_md5(cur_cert_data)
                if cur_cert_md5 == cert_md5:
                    matches.append([sample.name, sample.sha256])

            print_info("{0} relevant matches found".format(bold(len(matches))))

            if len(matches) > 0:
                print(table(header=['Name', 'SHA256'], rows=matches))                

    def language(self):

        def usage():
            print("usage: pe language [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--scan (-s)\tScan the repository")
            print("")

        def get_iat(pe):
            iat = []
            if hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
                for peimport in pe.DIRECTORY_ENTRY_IMPORT:
                    iat.append(peimport.dll)

            return iat
        
        def check_module(iat, match):
            for imp in iat:
                if imp.find(match) != -1:
                    return True

            return False

        def is_cpp(data, cpp_count):
            for line in data:
                if 'type_info' in line or 'RTTI' in line:
                    cpp_count += 1
                    break

            if cpp_count == 2:
                return True

            return False

        def is_delphi(data):
            for line in data:
                if 'Borland' in line:
                    path = line.split('\\')
                    for p in path:
                        if 'Delphi' in p:
                            return True
            return False
                    
        def is_vbdotnet(data):
            for line in data:
                if 'Compiler' in line:
                    stuff = line.split('.')
                    if 'VisualBasic' in stuff:
                        return True

            return False

        def is_autoit(data):
            for line in data:
                if 'AU3!' in line:
                    return True

            return False

        def is_packed(pe):
            for section in pe.sections:
                if section.get_entropy() > 7:
                    return True

            return False
        
        def get_strings(content):
            regexp = '[\x30-\x39\x41-\x5f\x61-\x7a\-\.:]{4,}'
            return re.findall(regexp, content)

        def find_language(iat, sample, content):
            dotnet = False
            cpp_count = 0
            found = None

            # VB check
            if check_module(iat, 'VB'):
                print_info("{0} - Possible language: Visual Basic".format(sample.name))
                return True

            # .NET check
            if check_module(iat, 'mscoree.dll') and not found:
                dotnet = True
                found = '.NET'
            
            # C DLL check
            if not found and (check_module(iat, 'msvcr') or check_module(iat, 'MSVCR') or check_module(iat, 'c++')):
                cpp_count += 1

            if not found:
                data = get_strings(content)
                
                if is_cpp(data, cpp_count) and not found:
                    found = 'CPP'
                if not found and cpp_count == 1:
                    found = 'C'
                if not dotnet and is_delphi(data) and not found:
                    found = 'Delphi'
                if dotnet and is_vbdotnet(data):
                    found = 'Visual Basic .NET'
                if is_autoit(data) and not found:
                    found = 'AutoIt'

            return found

        try:
            opts, argv = getopt.getopt(self.args[1:], 'hs', ['help', 'scan'])
        except getopt.GetoptError as e:
            print(e)
            usage()
            return

        arg_scan = False

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-s', '--scan'):
                arg_scan = True

        if not self.__check_session():
            return
        
        if is_packed(self.pe):
            print_warning("Probably packed, the language guess might be unreliable")

        language = find_language(
            get_iat(self.pe),
            __sessions__.current.file,
            __sessions__.current.file.data
        )

        if language:
            print_info("Probable language: {0}".format(bold(language)))
        else:
            print_error("Programming language not identified")
            return

        if arg_scan:
            print_info("Scanning the repository for matching samples...")

            db = Database()
            samples = db.find(key='all')

            matches = []
            for sample in samples:
                if sample.sha256 == __sessions__.current.file.sha256:
                    continue

                sample_path = get_sample_path(sample.sha256)

                if not os.path.exists(sample_path):
                    continue
                
                try:
                    cur_pe = pefile.PE(sample_path)
                except pefile.PEFormatError as e:
                    continue

                cur_packed = ''
                if is_packed(cur_pe):
                    cur_packed = 'Yes'

                cur_language = find_language(
                    get_iat(cur_pe),
                    sample,
                    open(sample_path, 'rb').read()
                )

                if not cur_language:
                    continue

                if cur_language == language:
                    matches.append([sample.name, sample.md5, cur_packed])

            if matches:
                print(table(header=['Name', 'MD5', 'Is Packed'], rows=matches))
            else:
                print_info("No matches found")

    def sections(self):
        if not self.__check_session():
            return

        rows = []
        for section in self.pe.sections:
            rows.append([
                section.Name,
                hex(section.VirtualAddress),
                hex(section.Misc_VirtualSize),
                section.SizeOfRawData,
                section.get_entropy()
            ])

        print_info("PE Sections:")
        print(table(header=['Name', 'RVA', 'VirtualSize', 'RawDataSize', 'Entropy'], rows=rows))

    def usage(self):
        print("usage: pe <command>")

    def help(self):
        self.usage()
        print("")
        print("Options:")
        print("\thelp\t\tShow this help message")
        print("\timports\t\tList PE imports")
        print("\texports\t\tList PE exports")
        print("\tresources\tList PE resources")
        print("\timphash\t\tGet and scan for imphash")
        print("\tcompiletime\tShow the compiletime")
        print("\tpeid\t\tShow the PEiD signatures")
        print("\tsecurity\tShow digital signature")
        print("\tlanguage\tGuess PE language")
        print("\tsections\tList PE Sections")
        print("")

    def run(self):
        if not HAVE_PEFILE:
            print_error("Missing dependency, install pefile (`pip install pefile`)")
            return

        if len(self.args) == 0:
            self.help()
            return

        if self.args[0] == 'help':
            self.help()
        elif self.args[0] == 'imports':
            self.imports()
        elif self.args[0] == 'exports':
            self.exports()
        elif self.args[0] == 'resources':
            self.resources()
        elif self.args[0] == 'imphash':
            self.imphash()
        elif self.args[0] == 'compiletime':
            self.compiletime()
        elif self.args[0] == 'peid':
            self.peid()
        elif self.args[0] == 'security':
            self.security()
        elif self.args[0] == 'sections':
            self.sections()
        elif self.args[0] == 'language':
            self.language()
