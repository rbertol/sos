# Copyright (C) 2018 Red Hat, Inc., Jake Hunsaker <jhunsake@redhat.com>

# This file is part of the sos project: https://github.com/sosreport/sos
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# version 2 of the GNU General Public License.
#
# See the LICENSE file in the source distribution for further information.

from sos.report.plugins import Plugin, RedHatPlugin, UbuntuPlugin


class Alternatives(Plugin):

    short_desc = 'System alternatives'
    plugin_name = 'alternatives'
    alternatives_cmd = None
    alternatives_list = None

    def setup(self):

        self.add_cmd_output(f'{self.alternatives_cmd} --version')

        alts = []
        ignore = [
            'cdrecord',
            'ld',
            'mkisofs',
            'whois',
            'xinputrc'
        ]

        res = self.collect_cmd_output(self.alternatives_list)
        if res['status'] == 0:
            for line in res['output'].splitlines():
                alt = line.split()[0]
                if alt not in ignore:
                    alts.append(alt)
            disp_cmd = f"{self.alternatives_cmd} --display %s"
            self.add_cmd_output([disp_cmd % alt for alt in alts])


class RedHatAlternatives(Alternatives, RedHatPlugin):

    packages = ('alternatives',)
    commands = ('alternatives',)

    alternatives_cmd = 'alternatives'
    alternatives_list = f'{alternatives_cmd} --list'

    def setup(self):

        super().setup()

        self.add_cmd_tags({
            "alternatives --display java.*": 'display_java',
            "alternatives --display python.*":
                'alternatives_display_python'
        })


class UbuntuAlternatives(Alternatives, UbuntuPlugin):

    packages = ('dpkg',)
    commands = ('update-alternatives',)

    alternatives_cmd = 'update-alternatives'
    alternatives_list = f'{alternatives_cmd} --get-selections'

    def setup(self):

        super().setup()

        if self.get_option("all_logs"):
            self.add_copy_spec([
                "/var/log/alternatives.log*",
            ])
        else:
            self.add_copy_spec([
                "/var/log/alternatives.log",
                "/var/log/alternatives.log.1",
            ])

# vim: set et ts=4 sw=4 :
