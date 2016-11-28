#!/usr/bin/env python
# Copyright 2016, DELLEMC, Inc.

"""
This is a command line program that makes a rackhd release to bintray.
This program build debian packages for repositories 
which checked out based on the given manifest file.

Usage:
./on-tools/manifest-build-tools/HWIMO-BUILD on-tools/manifest-build-tools/application/make-debian-release.py \
--build-directory b/ \
--manifest-name rackhd-devel \
--manifest-repo build-manifests/ \
--git-credential https://github.com,GITHUB \
--jobs 8 \
--is-official-release \
--parameter-file downstream-files \
--force \
--sudo-credential

The required parameters:
build-directory: A directory where all the repositories are cloned to. 
manifest-name: The name of a manifest file. 
               All the repositories are cloned based on the manifest file.
manifest-repo: The directory of manifest repository
git-credential: Git URL and credential for CI services: <URL>,<Credentials>

The optional parameters:
is-official-release: If true, this release is official, the default value is false
parameter-file: The file with parameters. The file will be passed to downstream jobs.
force: Use destination directory, even if it exists.
sudo-credential: The environment variable name of sudo credentials.
                 For example: SUDO_CRED=username:password
jobs: Number of parallel jobs(build debian packages) to run.
      The number is related to the compute architecture, multi-core processors..
force:
"""

import argparse
import os
import sys
import json
import traceback

try:
    from reprove import ManifestActions
    from update_rackhd_version import RackhdDebianControlUpdater
    from version_generator import VersionGenerator
    from DebianBuilder import DebianBuilder
except ImportError as import_err:
    print import_err
    sys.exit(1)

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

    parser.add_argument('--manifest-repo',
                        required=True,
                        help="The directory of the checked out manifest repository",
                        action='store')

    parser.add_argument('--manifest-name',
                        required=True,
                        help="The name of manifest file",
                        action='store')

    parser.add_argument('--parameter-file',
                        help="The jenkins parameter file that will used for succeeding Jenkins job",
                        action='store',
                        default="downstream_parameters")

    parser.add_argument('--git-credential',
                        required=True,
                        help="Git URL and credential for CI services: <URL>,<Credentials>",
                        action='append',
                        default=None)

    parser.add_argument('--sudo-credential',
                        help="username:password pair for sudo user",
                        action='store',
                        default=None)

    parser.add_argument('--jobs',
                        help="Number of build jobs to run in parallel",
                        default=-1,
                        type=int,
                        action="store")

    parser.add_argument('--is-official-release',
                        help="True if this release is official",
                        action="store_true")

    parser.add_argument('--force',
                        help="",
                        action="store_true")

    parsed_args = parser.parse_args(args)
    return parsed_args

def update_rackhd_control(top_level_dir, manifest_repo_dir, is_official_release=False):
    updater = RackhdDebianControlUpdater(manifest_repo_dir, top_level_dir, is_official_release=is_official_release)
    updater.update_RackHD_control()

def generate_version_file(top_level_dir, manifest_repo_dir, is_official_release=False):
    for repo in os.listdir(top_level_dir):
        repo_dir = os.path.join(top_level_dir, repo)
        version_generator = VersionGenerator(repo_dir, manifest_repo_dir)
        version = version_generator.generate_package_version(is_official_release)
        if version != None:
            params = {}
            params['PKG_VERSION'] = version
            version_file = "{0}.version".format(repo)
            version_path = os.path.join(repo_dir, version_file)
            write_parameters(version_path, params)

def run_build_scripts(top_level_dir, repos, jobs=1, sudo_creds=None):
    """
    Go into the directory provided and run all the building scripts.
    :param top_level_dir: Top level directory that stores all the
                          cloned repositories.
    :param repos: A list of repositories to be build
    :param jobs: Number of parallel jobs(build debian packages) to run.
    :param sudo_creds: the environment variable name of sudo credentials.
                       for example: SUDO_CRED=username:password
    :return:
        exit on failures
        None on success.
    """
    try:
        builder = DebianBuilder(top_level_dir, repos, jobs=jobs, sudo_creds=sudo_creds)
        builder.blind_build_all()
        builder.print_summary_report()

        result = builder.get_build_result()
        if result:
            print "Debian building is finished successfully."
        else:
            builder.print_detailed_report()
            print "Error found during debian building. cannot continue."
            sys.exit(2)
    except Exception, e:
        sys.exit(1)

def get_build_repos(directory):
    """
    :param directory: Directory that stores all the cloned repositories.
    :return: a list which contains the name of repositories under the directory
    """
    repos = []
    for filename in os.listdir(directory):
        repos.append(filename)
    return repos

def checkout_repos(manifest, builddir, force, git_credential, jobs):
    manifest_actions = ManifestActions(manifest, builddir, force=force, git_credentials=git_credential, jobs=jobs, actions=["checkout", "packagerefs"])
    manifest_actions.execute_actions()
    
def build_debian_packages(build_directory, jobs, manifest_repo, is_official_release, sudo_creds):
    """
    Build debian packages
    """
    # Update the debian/control of rackhd to depends on specified version of component of raqkhd
    update_rackhd_control(build_directory, manifest_repo, is_official_release=is_official_release)
    # Generate a file which contains the version of repository 
    generate_version_file(build_directory, manifest_repo, is_official_release=is_official_release)
    repos = get_build_repos(build_directory)
    # Run HWIMO-BUILD script under each repository to build debian packages
    run_build_scripts(build_directory, repos, jobs=jobs, sudo_creds=sudo_creds)

def write_parameters(filename, params):
    """
    Add/append downstream parameter (java variable value pair) to the given parameter file. 
    If the file does not exist, then create the file.
    :param filename: The parameter file that will be used for making environment
                     variable for downstream job.
    :param params: the parameters dictionary
    :return:
            None on success
            Raise any error if there is any
    """
    if filename is None:
        return

    with open(filename, 'w') as fp:
        try:
            for key in params:
                entry = "{key}={value}\n".format(key=key, value=params[key])
                fp.write(entry)
        except IOError:
            print "Unable to write parameter(s) for next step(s), exit"
            sys.exit(2)

def main():
    """
    Build all the debians.
    Exit on encountering any error.
    """
    args = parse_args(sys.argv[1:])
    
    try:
        manifest_path = os.path.join(args.manifest_repo, args.manifest_name)
        checkout_repos(manifest_path, args.build_directory, args.force, args.git_credential, args.jobs)
        build_debian_packages(args.build_directory, args.jobs, args.manifest_repo, args.is_official_release, args.sudo_credential)
        #upload_debian_packages()
    except Exception, e:
        traceback.print_exc()
        print "Failed to build debian packages due to {0}".format(e)
        sys.exit(1)

if __name__ == '__main__':
    main()
