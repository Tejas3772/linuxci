#!/usr/bin/env python3

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: 2017 IBM
# Author: Abdul Haleem <abdhalee@linux.vnet.ibm.com>
#       : Harish <harisrir@linux.vnet.ibm.com>

import os
import json
import re
import logging
import fcntl
import sys
import subprocess
import configparser
import pexpect
import datetime
import time

config_details = configparser.ConfigParser()
config_details.read(os.path.join(os.path.dirname(__file__), 'details.ini'))
repo = config_details.get('Details', 'repo')
autotest_repo = config_details.get('Details', 'autotest_repo')
continue_cmd = config_details.get('Details', 'continue_cmd')
autotest_result = config_details.get('Details', 'autotest_result')
avocado_repo = config_details.get('Details', 'avocado_repo')
avocado_result = config_details.get('Details', 'avocado_result')
avocado_clean = config_details.get('Details', 'avocado_clean')
avocado_test_run = config_details.get('Details', 'avocado_test_run')
base_path = config_details.get('Details', 'base_path')
schedQfile = config_details.get('Details', 'schedQfile')
machineQfile = config_details.get('Details', 'machineQfile')
repo_path = config_details.get('Details', 'repo_path')
hostcopy_path = config_details.get('Details', 'hostcopy_path')
subscribersfile = config_details.get('Details', 'subscribersfile')
scp_timeout = int(config_details.get('Details', 'scp_timeout'))
test_timeout = int(config_details.get('Details', 'test_timeout'))
server = config_details.get('Details', 'server')

# basic required pkgs, without this the run fails
BASEPKG = ['git', 'telnet', 'rpm', 'python', 'flex', 'bison']


def get_output(cmd):
    commit = subprocess.Popen(
        [cmd], stdout=subprocess.PIPE, shell=True).communicate()[0]
    return str (commit).replace('\n', '')


def detect_distro(obj, console):
    release = [
        {'name': 'redhat-release', 'key': 'Red Hat'}, {
            'name': 'SuSE-release', 'key': 'SUSE'},
        {'name': 'os-release', 'key': 'Ubuntu'}, {'name': 'centos-release', 'key': 'CentOS'}, {'name': 'fedora-release', 'key': 'Fedora'}]
    for distro in release:
        cmd = 'if [ -f /etc/%s ] ;then echo Yes;else echo No;fi' % (
            distro['name'])
        status = obj.run_cmd(cmd, console)
        if status[-1] == 'Yes':
            cmd = 'grep -w "%s" /etc/%s > /dev/null 2>&1;echo $?' % (
                distro['key'], distro['name'])
            status = obj.run_cmd(cmd, console)
            if status[-1] == '0':
                return distro['key']
    return None


def install_packages(obj, console):
    # Check repository is set and check and install basic packages
    logging.info('\nCheck for package repository and install basic pkgs\n')
    release = detect_distro(obj, console)
    logging.info(release)
    if 'None' in release:
        logging.info('\nERROR: Unsupported OS !!!')

    if any(re.findall(r'Red Hat|CentOS|Fedora', str(release))):
        status = obj.run_cmd(
            'yum repolist all > /dev/null 2>&1;echo $?', console)
        if status[-1] != '0':
            logging.info('\nERROR: Please set Package repository !!!')
            sys.exit(0)
        BASEPKG.append('openssh-clients')
        tool = 'yum install -y '

    elif 'Ubuntu' in release:
        status = obj.run_cmd(
            'apt-get update > /dev/null 2>&1;echo $?', console)
        if status[-1] != '0':
            logging.info('\nERROR: Please set Package repository !!!')
            sys.exit(0)
        BASEPKG.append('openssh-client')
        tool = 'apt-get install -y '

    elif 'SUSE' in release:
        status = obj.run_cmd('zypper repos > /dev/null 2>&1;echo $?', console)
        if status[-1] != '0':
            logging.info('\nERROR: Please set Package repository !!!')
            sys.exit(0)
        BASEPKG.append('openssh')
        tool = 'zypper install '

    for pkg in BASEPKG:
        if 'openssh' in pkg:
            cmd = 'which scp;echo $?'
        else:
            cmd = 'which %s;echo $?' % (pkg)
        status = obj.run_cmd(cmd, console)
        if status[-1] != '0':
            cmd = tool + pkg + ' > /dev/null 2>&1;echo $?'
            status = obj.run_cmd(cmd, console)
            if status[-1] != '0':
                logging.info('\nERROR: package %s could not install !!!', pkg)
                sys.exit(0)


