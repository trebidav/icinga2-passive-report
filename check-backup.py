#!/usr/bin/env python3

# David Trebicky 2017 davidtrebicky@gmail.com

import os
import argparse
import sys
import requests
import datetime
import json
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning


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
parser.add_argument('--listname', 			nargs='?', 				metavar='filename', 	help='Name of the file which contains list of backed-up files (format: "filename;bytesize;ctime\\n") - default: list.txt', default="list.txt")
parser.add_argument('--dir', 				nargs='?', 				metavar='directory', 	help='Directory where backups are stored - default: ./backup', default=os.path.dirname(sys.argv[0])+"/backup")
parser.add_argument('--icingaserverhost', 	nargs='?', 	type=str, 	metavar='hostname', 	help='Icinga2 API server where the passive check should be processed - default: icinga2.vlp.cz', default="icinga2.vlp.cz")
parser.add_argument('--icingaserverport', 	nargs='?', 	type=str, 	metavar='port', 		help='Icinga2 API server port - default: 5665', default="5665")
parser.add_argument('--icingaserveruser', 	nargs='?', 	type=str, 	metavar='username', 	help='Icinga2 API user (should be user with minimal privileges - not root) - default: root', default="root")
parser.add_argument('--icingaserverpass', 	nargs='?', 	type=str, 	metavar='password', 	help='Icinga2 API password - default: root', default="root")
parser.add_argument('--icingahost', 					type=str, 	metavar='hostname', 	help='Name of the Icinga2 host', default="icinga2.vlp.cz", required=True)
parser.add_argument('--icingaservice', 					type=str, 	metavar='servicename', 	help='Name of the Icinga2 service associated with the icingahost - defuault: MySQLBackup', default="MySQLBackup")
parser.add_argument('--maxage', 			nargs='?',	type=int,	metavar='seconds',		help='Maximum age of backups in seconds - default 30h (108000s)', default=108000)
parser.add_argument('--filenames',			nargs='+',	type=str, 	metavar='filename',	 	help='Filenames to check if present')
parser.add_argument('--verbose', 			help='Increase verbosity level', default=False, action="store_true")

args = parser.parse_args()
exit = 0

# get all dirs newer than args.maxage
new_dirs = []
today = datetime.datetime.today()

if not os.path.isdir(args.dir):
	sys.exit("No directory named " + args.dir)


for root, dirs, files in walklevel(args.dir.rstrip("/"),level=0):
    for name in dirs:
        filedate = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(root, name)))
        if (today - filedate).total_seconds() < args.maxage:
            new_dirs.append(name)

# if no new directories, exit

if (len(new_dirs) == 0):
	sys.exit("No new directories.")

# construct path to all filelists (eg. list.txt) files

lists = []

for directory in new_dirs:
	lists.append(args.dir.rstrip("/") + "/" + directory + "/" + args.listname)

# get all files for checking (from lists.txt files) and their attributes

files = list()

for file in lists:
	try:
		with open(file, "r") as f:
			for line in f:
				item = line.split(";")
				item[0] = os.path.dirname(file) + "/" + item[0]
				item[1] = int(item[1])
				item[2] = float(item[2].rstrip("\n"))
				files.append(item)
	except Exception as exc:
		print (exc, file=sys.stderr)
		sys.exit("Couldn't read file or wrong format.")

# if no files to check, exit

if (len(files) == 0):
	sys.exit("No files to check.")


message = ""

if (args.filenames):
	for name in args.filenames:
		if not any(name in s for s in [item[0] for item in files]): #very very pythonic :D basically if the filenames defined are substrings of any backed-up files (you can omit .tar.gz for example)
			exit = 2
			message += "[CRITICAL] Missing file " + name + "\n"


# check the actual backup files (zatim nebezpecny, potreba ovyjimkovat)

size = 0
maxAge = 0

for file in files:
	name = file[0].replace(os.path.join(args.dir, ''),"")
	if not os.path.isfile(file[0]):
		message += "[CRITICAL] " + name + " is not present on the server but is in the "+ args.listname +"\n"
		continue

	age		= (today - datetime.datetime.fromtimestamp(file[2])).total_seconds()	
	maxAge 	= max(maxAge, age)
	curSize	= os.path.getsize(file[0])
	size	+= curSize

	if curSize == file[1]:

		if (age < args.maxage):
			message+=("[OK] " + name + "; size: " + str(file[1]) + "B; age: " + str(age).split(".",1)[0] + "s\n")	
		
		elif (age < 2*args.maxage):
			message+=("[WARNING] " + name + "; size: " + str(file[1]) + "B; age: " + str(age).split(".",1)[0] + "s (too old)\n")

			if (exit < 2):
				exit = 1

		else:
			message+=("[CRITICAL] " + name + "; size: " + str(file[1]) + "B; age: " + str(age).split(".",1)[0] + "s (too old)\n")
			exit = 2
	else:
		message+=("[CRITICAL] " + name + " size mismatch; " + str(os.path.getsize(file[0])) + "B vs " + str(file[1]) + "B (computed vs written in " + args.listname + ")\n")
		exit = 2

# if verbose is set, print output

if args.verbose:
	print(message)
	print("Oldest file: " + str(maxAge) + "s")
	print("Size of all files: " + str(size)+ "B")

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

payload	= { "exit_status": exit, "plugin_output": message, "performance_data": [ "size="+str(size)+"B", "age="+str(maxAge)+"s" ], "check_source": args.icingahost }
auth 	= HTTPBasicAuth(args.icingaserveruser, args.icingaserverpass)
headers	= {'Accept': 'application/json',}
params 	= (('service', args.icingahost + '!' + args.icingaservice),)
url 	= 'https://' + args.icingaserverhost + ':'+ args.icingaserverport +'/v1/actions/process-check-result'

# sent request to the icinga2 api

r = requests.post(url, data=json.dumps(payload), auth=auth, verify=False, headers=headers, params=params)




