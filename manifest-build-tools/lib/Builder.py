"""
This is a module that contains the tool for python to build/test the
debians after all the directories are checked out based on a given manifest file.
"""
# Copyright 2016, EMC, Inc.

import os
import subprocess
import sys
import traceback

try:
    from ParallelTasks import ParallelTasks
    from common import *
except ImportError as import_err:
    print import_err
    sys.exit(1)

class BuildResult(object):
    """
    Complete output from the running of a build command on a given host.

    Contains the command that was supposed to be run, whether it was present ot not,
    the return code, and the standard output and standard error text.
    """
    def __init__(self, command, present, return_code=None, stdout=None, stderr=None):
        self.__command = command
        self.__present = present

        self.__return_code = return_code
        self.__stdout = stdout
        self.__stderr = stderr

    def generate_report(self):
        detailed = []
        summary = []
        errors = 0

        short_command = os.path.basename(self.__command)
        if self.__present is True:
            if self.__return_code is not None:
                if self.__return_code == 0:
                    status = "GOOD"
                else:
                    status = "ERROR {0}".format(self.__return_code)
            else:
                status = "RETURN CODE IS NONE"

            detailed.append(self.__command)
            if self.__return_code != 0:
                detailed.append("  ERROR: returned {0}".format(self.__return_code))
                errors = 1
                if self.__stdout != "": 
                    detailed.append(self.__stdout)
                if self.__stderr != "":
                    detailed.append(self.__stderr)
        else:
            status = " Not present"
        summary.append("    {0}: {1}".format(short_command, status))

        return (detailed, summary, errors)

class Builder(ParallelTasks):
    """
    Run a list of command under a directory.

    This class is intended for use with ParallelTasks, and each commands list may be done
    in a separate process.

    """
    def add_task(self, data, name=None):
        """
        Add a task to task queue

        :param data: A dictonary which should contain:
                     directory: The command will be run under the directory
                     commands: A list of comamnds dictionary, for example:
                               {
                                   "command_name": xxx
                               }
        :param name: The key by which the job results will be returned
        :return: None
        """
        if data is not None and 'directory' in data and 'commands' in data:
            if name is None:
                name = os.path.basename(data['directory'])
        else:
            raise ValueError("no directory and/or commands entry in data: {0}".format(data))

        if not os.path.isdir(data['directory']):
            raise ValueError("Path '{0}' is not a directory".format(data['directory']))
        super(Builder, self).add_task(data, name)

    @staticmethod
    def __write_output_to_file(data, filename):
        """
        Save the given data to the specified filename

        :param data: arbitrary data (will not be written if None or empty)
        :param filename: the path to save the data into
        """
        if data is not None and data != "":
            with open(filename, "w") as output_file:
                output_file.write(data)

    def __parse_credential_variable(varname):
        """
        Get the specified variable name from the environment and split it into username,password
        :param varname: environment variable name
        :return: username, password tuple
        """
        credential = os.environ[varname]
        (username, password) = credential.split(':', 2)
        return username, password

    def run_command(self, command, arguments=None, sudo=False, sudo_creds=None):
        """
        Run a named command script in the repository, capturing all of the results for
        future analysis.   If the command script does not exist, it won't run.   That's
        not necessarily an error, just noted as present=False.

        :param command_name: may exist in the repository
        :return: a BuildResult object
        """
        commandline = []

        print "command:"
        print command
        if which(command) is None:
            print "command {0} is not found".format(command)
            # no command present, so we record that
            return BuildResult(command, present=False)

        if sudo:
            print "11111111111111"
            print "sudo_creds:"
            print sudo_creds
            (username, password) = self.__parse_credential_variable(sudo_creds)
            print username
            print password
            commandline += ["echo"]
            commandline += [password]
            commandline += ["|sudo -S"]

        commandline += [command]
        if arguments:
            commandline += arguments

        print "Execute command: {0}".format(commandline)
        try:
            proc = subprocess.Popen(commandline,
                                    stderr=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    shell=False)
            (out, err) = proc.communicate()
        except subprocess.CalledProcessError as ex:
            # this is a terrible failure, not just process exit != 0
            return BuildResult(command,
                               present=True,
                               return_code=ex.returncode)

        # we've exited the process correctly, and captured the output
        # so save the output to files and then proceed
        try:
            self.__write_output_to_file(out, "{0}-output.log".format(command))
            self.__write_output_to_file(err, "{0}-errors.log".format(command))
        except IOError as ex:
            print "Error saving log data: {0}".format(ex)
            proc.returncode += 256

        result = BuildResult(command,
                             present=True,
                             return_code=proc.returncode,
                             stdout=out,
                             stderr=err)
        return result

    def do_one_task(self, name, data, results):
        """
        Perform the work of doing a build in a checked out repository
        name and data will come from the values passed in to add_task()
        :param name:
        :param data: it should contain:
                     'directory': the directory of repository 
                     'script': the script to be run
                     'arguments': the arguments for the script. The field is optional.
        :param results: a list of instances of BuildResult
        :return: None
        """
        if name is None or data is None:
            raise ValueError("name and/or data not present")

        for key in ['directory', 'commands']:
            if key not in data:
                raise ValueError("{0} key missing from data: {1}".format(key, data))

        try:
            print "building in {0}....".format(data['directory'])

            os.chdir(data['directory'])
            if 'env_file' in data and data['env_file'] is not None:
                props = parse_property_file(data['env_file'])
                if props:
                    for item in props.items():
                        key = item[0]
                        value = item[1]    
                        os.environ[key] = value
            for command in data['commands']:
                if 'command' not in command:
                    raise ValueError("command key missing from commands: {0}".format(command))

                arguments = None
                if 'arguments' in command:
                    arguments = command['arguments']

                sudo = False
                sudo_creds = None
                if 'sudo' in command and command['sudo'] == True:
                    if 'credential' not in command or command['credential'] is None:
                        raise RuntimeError("credential key missing from commands {0}".format(command))
                    sudo = True
                    sudo_creds = command['credential']

                build_result = self.run_command(command['command'], arguments=arguments, sudo=sudo, sudo_creds=sudo_creds)

                if build_result is not None:
                    if 'command' not in results:
                        results['command'] = []
                    results['command'].append(build_result)

        except Exception, e:
            trackback.print_exec()
            print "Failed to do task {0} due to {1}".format(name, e)
            raise RuntimeError("Failed to do task {0} due to {1}".format(name, e))
            
