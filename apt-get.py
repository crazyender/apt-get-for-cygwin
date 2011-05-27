#! /usr/bin/env python

from optparse import OptionParser
import os
import hashlib
import sys
import string
import re

setupini_path = ""
cache_path = "/setup"
mirror_path = "http://mirrors.163.com/cygwin/"
mirror_name = "";
mirrorpackages = {}
localpackages = {}
dependence_list = []


def sumfile(fobj):   
    m = hashlib.md5()
    while True:
        d = fobj.read(8096)
        if not d:
            break
        m.update(d)
    return m.hexdigest()


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

def sizeof_fmt(num):
    for x in ['bytes','KB','MB','GB','TB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0

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
    for line in file.readlines():
        if len(line) == 0 :
             continue        
        elif line.startswith("@"):
            if( len(package) != 0 ):
                mirrorpackages[package] = [package, version, [binurl, size, checksum], [srcurl, srcsize, srcchecksum], required]   
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
        mirrorpackages[package] = [package, version, [binurl, size, checksum], [srcurl, srcsize, srcchecksum], required]                       
    file.close()
    os.chdir(cwd)
    
def parse_local_db():
    fullname=""
    package=""
    cwd = os.getcwd()
    os.chdir("/etc/setup/")
    if os.path.exists("installed.db") == False:
        os.system("touch installed.db")
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
        os.mkdir(setupini_path)
    os.chdir(setupini_path)
    os.system("rm setup.ini")
    os.system("wget "+mirror_path+"setup.ini")
    os.chdir(cwd)
    
def install_package(package):
    package_param = mirrorpackages[package]
    url = mirror_path+package_param[2][0]
    cwd = os.getcwd()
    os.chdir(setupini_path)
    if os.path.exists("release") == False:
        os.mkdir("release");
    os.chdir("release");
    if os.path.exists(package) == False:
        os.mkdir(package)
    os.chdir(package)
    mirrorurl=package_param[2][0]
    verbs = mirrorurl.split("/")
    localfile=verbs[len(verbs)-1]
    if os.path.exists(localfile):
        print "already downloaded, skip"
    else:
        os.system("wget " + url)
        localmd5 = str(md5sum(localfile))
        mirrormd5=package_param[2][2]
        if localmd5 != mirrormd5:
            print "fatal error: md5 check fail"
            exit(0)
    cmdline = "tar -jxvf " + localfile + " -C / > \"/etc/setup/"+package+".lst\""
    os.system(cmdline)
    #print cmdline
    cmdline = "gzip -f \"/etc/setup/"+package+".lst\" "
    os.system(cmdline)
    #print cmdline

    
    #update local database
    localpackages[package] = [package, package_param[1]]
    
    
def run_postscript():
    pwd = os.getcwd()
    os.chdir("/etc/postinstall/")
    for parent, dirnames, filenames in os.walk("/etc/postinstall/"):
        for file in filenames:
            if file.endswith(".sh"):
                os.system("chmod u+x " + file)
                os.system("./"+file)
                os.rename(file, file+".done")
    os.chdir(pwd)
    
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
                #print "package " + package + " already installed, skip"
                return
        dependence_list.insert(0, package)
        package_param = mirrorpackages[package]
        dependences = package_param[4]
        for dependence in dependences:
            resolve_dependence(dependence)
    else:
        print "can not resolve dependence for " + package + ", exit"
        exit(0)
    
    
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
        for package in dependence_list:
            packagstr += (package + " ")
        print packagstr
        print "total size is " + sizeof_fmt(totalsize)
        ch = raw_input( "do you want to download these packages? (y/n)) : ")
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
        if (package in mirrorpackages.keys()) and (localpackages[package][1] != mirrorpackages[package][1]):
            upgradepackages.append(package)
    return upgradepackages

def download_package_source(packages):
    pwd = os.getcwd()
    if os.path.exists("/usr/src") == False:
        os.mkdir("/usr/src")
    os.chdir("/usr/src")
    for package in packages:
        if package in mirrorpackages.keys():
            if os.path.exists(package) == False:
                os.mkdir(package)
            os.chdir(package)
            url = mirror_path+mirrorpackages[package][3][0]
            os.system("wget -nc "+url)
            os.chdir("..")
        else:
            print "no such package"
    os.chdir(pwd)
            

parser = OptionParser()
parser.add_option("-u", "--update",dest="update", default=False, action="store_true", help="update setup.ini before install")
parser.add_option("-m", "--mirror",dest="mirror", help="set the mirror path where we get the packages")
parser.add_option("-c", "--cache",dest="cache", help="set the local cache path")
parser.add_option("-f", "--file",dest="file", help="rename the package with FILE")
parser.add_option("-n", "--noscript", dest="noscript", default=False, action="store_true", help="do not run post script file after install")
(options, args) = parser.parse_args()
main_arg = args.pop(0)

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
    download_packages(args)
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
elif main_arg == "find":
    parse_database();
    for package in args:
        for mirror_package in mirrorpackages.keys():
            try:
                patten = re.compile(package)
            except:
                print "wrong expression, please use Python style expression"
                exit(0)
            match = patten.match(mirror_package)
            if match:
                print mirror_package+"-"+mirrorpackages[mirror_package][1]
    exit(0)
elif main_arg == "source":
    parse_database();
    download_package_source(args)
    exit(0)
elif main_arg == "remove":
    parse_database()
    for arg in args:
        if arg in localpackages.keys():
            del localpackages[arg]
    update_local_db()
else:
    usage();
    exit(0);
    
    

    
