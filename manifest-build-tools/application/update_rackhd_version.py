#!/usr/bin/env python

"""
usage:
./manifest-build-tools/HWIMO-BUILD manifest-build-tools/application/update_rackhd_version.py \
--manifest-repo-url https://github.com/PengTian0/build-manifests \
--manifest-name rackhd-devel \
--builddir b \
--git-credential https://github.com/PengTian0,GITHUB \
--force

The parameters to this script:
manifest-repo-url: the url of manifest repository
manifest-repo-commit: the commit of repository manifest
manifest-name: the filename of manifest
builddir: the destination for checked out repositories
version-file: the version file used to save the version of rackhd
force: use destination directory, even if it exists
git-credential: url, credentials pair for the access to github repos
is-official-release: if true, this release is official, the default value is false
                     
The required parameters:
manifest-repo-url
manifest-name
builddir
git-credential
"""
import argparse
import sys
import os
import shutil
from RepositoryOperator import RepoOperator
from reprove import ManifestActions
from version_generator import VersionGenerator
from common import *

import deb822
import subprocess

class UpdateRackhdVersion(object):
    def __init__(self, manifest_dir, builddir):
        """
        __git_credential - url, credentials pair for the access to github repos
        __manifest_repo_dir - The directory of Repository manifest
        __builddir - Destination for checked out repositories
        __is_official_release - True if the official is official release
        :return:
        """
        self._git_credentials = None
        self._builddir = builddir
        self._manifest_repo_dir = manifest_dir       
        self._is_official_release = False

        self.repo_operator = RepoOperator()
        
    def set_git_credentials(self, git_credential):
        """
        Standard setter for git_credentials
        :return: None
        """
        self._git_credentials = git_credential
        self.repo_operator.setup_gitbit(credentials=self._git_credentials)

    def set_is_official_release(self, is_official_release):
        """
        Standard setter for is_official_release
        :return: None
        """
        self._is_official_release = is_official_release

    def _get_control_depends(self, control_path):
        """
        Parse debian control file
        :param control_path: the path of control file
        :return: a dictionay which contains all the package in field Depends
        """
        if not os.path.isfile(control_path):
            raise RuntimeError("Can't parse {0} because it is not a file".format(control))

        for paragraph in deb822.Deb822.iter_paragraphs(open(control_path)):
            for item in paragraph.items():
                if item[0] == 'Depends':
                    packages = item[1].split("\n")
                    return packages
        return None

    def _update_dependency(self, debian_dir, version_dict):
        """
        update the dependency version of RackHD/debian/control
        :param: debian_dir: the directory of RackHD/debian
        :param: version_dict: a dictionay which includes the version of on-xxx
        :return: None
        """
        control = os.path.join(debian_dir, "control")
        print "1111111111111111111"
        print control
        print version_dict
        if not os.path.isfile(control):
            raise RuntimeError("Can't update dependency of {0} because it is not a file".format(control))

        new_control = os.path.join(debian_dir, "control_new")
        new_control_fp = open(new_control , "wb")

        packages = self._get_control_depends(control)

        with open(control) as fp:
            package_count = 0
            is_depends = False
            for line in fp:
                if line.startswith('Depends'):
                    package_count += 1
                    is_depends = True
                    new_control_fp.write("Depends: ")
                    # Start to write the dependes
                    # If the depends is on-xxx, it will be replace with on-xxx (= 1.1...)
                    for package in packages:
                        package_name = package.split(',',)[0].strip()
                        if ' ' in package_name:
                            package_name = package_name.split(' ')[0]
                        if package_name in version_dict:
                            if ',' in package:
                                depends_str = "         {0} (= {1}),{2}".format(package_name, version_dict[package_name], os.linesep)
                            else:
                                depends_str = "         {0} (= {1}){2}".format(package_name, version_dict[package_name], os.linesep)
                            new_control_fp.write(depends_str)
                        else:
                            new_control_fp.write("{0}{1}".format(package, os.linesep))
                else:
                    if not is_depends or package_count >= len(packages):
                        new_control_fp.write(line)
                    else:
                        package_count += 1

        new_control_fp.close()
        os.remove(control)
        os.rename(new_control, control)

    def _generate_version_dict(self):
        """
        generate a dictory which includes the version of package on-xxx
        :return: a dictory
        """
        version_dict = {}
        for repo in os.listdir(self._builddir):
            repo_dir = os.path.join(self._builddir, repo)
            version_generator = VersionGenerator(repo_dir, self._manifest_repo_dir)
            version = version_generator.generate_package_version(self._is_official_release)
            if version != None:
                version_dict[repo] = version

        return version_dict

    def update_RackHD_control(self):
        """
        udpate RackHD/debian/control according to manifest
        :return: None     
        """
        try:
            rackhd_dir = os.path.join(self._builddir, "RackHD")
            debian_dir = os.path.join(rackhd_dir, "debian")
            version_dict = self._generate_version_dict()
            self._update_dependency(debian_dir, version_dict)
        except Exception, e:
            print "Failed to update RackHD/debian/control due to {0}".format(e)
            sys.exit(1)

        
def parse_command_line(args):
    """
    Parse script arguments.
    :return: Parsed args for assignment
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-repo-dir",
                        required=True,
                        help="the url of repository manifest",
                        action="store")
    
    parser.add_argument("--builddir",
                        required=True,
                        help="destination for checked out repositories",
                        action="store")

    parser.add_argument("--git-credential",
                        required=True,
                        help="Git credentials for CI services",
                        action="append")

    parser.add_argument("--is-official-release",
                        default=False,
                        help="whether this release is official",
                        action="store_true")

    parsed_args = parser.parse_args(args)
    return parsed_args

def main():
    # Parse arguments
    args = parse_command_line(sys.argv[1:])

    # Start to initial an instance of UpdateRackhdVersion
    updater = UpdateRackhdVersion(args.manifest_repo_dir, args.builddir)

    if args.is_official_release:
        updater.set_is_official_release(args.is_official_release)

    if args.git_credential:
        updater.set_git_credentials(args.git_credential)

    # Update the RackHD/debian/control according to manifest
    updater.update_RackHD_control()


if __name__ == "__main__":
    main()
    sys.exit(0)
