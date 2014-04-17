# Copyright (C) 2013-2014 Claudio "nex" Guarnieri.
# This file is part of Viper - https://github.com/botherder/viper
# See the file 'LICENSE' for copying permission.

import os
import re
import getopt
import importlib

from viper.common.out import *
from viper.common.abstracts import Module
from viper.core.session import __session__

class RAT(Module):
    cmd = 'rat'
    description = 'Extract information from known RAT families'

    def get_config(self, family):
        if not __session__.is_set():
            print_error("No session opened")
            return

        try:
            module = importlib.import_module('modules.rats.{0}'.format(family))
        except ImportError:
            print_error("There is no module for family {0}".format(bold(family)))
            return

        config = module.config(__session__.file.data)
        if config == None:
            print_info("No Configuration Detected")
            return

        rows = []
        for key, value in config.items():
            rows.append([key, value])

        print_info("Configuration:")
        print(table(header=['Key', 'Value'], rows=rows))

    def run(self):
        def usage():
            print("usage: xtreme [option]")

        def help():
            usage()
            print("")
            print("Options:")
            print("\t--help (-h)\tShow this help message")
            print("\t--auto (-a)\tAutomatically detect RAT")
            print("\t--family (-f)\tSpecify which RAT family")
            print("")

        try:
            opts, argv = getopt.getopt(self.args[0:], 'haf:', ['help', 'auto', 'family='])
        except getopt.GetoptError as e:
            print(e)
            return

        auto = False
        family = None

        for opt, value in opts:
            if opt in ('-h', '--help'):
                help()
                return
            elif opt in ('-a', '--auto'):
                # TODO
                return
            elif opt in ('-f', '--family'):
                family = value

        if not auto and not family:
            help()
            return

        if family:
            self.get_config(family)
