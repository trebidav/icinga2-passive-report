#!/usr/bin/env python3

import os
import argparse
import sys
import requests
from datetime import date

def walklevel(some_dir, level=1):
    some_dir = some_dir.rstrip(os.path.sep)
    assert os.path.isdir(some_dir)
    num_sep = some_dir.count(os.path.sep)
    for root, dirs, files in os.walk(some_dir):
        yield root, dirs, files
        num_sep_this = root.count(os.path.sep)
        if num_sep + level <= num_sep_this:
            del dirs[:]

parser = argparse.ArgumentParser(description='Checks folder if new backups are present and reports to Icinga2')
parser.add_argument('--listname', nargs='?', metavar='filename', help='Name of the file which contains list of backed-up files - default: list.txt', default="list.txt")
parser.add_argument('--dir', nargs='?', metavar='directory', help='Directory where backups are stored - default: ./backup', default=os.path.dirname(sys.argv[0])+"/backup")
parser.add_argument('--icingaserverhost', nargs='?', metavar='hostname', help='Icinga2 API server where the passive check should be processed - default: icinga2.vlp.cz', default="icinga2.vlp.cz")
parser.add_argument('--icingaserverport', nargs='?', metavar='port', help='Icinga2 API server port - default: 5665', default="5665")
parser.add_argument('--icingaserveruser', nargs='?', metavar='username', help='Icinga2 API user - default: root', default="root")
parser.add_argument('--icingaserverpass', nargs='?', metavar='password', help='Icinga2 API password - default: root', default="root")
parser.add_argument('--icingahost', nargs='?', metavar='hostname', help='Name of the Icinga2 host - default: icinga2.vlp.cz', default="icinga2.vlp.cz")
parser.add_argument('--icingaservice', nargs='?', metavar='servicename', help='Name of the Icinga2 service associated with the icingahost - defuault: external-check', default="external-check")
parser.add_argument('--maxage', nargs='?', metavar='seconds', type=int, help='Maximum age of backups in seconds - default 30h (108000s)', default=108000)
parser.add_argument('--filenames', metavar='N', type=str, nargs='+', help='Filenames to check if present')
parser.add_argument('--verbose', help='Increase verbosity level', default=False, action="store_true")
parser.add_argument('--sendfails', help='Send passive check if script fails', default=False, action="store_true")

args = parser.parse_args()

url = 'https://'+ args.icingaserverhost + ':' + args.icingaserverport + '/v1/actions/process-check-result?service=' + args.icingahost + "!" + args.icingaservice
print(url)

new_dirs = []
today = date.today()

for root, dirs, files in walklevel(args.dir,level=0):
    for name in dirs:
        filedate = date.fromtimestamp(os.path.getmtime(os.path.join(root, name)))
        if (today - filedate).total_seconds() < args.maxage:
            new_dirs.append(name)

print (new_dirs)

#'{ "exit_status": 0, "plugin_output": "OK - files backed up", "performance_data": [ "size=", "age=" ], "check_source": "args.icingahost" }'

