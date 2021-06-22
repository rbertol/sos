# Copyright (C) 2021 Red Hat, Inc., Pavel Moravec <pmoravec@redhat.com>

# This file is part of the sos project: https://github.com/sosreport/sos
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# version 2 of the GNU General Public License.
#
# See the LICENSE file in the source distribution for further information.

from sos.report.plugins import Plugin, IndependentPlugin
from pipes import quote
from re import match


class PulpCore(Plugin, IndependentPlugin):

    short_desc = 'Pulp-3 aka pulpcore'

    plugin_name = "pulpcore"
    commands = ("pulpcore-manager",)
    files = ("/etc/pulp/settings.py",)
    option_list = [
        ('task-days', 'days of tasks history', 'fast', 7)
    ]

    def parse_settings_config(self):
        databases_scope = False
        self.dbhost = "localhost"
        self.dbport = 5432
        self.dbpasswd = ""
        # TODO: read also redis config (we dont expect much customisations)
        # TODO: read also db user (pulp) and database name (pulpcore)
        self.staticroot = "/var/lib/pulp/assets"
        self.uploaddir = "/var/lib/pulp/media/upload"

        def separate_value(line, sep=':'):
            # an auxiliary method to parse values from lines like:
            #       'HOST': 'localhost',
            val = line.split(sep)[1].lstrip().rstrip(',')
            if (val.startswith('"') and val.endswith('"')) or \
               (val.startswith('\'') and val.endswith('\'')):
                val = val[1:-1]
            return val

        try:
            for line in open("/etc/pulp/settings.py").read().splitlines():
                # skip empty lines and lines with comments
                if not line or line[0] == '#':
                    continue
                if line.startswith("DATABASES"):
                    databases_scope = True
                    continue
                # example HOST line to parse:
                #         'HOST': 'localhost',
                if databases_scope and match(r"\s+'HOST'\s*:\s+\S+", line):
                    self.dbhost = separate_value(line)
                if databases_scope and match(r"\s+'PORT'\s*:\s+\S+", line):
                    self.dbport = separate_value(line)
                if databases_scope and match(r"\s+'PASSWORD'\s*:\s+\S+", line):
                    self.dbpasswd = separate_value(line)
                # if line contains closing '}' database_scope end
                if databases_scope and '}' in line:
                    databases_scope = False
                if line.startswith("STATIC_ROOT = "):
                    self.staticroot = separate_value(line, sep='=')
                if line.startswith("CHUNKED_UPLOAD_DIR = "):
                    self.uploaddir = separate_value(line, sep='=')
        except IOError:
            # fallback when the cfg file is not accessible
            pass
        # set the password to os.environ when calling psql commands to prevent
        # printing it in sos logs
        # we can't set os.environ directly now: other plugins can overwrite it
        self.env = {"PGPASSWORD": self.dbpasswd}

    def setup(self):
        self.parse_settings_config()

        self.add_copy_spec([
            "/etc/pulp/settings.py",
            "/etc/pki/pulp/*"
        ])
        # skip collecting certificate keys
        self.add_forbidden_path("/etc/pki/pulp/*.key")

        self.add_cmd_output("rq info -u redis://localhost:6379/8",
                            env={"LC_ALL": "en_US.UTF-8"},
                            suggest_filename="rq_info")
        self.add_cmd_output("curl -ks https://localhost/pulp/api/v3/status/",
                            suggest_filename="pulp_status")
        dynaconf_env = {"LC_ALL": "en_US.UTF-8",
                        "PULP_SETTINGS": "/etc/pulp/settings.py",
                        "DJANGO_SETTINGS_MODULE": "pulpcore.app.settings"}
        self.add_cmd_output("dynaconf list", env=dynaconf_env)
        for _dir in [self.staticroot, self.uploaddir]:
            self.add_cmd_output("ls -l %s" % _dir)

        task_days = self.get_option('task-days')
        for table in ['core_task', 'core_taskgroup',
                      'core_reservedresourcerecord',
                      'core_taskreservedresourcerecord',
                      'core_groupprogressreport', 'core_progressreport']:
            _query = "select * from %s where pulp_last_updated > NOW() - " \
                     "interval '%s days' order by pulp_last_updated" % \
                     (table, task_days)
            _cmd = "psql -h %s -p %s -U pulp -d pulpcore -c %s" % \
                   (self.dbhost, self.dbport, quote(_query))
            self.add_cmd_output(_cmd, env=self.env, suggest_filename=table)

    def postproc(self):
        # TODO obfuscate from /etc/pulp/settings.py :
        # SECRET_KEY = "eKfeDkTnvss7p5WFqYdGPWxXfHnsbDBx"
        # 'PASSWORD': 'tGrag2DmtLqKLTWTQ6U68f6MAhbqZVQj',
        self.do_path_regex_sub(
            "/etc/pulp/settings.py",
            r"(SECRET_KEY\s*=\s*)(.*)",
            r"\1********")
        self.do_path_regex_sub(
            "/etc/pulp/settings.py",
            r"(PASSWORD\S*\s*:\s*)(.*)",
            r"\1********")
        # apply the same for "dynaconf list" output that prints settings.py
        # in a pythonic format
        self.do_cmd_output_sub(
            "dynaconf list",
            r"(SECRET_KEY<str>\s*)'(.*)'",
            r"\1********")
        self.do_cmd_output_sub(
            "dynaconf list",
            r"(PASSWORD\S*\s*:\s*)(.*)",
            r"\1********")


# vim: set et ts=4 sw=4 :
