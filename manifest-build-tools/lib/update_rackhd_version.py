# Copyright 2016, EMC, Inc.
"""
A module that contains the tool to update the debian/control
based on debian files under a directory.
It assumes that the repositories under the directory are cloned successfully 
and run the scripts HWIMO-BUILD successfully.
"""
import sys
import os
import deb822

try:
    import common
except ImportError as import_err:
    print import_err
    sys.exit(1)

class RackhdDebianControlUpdater(object):
    def __init__(self, builddir):
        """
        __builddir - Destination for checked out repositories
        :return: None
        """
        self._builddir = builddir
        
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
            debian_files = common.find_specify_type_files(repo_dir, ".deb")
            for debian_file in debian_files:
                package_name = common.get_debian_package(debian_file)
                version = common.get_debian_version(debian_file)
                version_dict[repo] = version

        return version_dict

    def update_RackHD_control(self):
        """
        udpate RackHD/debian/control based on debian files under builddir
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