def add_machineQ(machine):
    while True:
        try:
            with open(machineQfile, 'a') as mQ:
                fcntl.flock(mQ, fcntl.LOCK_EX | fcntl.LOCK_NB)
                mQ.write(machine)
                mQ.write('\n')
                fcntl.flock(mQ, fcntl.LOCK_UN)
                mQ.close()
                if machine in open(machineQfile).read():
                    return True
                return False
        except IOError as ex:
            if ex.errno != errno.EAGAIN:
                raise
        else:
            time.sleep(0.1)


def remove_machineQ(machine):
    lines = []
    while True:
        try:
            with open(machineQfile) as mQ1:
                lines = mQ1.readlines()
                mQ1.close()
            with open(machineQfile, 'w') as mQ2:
                fcntl.flock(mQ2, fcntl.LOCK_EX | fcntl.LOCK_NB)
                for line in lines:
                    if machine != line.strip('\n'):
                        mQ2.write(line)
                fcntl.flock(mQ2, fcntl.LOCK_UN)
                mQ2.close()
                if machine not in open(machineQfile).read():
                    return True
                return False
        except IOError as ex:
            if ex.errno != errno.EAGAIN:
                raise
        else:
            time.sleep(0.1)


def read_json(path):
    if os.path.isfile(path):
        subfile = open(path, 'r')
        json_data = json.load(subfile)
        file_contents = json_data['data']
        return file_contents
    else:
        return []


def scp_to_host(file_path, host_details):
    scp = pexpect.spawn('scp -l 8192 -q -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r ' +
                        file_path + ' ' + host_details['username'] + '@' + host_details['hostname'] + ':/root/')
    res = scp.expect([r'[Pp]assword:', pexpect.EOF])
    if res == 0:
        scp.sendline(host_details['password'])
        logging.info("Copying files to host")
        scp.logfile = sys.stdout
        wait = scp.expect([pexpect.EOF], timeout=scp_timeout)
        if wait == 0:
            logging.info('Files successfully copied')


def append_json(path, json_details):
    file_contents = read_json(path)
    json_data = {}
    with open(path, mode='w') as file_json:
        file_contents.append(json_details)
        json_data['data'] = file_contents
        json.dump(json_data, file_json)


def update_json(path, json_details):
    json_data = {}
    with open(path, mode='w') as file_json:
        json_data['data'] = json_details
        json.dump(json_data, file_json)

def append_diff_json(path,json_details):
    file_contents = read_json(path)
    json_data = {}
    with open(path, mode='w') as file_json:
        file_contents.update(json_details)
        json_data['data'] = file_contents
        json.dump(json_data, file_json)
def tar_name(git, branch):
    git = re.split(".org|.com", git, 1)[1][1:]
    git = git.replace('/', '_')
    return str (git) + '_' + branch


def tar(folder, tar_folder):
    os.chdir(folder)
    if os.path.isdir(tar_folder):  # Handling with proper git name
        print("Tarring " + tar_folder)
        os.system('tar -czf ' + tar_folder +
                  '.tar.gz ' + tar_folder)


def untar(tar_file, dest='.'):
    if os.path.exists(tar_file):
        print("Untarring " + tar_file)
        os.system('tar -xzf ' + tar_file + ' -C ' + dest)


def get_keyvalue(values):
    details = {}
    values = values.split(',')
    for value in values:
        n = re.findall('(.*?)=.*', value)[0]
        x, v = value.split('%s=' % n)
        details[n] = v
    return details


def oneday(cr_date):
    return str((datetime.datetime.strptime(cr_date, '%Y_%m_%d') + datetime.timedelta(days=1)).strftime('%Y_%m_%d'))


def oneweek(cr_date):
    return str((datetime.datetime.strptime(cr_date, '%Y_%m_%d') + datetime.timedelta(days=7)).strftime('%Y_%m_%d'))


