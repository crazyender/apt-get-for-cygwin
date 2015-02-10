#! /usr/bin/env python

# Copyright (C) crazyender

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from optparse import OptionParser
import os
import platform
import hashlib
import sys
import string
import re
import commands
import urllib2
import urllib
from time import time, sleep
import stat

useregrex = False;
setupini_path = ""
cache_path = "/setup"
mirror_path = ""
mirror_name = "";
httpproxy = "";
httpsproxy = "";
# [package] = [package, version, [binurl, size, checksum], [srcurl, srcsize, srcchecksum], required]
mirrorpackages = {}
# [package] = [package, version]
localpackages = {}
dependence_list = []
proxies = {}

config = {
    'MIRROR': "http://mirrors.sohu.com/cygwin/",
    'CACHE': "/setup",
    'HTTP.PROXY' : "",
    'HTTPS.PROXY' : ""
}
unsafe_packages = [
    '_autorebase',
    'cygwin',
    'base-cygwin',
    'cygwin-debuginfo'
];

def parse_apt_get_config():
    pwd = os.getcwd()
    os.chdir(os.environ['HOME'])
    rc = ".aptgetrc"
    if os.path.exists(rc) == False:
        rc = "/etc/aptgetrc"
        if os.path.exists(rc) == False:
            os.chdir(pwd)
            return
    file = open(rc, 'r')
    lines = file.readlines()
    for line in lines:
        if line.startswith("MIRROR:"):
            mirror_path = line.replace("MIRROR:", "").strip()
            if mirror_path.endswith("/") == False:
                mirror_path += "/"
            config['MIRROR'] = mirror_path
        if line.startswith("CACHE:"):
            cache_path = line.replace("CACHE:", "").strip()
            config['CACHE'] = cache_path
        if line.startswith("HTTP.PROXY:"):
            cache_path = line.replace("HTTP.PROXY:", "").strip()
            config['HTTP.PROXY'] = cache_path
        if line.startswith("HTTPS.PROXY:"):
            cache_path = line.replace("HTTPS.PROXY:", "").strip()
            config['HTTPS.PROXY'] = cache_path
    os.chdir(pwd)
            
# run external command, exit if external command fail
# input:  nil
# output: output of external command
def run(command):
    (status, output) = commands.getstatusoutput(command)
    if status != 0:
        print "Error in command " + command + "\n" + output
        exit(status)
    return output

# human readable file size
# input:  size in dec digest
# outout: human readable file size in string
def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB','TB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0

# download url to local path
# input: 
#   @url: remote path
#   @localfile: local path
# output: nil
def wget(url, localfile):
    def get_http_file_size(url):
        length = 0
        try:
            conn = urllib.urlopen(url, proxies=proxies)
            headers = conn.info().headers
            for header in headers:
                if header.find('Length') != -1:
                    length = header.split(':')[-1].strip()
                    length = int(length)
        except Exception, err:
            pass
        return length

    downloadAll = False
    retries = 1
    downloaded = 0
    position = 0
    totalsize = get_http_file_size(url)
    startTime = time()
    print "download " + localfile + ": ",
    while not downloadAll:
        if retries > 10:
            break
        try:
            request = urllib2.Request(url)
            headerrange = (downloaded, totalsize)
            request.add_header('Range', 'bytes=%d-%d' %headerrange)
            conn = urllib2.urlopen(request)
            data = conn.read(1024)
            while data:
                f = open(localfile, 'ab')
                f.write(data)
                f.close()
                downloaded += len(data)
                current = time()
                duration = current - startTime
                if (duration >= 2.0) or (downloaded >= totalsize):
                    startTime = current
                    speed = float(downloaded - position) / float(duration)
                    position = downloaded
                    percent = 100.0 * float(downloaded)/float(totalsize)
                    sys.stdout.write( "\rdownload %s: %3.1f%%\tspeed: %8s/s"%(localfile, percent, sizeof_fmt(speed)) )
                    sys.stdout.flush()      
                data = conn.read(1024)
            downloadAll = True
        except Exception, err:
            print err
            retries += 1
            continue
    print '\n',

