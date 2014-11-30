# This file is part of Viper - https://github.com/botherder/viper
# See the file 'LICENSE' for copying permission.

import os
import json
import getopt

try:
    import requests
    HAVE_REQUESTS = True
except ImportError:
    HAVE_REQUESTS = False

from viper.common.out import *
from viper.common.abstracts import Module
from viper.core.session import __sessions__
from config import vt_key as KEY


VIRUSTOTAL_URL = 'https://www.virustotal.com/vtapi/v2/file/report'
VIRUSTOTAL_URL_SUBMIT = 'https://www.virustotal.com/vtapi/v2/file/scan'

class VirusTotal(Module):
    cmd = 'virustotal'
    description = 'Lookup the file on VirusTotal'
    authors = ['nex']

    def run(self):
        def usage():
            print("usage: virustotal [-h] [-s]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--submit (-s)\tSubmit file to VirusTotal (by default it only looks up the hash)")
            print("")

        arg_submit = False

        try:
            opts, argv = getopt.getopt(self.args[0:], 'hs', ['help', 'submit'])
        except getopt.GetoptError as e:
            print(e)
            return

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-s', '--submit'):
                arg_submit = True

        if not HAVE_REQUESTS:
            print_error("Missing dependency, install requests (`pip install requests`)")
            return

        if not __sessions__.is_set():
            print_error("No session opened")
            return

        data = {'resource' : __sessions__.current.file.md5, 'apikey' : KEY}

        try:
            response = requests.post(VIRUSTOTAL_URL, data=data)
        except Exception as e:
            print_error("Failed performing request: {0}".format(e))
            return

        try:
            virustotal = response.json()
            # since python 2.7 the above line causes the Error dict object not callable
        except Exception as e:
            # workaround in case of python 2.7
            if str(e) == "'dict' object is not callable":
                try:
                    virustotal = response.json
                except Exception as e:
                    print_error("Failed parsing the response: {0}".format(e))
                    print_error("Data:\n{}".format(response.content))
                    return                        
            else:
                print_error("Failed parsing the response: {0}".format(e))
                print_error("Data:\n{}".format(response.content))
                return

        rows = []
        if 'scans' in virustotal:
            for engine, signature in virustotal['scans'].items():
                if signature['detected']:
                    signature = signature['result']
                else:
                    signature = ''
                rows.append([engine, signature])

        rows.sort()
        if rows:
            print_info("VirusTotal Report:")
            print(table(['Antivirus', 'Signature'], rows))

            if arg_submit:
                print("")
                print_info("The file is already available on VirusTotal, no need to submit")
        else:
            print_info("The file does not appear to be on VirusTotal yet")

            if arg_submit:
                try:
                    data = {'apikey' : KEY}
                    files = {'file' : open(__sessions__.current.file.path, 'rb').read()}
                    response = requests.post(VIRUSTOTAL_URL_SUBMIT, data=data, files=files)
                except Exception as e:
                    print_error("Failed Submit: {0}".format(e))
                    return

                try:
                    virustotal = response.json()
                    # since python 2.7 the above line causes the Error dict object not callable
                except Exception as e:
                    # workaround in case of python 2.7
                    if str(e) == "'dict' object is not callable":
                        try:
                            virustotal = response.json
                        except Exception as e:
                            print_error("Failed parsing the response: {0}".format(e))
                            print_error("Data:\n{}".format(response.content))
                            return                        
                    else:
                        print_error("Failed parsing the response: {0}".format(e))
                        print_error("Data:\n{}".format(response.content))
                        return

                if 'verbose_msg' in virustotal:
                    print_info("{}: {}".format(bold("VirusTotal message"), virustotal['verbose_msg']))