def onemonth(cr_date):
    m, y = (cr_date.month + 1) % 12, cr_date.year + \
        ((cr_date.month) + 1 - 1) // 12
    if not m:
        m = 12
    d = min(cr_date.day, [31, 29 if y % 4 == 0 and not y % 400 ==
                          0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1])
    return cr_date.replace(day=d, month=m, year=y).strftime('%Y_%m_%d')


def get_sid_list():
    '''
    Get the list of Subscription ID's from subscription.json
    '''
    sidlist = []
    subfile = read_json(subscribersfile)
    for sid in subfile:
        sidlist.append(sid['SID'])
    return sidlist


def setup_linux_tar(git, sid):
    local_path = get_output('pwd') + '/'
    os.system('rm -rf hostCopy && rm -rf hostCopy.tar.gz')
    tarname = tar_name(git['host_kernel_git'], git['host_kernel_branch'])
    tarfile = "%s.tar.gz" % tarname
    tar_path = os.path.join(hostcopy_path, tarfile)
    rpath = os.path.join(repo_path, tarname)
    hpath = os.path.join(hostcopy_path, tarname)
    if not os.path.exists(tar_path):
        logging.info('Cloning new tar ...')
        logging.info("Fetching %s from branch %s", git[
                     'host_kernel_git'], git['host_kernel_branch'])
        os.system('git clone -b %s %s %s' %
                  (git['host_kernel_branch'], git['host_kernel_git'], rpath))
        os.system('tar -zcf %s.tar.gz %s' % (rpath, rpath))
        if os.path.exists(rpath):
            os.system('rm -rf %s/.git' % rpath)
            os.system('tar -zcf %s.tar.gz %s' % (hpath, rpath))
            os.system('rm -rf %s' % rpath)

    logging.info('Using existing tar ..')
    os.system('tar -zxf %s > /dev/null' % tar_path)
    os.system('mv %s hostCopy' % tarname)
    logging.info('Making a host copy')
    os.system('tar -zcf hostCopy.tar.gz hostCopy')
    os.system('rm -rf hostCopy')

    if sid:
        sid_path = os.path.join(base_path, sid)
        os.system('mv hostCopy.tar.gz %s/' % sid_path)