# calculate the md5 value
def sumfile(fobj):   
    m = hashlib.md5()
    while True:
        d = fobj.read(8096)
        if not d:
            break
        m.update(d)
    return m.hexdigest()

# md5 wrapper
# input:  file path
# output: md5 value in hex digest
def md5sum(fname):   
    if fname == '-':
        ret = sumfile(sys.stdin)
    else:
        try:
            f = file(fname, 'rb')
        except:
            return 'Failed to open file'
        ret = sumfile(f)
        f.close()
    return ret



# parse the site.ini from mirror and get all package info
def parse_mirror_db():
    package = ""
    version = ""
    binurl = ""
    srcurl=""
    size = 0
    checksum = ""
    srcsize = 0
    srcchecksum = ""
    line = ''
    required = []
    skipversion = False;
    cwd = os.getcwd()
    os.chdir(setupini_path)
    file = open("setup.ini", 'r')
    context = file.read()
    blocks = context.split("\n\n")
    for block in blocks:
        lines = block.split("\n")
        for line in lines:
            if len(line) == 0 :
                continue        
            elif line.startswith("@"): 
                verbs = line.split();
                package = verbs[1]
                skipversion = False
            elif line.startswith("requires:"):
                verbs = line.split()
                verbs.pop(0)
                required = verbs
            elif line.startswith("version:"):
                if skipversion != True:
                    verbs = line.split()
                    version = verbs[1]
            elif line.startswith("install:"):
                if skipversion != True:
                    verbs = line.split()
                    binurl = verbs[1]
                    size = verbs[2]
                    checksum = verbs[3]
            elif line.startswith("source:"):
                if skipversion != True:
                    verbs = line.split()
                    srcurl = verbs[1]
                    srcsize = verbs[2]
                    srcchecksum = verbs[3]
            elif line.startswith("[prev]"):
                skipversion = True;
        if( len(package) != 0 ):
            mirrorpackages[package] = \
                [package, version, [binurl, size, checksum], [srcurl, srcsize, srcchecksum], required]                       
    file.close()
    os.chdir(cwd)
    
# parse installed.db and get all installed package info
def parse_local_db():
    fullname=""
    package=""
    cwd = os.getcwd()
    os.chdir("/etc/setup/")
    if os.path.exists("installed.db") == False:
        run("touch installed.db")
    file = open("installed.db", 'r')
    for line in file.readlines():
        verbs = line.split(' ')
        package = verbs[0]
        fullname = verbs[1]
        version = fullname.replace(package+"-", "")
        version = version.replace(".tar.bz2", "")
        localpackages[package] = [package, version]
    file.close()
    os.chdir(cwd)
        
def parse_database():
    parse_mirror_db()
    parse_local_db()
    
    
    
    
def download_setupini():
    cwd = os.getcwd()
    if os.path.exists(setupini_path) == False:
        os.makedirs(setupini_path)
    os.chdir(setupini_path)
    if os.path.exists("setup.ini"):
        run("rm setup.ini")

    path = mirror_path
    if platform.architecture()[0] == '64bit':
        path += 'x86_64/'
    else:
        path += 'x86/'
    path += "setup.ini"
    wget(path, "setup.ini")
    os.chdir(cwd)
    
