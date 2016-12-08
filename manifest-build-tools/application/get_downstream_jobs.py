#!/usr/bin/env python
# Copyright 2016, DELLEMC, Inc.

'''
Usage:
python get_downstream_jobs.py \
--jenkins_url http://rackhdci.lss.emc.com \
--build_url http://rackhdci.lss.emc.com/job/on-core/851/
'''

import json
import requests
import os
import sys
import argparse
try:
    import common
except ImportError as import_err:
    print import_err
    sys.exit(1)

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('--jenkins-url',
                        required=True,
                        help="The url of the internal jenkins",
                        action="store")
    parser.add_argument('--build-url',
                        required=True,
                        help="the url of the build in jenkins",
                        action="store")
    parser.add_argument('--parameter-file',
                        help="The jenkins parameter file that will be used for Jenkins job",
                        action='store',
                        default="downstream_parameters")

    parsed_args = parser.parse_args(args)
    return parsed_args

def get_build_data(build_url):
    '''
    get the json data of a build
    :param build_url: the url of a build in jenkins
    :return: json data of the build if succeed to get the json data
             None if failed to get the json data
    '''
    r = requests.get(build_url + "/api/json")
    if is_error_response(r):
        print "Failed to get api json of {0}".format(build_url)
        print r.status_code
        return None
    else:
        data = r.json()
        return data

def get_sub_builds(build_url, jenkins_url):
    '''
    get sub builds of a build
    :param build_url: the url of a build in jenkins
    :return: a dictionary which contains key, value: build name= build number of the sub builds
    '''
    build_data = get_build_data(build_url)
    builds = {}
    if build_data:
        if 'subBuilds' in build_data:
            for subBuild in build_data['subBuilds']:
                sub_job_name = subBuild['jobName'] 
                sub_build_number = subBuild['buildNumber']
                sub_build_url = jenkins_url + "/" + subBuild['url']
                builds[sub_job_name] = sub_build_number
                sub_builds = get_sub_builds(sub_build_url, jenkins_url)
                builds.update(sub_builds)

    return builds

def is_error_response(res):
    """
    check the status code of http response
    :param res: http response
    :return: True if the status code less than 200 or larger than 206;
             False if the status code is between 200 and 206
    """
    if res is None:
        return True
    if res.status_code < 200 or res.status_code > 299:
        return True
    return False

def main():
    args = parse_args(sys.argv[1:])
    try:
        sub_builds = get_sub_builds(args.build_url, args.jenkins_url)
        common.write_parameters(args.parameter_file, sub_builds)
    except Exception as e:
        print e
        sys.exit(1)

if __name__ == "__main__":
    main()

