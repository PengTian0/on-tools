#!/usr/bin/env python

"""
This is a command line program that makes a rackhd release to bintray.

This program first build debian packages for repositories which has changes.
Then it will download packages for repositories which has no change and update their version.
If all the debian packages are built successfully, it will uploads all the packages to bintray.
Exit code will be 0 on success, something else on failures.

./on-tools/manifest-build-tools/HWIMO-BUILD on-tools/manifest-build-tools/application/make-debian-release.py \
--build-directory b/ \
--manifest-name rackhd-devel \
--manifest-repo build-manifests/ \
--manifest-branch master \
--manifest-commit-id HEAD\
--git-credential https://github.com,GITHUB \
--updated-repo on-core  \
--jobs 8 \
--is-official-release \
--parameter-file downstream-files \
--debian-depth 3

The required parameters:
build-directory: A directory where all the repositories are cloned to. 
manifest-name: The name of a manifest file. All the repositories are cloned according to the manifest file.
manifest-repo: The directory of manifest repository
git-credential: Git URL and credential for CI services: <URL>,<Credentials>

The optional parameters:
manifest-branch: The branch of manifest repository, the default value is master.
manifest-commit-id: The commit id of manifest repository, the default value is HEAD.
updated-repo: The name of updated repository. The manifest file is updated with the repository.
jobs: Number of parallel jobs(build debian packages) to run. 
      The number is related to the compute architecture, multi-core processors..
is-official-release: If true, this release is official, the default value is false
parameter-file: The file with parameters. The file will be passed to downstream jobs.
debian-depth: The depth in top level directory that you want this program look into to find debians.

"""

# Copyright 2016, EMC, Inc.

import argparse
import os
import sys
import traceback

try:
    from common import *
except ImportError as import_err:
    print import_err
    sys.exit(1)

class Bintray(object):
    def __init__(self, creds, subject, repo, push_executable, **kwargs):
        self._username, self._api_key = parse_credential_variable(creds)
        self._subject = subject
        self._repo = repo
        self._push_executable = push_executable
        self._component = None
        self._distribution = None
        self._architecture = None
        for key, value in kwargs.items():
            setattr(self, key, value)

    def upload_a_file(self, package, version, file_path):
        cmd_args = [self._push_executable]
        cmd_args += ["--user", self._username]
        cmd_args += ["--api_key", self._api_key]
        cmd_args += ["--subject", self._subject]
        cmd_args += ["--repo", self._repo]
        cmd_args += ["--package", package]
        cmd_args += ["--version", version]
        cmd_args += ["--file_path", file_path]

        if self._component:
            cmd_args += ["--component", self._component]
        if self._distribution:
            cmd_args += ["--distribution", self._distribution]
        if self._architecture:
            cmd_args += ["--architecture", self._architecture]

        cmd_args += ["--package", package]
        cmd_args += ["--version", version]
        cmd_args += ["--file_path", file_path]

        try:
            proc = subprocess.Popen(cmd_args,
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    shell=False)
            (out, err) = proc.communicate()
            if proc.returncode != 0:
                raise RuntimeError(err)
        except subprocess.CalledProcessError as ex:
            raise RuntimeError("Failed to upload file {0} due to {1}".format(file_path, ex))

        return True

def parse_args(args):
    """
    Parse script arguments.
    :return: Parsed args for assignment
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-directory',
                        required=True,
                        help="Top level directory that stores all the cloned repositories.",
                        action='store')

    parser.add_argument('--debian-depth',
                        help="The depth in top level directory that you want"
                             " this program look into to find debians.",
                        default=3,
                        type=int,
                        action='store')

    parser.add_argument('--bintray-credential',
                        required=True,
                        help="bintray credential for CI services: <Credentials>",
                        action='store')

    parser.add_argument('--bintray-subject',
                        required=True,
                        help="the Bintray subject, which is either a user or an organization",
                        action='store')

    parser.add_argument('--bintray-repo',
                        required=True,
                        help="the Bintary repository name",
                        action='store')

    parser.add_argument('--bintray-component',
                        help="such as: main",
                        action='store',
                        default='main')

    parser.add_argument('--bintray-distribution',
                        help="such as: trusty, xenial",
                        action='store',
                        default='trusty')

    parser.add_argument('--bintray-architecture',
                        help="such as: amd64, i386",
                        action='store',
                        default='amd64')

    parsed_args = parser.parse_args(args)
    return parsed_args

def get_debian_version(file_path):
    cmd_args = ["dpkg-deb", "-f", file_path, "Version"]
    proc = subprocess.Popen(cmd_args,
                            stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            shell=False)
    (out, err) = proc.communicate()
    if proc.returncode == 0:
        return out.strip()
    else:
        raise RuntimeError("Failed to parse version of {0} due to {1}".format(file_path, err))

def do_a_repo(repo_dir, debian_depth, bintray):
    """
    upload all the debians under top level dir to bintray
    :param top_devel_dir: 
    :param debian_depth:
    :param bintray: A dictionary which contains bintray username,
                    api key, subject, repository, component, distribution, architecture
    """
    return_is_success = True
    return_dict_detail = {}
    has_deb = False
    package = os.path.basename(repo_dir)
    top_dir_depth = repo_dir.count(os.path.sep) #How deep is at starting point
    for root, dirs, files in os.walk(repo_dir, topdown=True):
        root_depth = root.count(os.path.sep)
        if (root_depth - top_dir_depth) <= debian_depth:
            for file_itr in files:
                if file_itr.endswith(".deb"):
                    has_deb = True
                    abs_file = os.path.abspath(os.path.join(root, file_itr))
                    file_name = os.path.basename(file_itr)
                    version = get_debian_version(abs_file)
                    upload_result = bintray.upload_a_file(package, version, abs_file)
                    if upload_result:
                        return_dict_detail[file_name] = "Success"
                    else:
                        return_dict_detail[file_name] = "Fail"
                        return_is_success = False
        else:
            dirs = [] # Stop iteration

    if not has_deb:
        print "No debians found under {dir}".format(dir=repo_dir)

    return return_is_success, return_dict_detail


def main():
    """
    Build all the debians, create the repository and upload all the artifacts.
    Exit on encountering any error.
    :return:
    """
    args = parse_args(sys.argv[1:])
    push_script_path = "/home/onrack/rackhd/release/MBU/on-tools/manifest-build-tools/pushToBintray.sh"
    try:
        bintray = Bintray(args.bintray_credential, args.bintray_subject, args.bintray_repo, push_script_path, component=args.bintray_component, distribution=args.bintray_distribution, architecture=args.bintray_architecture)
        
        for repo in os.listdir(args.build_directory):
            repo_dir = os.path.join(args.build_directory, repo)
            do_a_repo(repo_dir, args.debian_depth, bintray)    

    except Exception, e:
        traceback.print_exc()
        print "Failed to build and upload debian packages due to {0}".format(e)
        sys.exit(1)

if __name__ == '__main__':
    main()