# download and unpack package
# input: name of the package
# output: nil
def install_package(package):
    package_param = mirrorpackages[package]
    url = mirror_path+package_param[2][0]
    cwd = os.getcwd()
    os.chdir(setupini_path)
    if os.path.exists("release") == False:
        os.makedirs("release");
    os.chdir("release");
    if os.path.exists(package) == False:
        os.makedirs(package)
    os.chdir(package)
    mirrorurl=package_param[2][0]
    verbs = mirrorurl.split("/")
    localfile=verbs[len(verbs)-1]
    if os.path.exists(localfile) == False:
        wget(url, localfile)
    else:
        # the file already downloaded, but may be wrong
        # give a second chance
        localmd5 = str(md5sum(localfile))
        mirrormd5=package_param[2][2]
        if localmd5 != mirrormd5:
            run("rm " + localfile)
            wget(url, localfile)
            localmd5 = str(md5sum(localfile))
            mirrormd5=package_param[2][2]
            if localmd5 != mirrormd5:
                print "fatal error: " + localfile + " md5 check fail"
                exit(0)
        else:
            print package + " already downloaded"

    # the $package.lst thing is cygwin required
    cmdline = "tar -xvf " + localfile + " -C /"
    output = run(cmdline)
    file = open("/etc/setup/"+package+".lst", "w+")
    file.write(output)
    file.close()
    cmdline = "gzip -f \"/etc/setup/"+package+".lst\" "
    run(cmdline)
    #update local database
    localpackages[package] = [package, package_param[1]]
    
    
def run_postscript():
    pwd = os.getcwd()
    os.chdir("/etc/postinstall/")
    for parent, dirnames, filenames in os.walk("/etc/postinstall/"):
        for file in filenames:
            if file.endswith(".sh"):
                os.chmod(file, stat.S_IEXEC+stat.S_IREAD+stat.S_IWRITE)
                print "run postscript " + file
                run("sh "+file)
                os.rename(file, file+".done")
    os.chdir(pwd)
    
# check all dependence of this package and mark them as install needed
# input:    name of the package
# output:   nil
# modified: dependence_list
def resolve_dependence(package):
    if package in dependence_list:
        return
    mirror_all = mirrorpackages.keys()
    local_all = localpackages.keys()
    if package in mirror_all:
        if package in local_all:
            local_version = localpackages[package][1]
            mirror_version = mirrorpackages[package][1]
            if local_version == mirror_version:
                return
        if package not in unsafe_packages:
            dependence_list.insert(0, package)
            package_param = mirrorpackages[package]
            dependences = package_param[4]
            for dependence in dependences:
                resolve_dependence(dependence)
    else:
        print "can not resolve dependence for " + package + ", exit"
        exit(0)
    

# download and install all packages and their dependence
# input:  list of packages
# output: nil
def download_packages(packages):
    global dependence_list
    dependence_list = []
    for package in packages:
        resolve_dependence(package)
    if len(dependence_list) == 0:
        print "no package will be changed"
    else:
        totalsize=0;
        for package in dependence_list:
            totalsize += string.atoi(mirrorpackages[package][2][1], 10)
        print "following packages will be chaged:"
        packagstr = ""
        for package in packages:
            packagstr += (package + " ")
        print packagstr
        print ""
        print "following additional packages will be installed:"
        packagstr = ""
        for package in dependence_list:
            if (package in packages) == False:
                packagstr += (package + " ")
        print packagstr
        print "total size is " + sizeof_fmt(totalsize)
        ch = raw_input( "do you want to download these packages? (y/n) : ")
        if ch == "y":
            for package in dependence_list:
                install_package(package)
        else:
            exit(0)
    
def update_local_db():
    pwd = os.getcwd()
    os.chdir("/etc/setup/")
    if os.path.exists("installed.db") == True:
        os.rename("installed.db", "installed.sav")
    file = open("installed.db", "w+")
    file.write("INSTALLED.DB 2\n")
    for package in localpackages.keys():
        if package == "INSTALLED.DB":
            continue
        line = package
        line += " " + (package+"-"+localpackages[package][1])+".tar.bz2 0\n"
        file.write(line)
    file.close()

def check_upgrade_packages():
    upgradepackages = []
    for package in localpackages.keys():
        if ( (package in mirrorpackages.keys()) and (localpackages[package][1] != mirrorpackages[package][1])
            and (package not in unsafe_packages)):
            upgradepackages.append(package)
    return upgradepackages

