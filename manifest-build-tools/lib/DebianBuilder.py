"""
This is a module that contains the tool for python to build/test the
debians after all the directories are checked out based on a given manifest file.
"""
# Copyright 2016, EMC, Inc.

import os
import subprocess
import sys

try:
    from Builder import Builder
    from common import *
except ImportError as import_err:
    print import_err
    sys.exit(1)

class DebianBuilder(object):
    """
    This is a class that builds the packages. 
    It assumes that the repository is cloned successfully and is accessible for the tool.
    """

    def __init__(self, top_level_dir, jobs=1, sudo_creds=None):
        """
        Initializer set up the ArtifactBuilder
        :param top_level_dir: the directory that holds all the cloned
        repositories according to manifest
            example: <top_level_dir>/on-http/...
                                    /on-cli/...
        :return: None
        """
        self.set_repo_directory(top_level_dir)
        self._jobs = jobs
        self._sudo_creds = sudo_creds

    def get_repo_directory(self):
        """
        getter for repository directory
        :return: directory where the repositories are cloned.
        """
        return self._top_level_dir

    def set_repo_directory(self, top_level_dir):
        """
        Setter for the repository directory
        :param top_level_dir: the directory that holds all the cloned
        repositories according to manifest
            example: <top_level_dir>/on-http/...
                                      /on-cli/...
        :return: None
        """
        if os.path.isdir(top_level_dir):
            self._top_level_dir = os.path.abspath(top_level_dir)
        else:
            raise ValueError("The path provided '{dir}' is not a directory."
                             .format(dir=top_level_dir))

    @staticmethod
    def __printable_results(name, build_result):
        """
        Generate complete and summary reports for the given build
        :param build_result:
        :return: tuple of (detailed, summary, errors), printable lines of results along with
                 a numeric error count
        """
        detailed = []
        summary = []
        errors = 0

        detailed.append("=== Results for {0} ===".format(name))
        summary.append("{0}:".format(name))

        if 'command' not in build_result:
            return (detailed, summary, errors)

        for result in build_result['command']:
            result_detailed, result_summary, result_errors = result.generate_report()
            detailed.extend(result_detailed)
            summary.extend(result_summary)
            errors += result_errors

        return (detailed, summary, errors)

    @staticmethod
    def summarize_results(results):
        """
        :param results: returned results from the repository builds
        :return: number of errors found
        """
        build_errors = 0
        all_detailed = []
        all_summary = []

        key_list = results.keys()

        # results is a ProxyDict, not iterable in the for name in results sense
        for name in sorted(key_list):
            
            (detailed, summary, errors) = DebianBuilder.__printable_results(name, results[name])

            all_detailed.extend(detailed)
            all_summary.extend(summary)
            build_errors += errors

        #print "\n\nvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv\n\n"
        #print "Full Details\n"
        #for item in all_detailed:
        #    print item
        #print "\n\n^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n"

        print "Summary:"
        for item in all_summary:
            print item
        print "\n\n"

        return build_errors

    def generate_tasks(self):
        tasks = []
        for repo in os.listdir(self._top_level_dir):
            task = {
                    'name': repo,
                    'data': {
                             'directory': None,
                             'commands': [],
                             'env_file': None
                            }
                   }
            path = os.path.abspath(os.path.join(self._top_level_dir, repo))
            task['data']['directory'] = path

            command = {'command': os.path.join(path, 'HWIMO-BUILD')}
            if self._sudo_creds:
                command['sudo'] = True
                command['credential'] = self._sudo_creds
            task['data']['commands'].append(command)

            version_file = "{0}.version".format(repo)
            version_path = os.path.abspath(os.path.join(path, version_file))
            if os.path.exists(version_path):
                task['data']['env_file'] = version_path
            tasks.append(task)

        return tasks

    def blind_build_all(self):
        """
        Iterate through the first layer subdirectory of top_level_dir and
        if found HWIMO-BUILD or HWIMO-TEST, then execute these two scripts in
        the order of HWIMO-TEST; HWIMO-BUILD.

        It does not check the correctness of the cloned directory. If all the
        HWIMO-BUILD and HWIMO-TEST success, then return true,
        otherwise return false

        Build result example:
        {
        'on-http': {
            'HWIMO-TEST': 'pass'/'fail'/None,
            'HWIMO-BUILD': 'pass'/'fail'/None
            }
        }
        :return: True/False for build success.
        """
        try:
            builder = Builder(self._jobs)

            tasks = self.generate_tasks()
            for task in tasks:
                builder.add_task(task['data'], task['name'])

            builder.finish()
            results = builder.get_results()
            build_errors = DebianBuilder.summarize_results(results)

            if build_errors > 0:
                print "**** ERRORS IN BUILD ****"
                return False
            else:
                print "---- GOOD BUILD ----"
                return True
        except Exception, e:
            raise RuntimeError("Failed to build all debian packages due to {0}".format(e))
