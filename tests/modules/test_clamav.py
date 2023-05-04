# -*- coding: utf-8 -*-
# This file is part of Viper - https://github.com/viper-framework/viper
# See the file 'LICENSE' for copying permission.

import os
import re

import pytest

from tests.conftest import FIXTURE_DIR
from viper.common.abstracts import ArgumentErrorCallback, Module
from viper.core.plugins import __modules__
from viper.core.session import __sessions__

clamav = __modules__["clamav"]["obj"]


class TestClamAV:
    def test_init(self):
        instance = clamav()
        assert isinstance(instance, clamav)
        assert isinstance(instance, Module)

    def test_args_exception(self):
        instance = clamav()
        with pytest.raises(ArgumentErrorCallback) as excinfo:
            instance.parser.parse_args(["-h"])
        excinfo.match(r".*Scan file from local ClamAV daemon.*")

    def test_run_help(self, capsys):
        instance = clamav()
        instance.set_commandline(["--help"])

        instance.run()
        out, err = capsys.readouterr()
        assert re.search(r"^usage:.*", out)

    def test_run_short_help(self, capsys):
        instance = clamav()
        instance.set_commandline(["-h"])

        instance.run()
        out, err = capsys.readouterr()
        assert re.search(r"^usage:.*", out)

    def test_run_invalid_option(self, capsys):
        instance = clamav()
        instance.set_commandline(["invalid"])

        instance.run()
        out, err = capsys.readouterr()
        assert re.search(r".*unrecognized arguments:.*", out)

    @pytest.mark.parametrize("filename", ["whoami.exe"])
    def test_run_session(self, capsys, filename):
        __sessions__.new(os.path.join(FIXTURE_DIR, filename))
        instance = clamav()
        instance.command_line = []

        instance.run()
        out, err = capsys.readouterr()

        assert re.search(r".*Clamav identify.*", out)

    def test_run_all(self, capsys):
        instance = clamav()
        instance.set_commandline(["-a", "-t"])

        instance.run()
        out, err = capsys.readouterr()
        assert re.search(r".*Clamav identify.*", out)