def download_package_source(packages):
    pwd = os.getcwd()
    if os.path.exists("/usr/src") == False:
        os.makedirs("/usr/src")
    os.chdir("/usr/src")
    for package in packages:
        if package in mirrorpackages.keys():
            if os.path.exists(package) == False:
                os.makedirs(package)
            os.chdir(package)
            url = mirror_path+mirrorpackages[package][3][0]
            verbs = url.split("/")
            localfile=verbs[len(verbs)-1]
            wget(url, localfile)
            os.chdir("..")
        else:
            print "no such package"
    os.chdir(pwd)

def find_package(args):
    find_result = []
    for package in args:
        for mirror_package in mirrorpackages.keys():
            if useregrex:
                try:
                    patten = re.compile(package)
                except:
                    print "wrong expression, please use Python style expression"
                    exit(0)
                matches = patten.findall(mirror_package)
                for match in matches:
                    if match == mirror_package:
                        find_result.append(mirror_package)
                        break
            else:
                if mirror_package == package:
                    find_result.append(mirror_package)
    return find_result
                
            
#
#   Main script block
#
parser = OptionParser("apt-get [Options] command")
parser.add_option("-u", "--update",dest="update", default=False, action="store_true", help="update setup.ini before install")
parser.add_option("-m", "--mirror",dest="mirror", default="", help="set the mirror path where we get the packages")
parser.add_option("-c", "--cache",dest="cache", default="", help="set the local cache path")
parser.add_option("-n", "--noscript", dest="noscript", default=False, action="store_true", help="do not run post script file after install")
parser.add_option("-e", "--regrex", dest="regrex", default=False, action="store_true", help="find package using python regrex")
(options, args) = parser.parse_args()
main_arg = args.pop(0)

# parse config file
# first search ~/.aptgetrc
# then search /etc/aptgetrc
parse_apt_get_config()

httpproxy = config['HTTP.PROXY']
httpsproxy = config['HTTPS.PROXY']
if len(httpproxy) != 0:
    proxies['http'] = httpproxy
if  len(httpsproxy) != 0:
    proxies['https'] = httpsproxy

if len(proxies) != 0:
    opener = urllib2.build_opener( urllib2.ProxyHandler(proxies) )
    urllib2.install_opener( opener )

if options.mirror != "":
        str = options.mirror
        if str.endswith("/") == False:
            str += "/"
        config['MIRROR'] = str

if options.cache != "":
    str = options.cache
    config['CACHE'] = str

useregrex = options.regrex

mirror_path = config['MIRROR']
cache_path = config['CACHE']

mirror_name=mirror_path.replace(":", "%3a")
mirror_name=mirror_name.replace("/", "%2f")
setupini_path=cache_path+"/"+mirror_name

if options.update == True:
    download_setupini()
elif main_arg == "update":
    download_setupini()
    exit(0)
else:
    if os.path.exists(setupini_path+"/setup.ini") == False:
        print "setup.ini does not exist, please update first"
        exit(0)


if main_arg == "install":
    parse_database();
    find_result = find_package(args)
    if len(find_result) != 0:
        download_packages(find_result)
        if options.noscript == False:
            run_postscript()
    update_local_db()
    exit(0)
elif main_arg == "upgrade":
    parse_database()
    packs = check_upgrade_packages()
    download_packages(packs)
    if options.noscript == False:
        run_postscript()
    update_local_db()
    exit(0)
elif main_arg == "find" or main_arg == "search":
    parse_database();
    find_result = find_package(args);
    for mirror_package in find_result:
        print mirror_package+"-"+mirrorpackages[mirror_package][1]
    exit(0)
elif main_arg == "source" or main_arg == "src":
    parse_database();
    find_result = find_package(args)
    if len(find_result) != 0:
        download_package_source(find_result)
    exit(0)
elif main_arg == "remove":
    parse_database()
    for arg in args:
        if arg in localpackages.keys():
            del localpackages[arg]
    update_local_db()
else:
    parser.print_help()
    exit(0);