def bisect(obj, console, hostdetails, git, json_path, good, bad, bisect, disk, details, hmc_flag=False):
    output = []
    tar = tar_name(git['host_kernel_git'], git['host_kernel_branch'])
    local_path = get_output('pwd') + '/'
    tarfile = '%s%s.tar.gz' % (repo_path, tar)
    os.system('rm -rf hostCopy hostCopy.tar.gz %s' % tar)
    obj.run_cmd('cd;rm -rf /root/hostCopy', console)
    obj.run_cmd('chmod +x /root/boot.sh /root/build.sh', console)
    res = obj.run_cmd('ls /root/hostCopy.tar.gz', console)
    if 'No such file or directory' in res[-1]:
        logging.info('COPY TAR TO CLIENT')
        if os.path.exists(tarfile):
            os.system('yes "" | cp %s %s' % (tarfile, local_path))
            os.system('tar -zxf %s> /dev/null' % tarfile)
            logging.info('Making a host copy')
            os.system('yes "" | mv %s hostCopy' % tar)
            os.system('tar -zcf hostCopy.tar.gz hostCopy')
            scp_to_host(local_path + 'hostCopy.tar.gz', hostdetails)
    logging.info("UNTAR HOSTCOPY IN CLIENT")
    out = obj.run_cmd('tar -zxf /root/hostCopy.tar.gz;echo $?', console)
    flag = False
    if '0' not in out[-1]:
        logging.info('COPY FAILED, START CLONE')
        cmd = 'git clone -b %s %s /root/hostCopy' % (
            git['host_kernel_branch'], git['host_kernel_git'])
        res = obj.run_cmd(cmd, console)
        while not flag:
            res = obj.run_cmd('ls /root/hostCopy; echo $?', console)
            if '0' not in res[-1]:
                time.sleep(1)
            else:
                flag = True
    obj.run_cmd("cd /root/hostCopy", console)
    out = obj.run_cmd("git remote -v;echo $?", console)
    if '0' not in out[-1]:
        cmd = "git init && git config --global http.sslverify false"
        obj.run_cmd(cmd, console)
        cmd = "git remote add origin %s" % git['host_kernel_git']
        obj.run_cmd(cmd, console)

    cmd = "git remote update > /dev/null"
    obj.run_cmd(cmd, console)
    cmd = "git fetch --all --tags --prune > /dev/null && git reset origin/%s > /dev/null; git clean -df > /dev/null" % git[
        'host_kernel_branch']
    obj.run_cmd(cmd, console)
    logging.info("COPY .CONFIG TO TAR")
    cmd = "yes "" | cp /root/%s /root/hostCopy/.config" % git['kernel_config']
    obj.run_cmd(cmd, console)
    obj.run_cmd('yes "" | cp /root/boot.sh /root/hostCopy/', console)
    logging.info("GIT BISECT START")
    cmd = "git bisect reset && git bisect start %s %s" % (good, bad)
    output = obj.run_cmd(cmd, console)
    time.sleep(20)
    if 'build' in bisect:
        logging.info("GIT BISECT RUN MAKE")
        cmd = "git bisect run /root/build.sh"
        output = obj.run_cmd(cmd, console)
        if 'first bad commit' in output[-2]:
            logging.info("\nFOUND BAD COMMIT\n")
            badcommit = output[-2].split()
            os.system('git show %s --stat' % badcommit[0])
            os.system('git bisect log')
        if json_path:
            sid_json = read_json(json_path)
            sid_json['LASTBAD'] = badcommit[-1]
            update_json(json_path, sid_json)

    elif 'boot' in bisect:
        gflag = bflag = boot = False
        while True:
            cmd = "cd;cd /root/hostCopy"
            obj.run_cmd(cmd, console)
            if gflag:
                logging.info("GOOD Commit:")
                output = obj.run_cmd('git bisect good', console)
            if bflag:
                logging.info("BAD Commit:")
                output = obj.run_cmd('git bisect bad', console)
            for line in output:
                if 'first bad commit' in line:
                    logging.info("\nFOUND BAD COMMIT\n")
                    badcommit = line.split()
                    cmd = 'git show %s --stat' % badcommit[0]
                    obj.run_cmd(cmd, console)
                    obj.run_cmd('git bisect log', console)

            rc = obj.run_cmd('./boot.sh', console, timeout=2000)
            # TODO: handle intermediate failure / build fails
            # match for exact trace, if other say as GOOD
            # assume GOOD for build failures for now
            state = obj.check_kernel_panic(console)
            if state != 'panic' or 'exit 2' in rc:
                gflag = True
                bflag = False
            else:
                bflag = True
                gflag = False
            try:
                console.send('\r')
                rc = console.expect(
                    ['login:', 'pexpect', pexpect.TIMEOUT], timeout=120)
                if rc == 0:
                    res = console.before
                    res = res.splitlines()
                    console.sendline(hostdetails['username'])
                    rc = console.expect(
                        [r"[Pp]assword:", pexpect.TIMEOUT], timeout=120)
                    time.sleep(5)
                    if rc == 0:
                        console.sendline(hostdetails['password'])
                        rc = console.expect(
                            ["Last login", "incorrect"], timeout=60)
                        if rc == 1:
                            sys.exit(1)
                    console.sendline("PS1=[pexpect]#")
                    rc = console.expect_exact("[pexpect]#")
                    if rc != 0:
                        boot = True
                        break
                elif rc == 2:
                    boot = False
                else:
                    boot = True
                    pass
            except:
                pass
            if boot:
                logging.info("Oops ! Rebooting...")
                if hmc_flag:
                    reb_result = obj.handle_reboot(
                        disk, details['server'], details['lpar'])
                    if reb_result == "Login":
                        logging.info("SYSTEM REBOOTED")
                        time.sleep(20)
                        obj.set_unique_prompt(console)
                else:
                    obj.handle_reboot(disk, host_details)
                    logging.info("REBOOT COMPLETE")
                    obj.set_unique_prompt(
                        console, host_details['username'], host_details['password'])
                    time.sleep(10)
    if json_path:
        logging.info("\nREMOVE MACHINE FROM QUEUE")
        if remove_machineQ(sid_json['BUILDMACHINE']):
            logging.info("\n%s removed from queue\n", sid_json['BUILDMACHINE'])
