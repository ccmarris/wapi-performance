#!/usr/bin/env python3
#vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
'''

 Description:

    Import CSV File for Infoblox NIOS and perform appropriate action.
    Allows for the monitoring of the CSV job progress.

 Requirements:
   Python 3.6+

 Author: Chris Marrison

 Date Last Updated: 20201118

 Todo:

 Copyright (c) 2020 Chris Marrison / Infoblox

 Redistribution and use in source and binary forms,
 with or without modification, are permitted provided
 that the following conditions are met:

 1. Redistributions of source code must retain the above copyright
 notice, this list of conditions and the following disclaimer.

 2. Redistributions in binary form must reproduce the above copyright
 notice, this list of conditions and the following disclaimer in the
 documentation and/or other materials provided with the distribution.

 THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 POSSIBILITY OF SUCH DAMAGE.

'''
__version__ = '0.0.1'
__author__ = 'Chris Marrison'
__author_email__ = 'chris@infoblox.com'

import logging
import os
import sys
import requests
import argparse
import configparser
import datetime
import time


def parseargs():
    '''
    Parse Arguments Using argparse

    Parameters:
        None

    Returns:
        Returns parsed arguments
    '''
    parse = argparse.ArgumentParser(description='Test Object creation in NIOS')
    parse.add_argument('-c', '--config', type=str, default='gm.ini',
                        help="Override ini file")
    parse.add_argument('-r', '--record_type', type=str, default="host",
                        help="Specify Object Type [host, a, cname, zone]")
    parse.add_argument('-z', '--basezone', type=str, default="test.poc",
                        help="Specify Object Type [host, a, cname, zone]")
    parse.add_argument('-n', '--number', type=int, default=1,
                        help="Number of Objects to create")
    parse.add_argument('-d', '--debug', action='store_true', 
                        help="Enable debug messages")

    return parse.parse_args()


def read_ini(ini_filename):
    '''
    Open and parse ini file

    Parameters:
        ini_filename (str): name of inifile

    Returns:
        config :(dict): Dictionary of BloxOne configuration elements

    '''
    # Local Variables
    cfg = configparser.ConfigParser()
    config = {}
    ini_keys = ['gm', 'version', 'valid_cert', 'user', 'pass', 'sleep']

    # Attempt to read api_key from ini file
    try:
        cfg.read(ini_filename)
    except configparser.Error as err:
        logging.error(err)

    # Look for NIOS section
    if 'NIOS' in cfg:
        for key in ini_keys:
            # Check for key in BloxOne section
            if key in cfg['NIOS']:
                config[key] = cfg['NIOS'][key].strip("'\"")
                logging.debug('Key {} found in {}: {}'.format(key, ini_filename, config[key]))
            else:
                logging.warning('Key {} not found in NIOS section.'.format(key))
                config[key] = ''
    else:
        logging.warning('No BloxOne Section in config file: {}'.format(ini_filename))
        config['api_key'] = ''

    return config


def check_csv_status(config, csvjob):
    '''
    Check status of CSV import
    '''
    status = 'PENDING'
    sleep = int(config['sleep'])
    stop_monitor = ['COMPLETED', 'FAILED', 'STOPPED']

    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['version'] + '/' + csvjob )

    if config['valid_cert'] == 'true':
        valid_cert = True
    else:
        valid_cert = False

    # Avoid error due to a self-signed cert.
    if not valid_cert:
        requests.packages.urllib3.disable_warnings()
    
    wapi_session = requests.session()
    wapi_session.auth = (config['user'], config['pass'])
    wapi_session.verify = valid_cert

    while status not in stop_monitor:
        response = wapi_session.get(url)
        result = response.json()
        if response.status_code == requests.codes.ok:
            status = result['status']
        else:
            status = 'WAPI_ERROR'
        print('Status: {}    Processed: {} lines'
             .format(status, result['lines_processed']), end='\r', flush=True)
        if status not in stop_monitor:
            time.sleep(sleep)

    start_time = datetime.datetime.fromtimestamp(result['start_time'])
    end_time = datetime.datetime.fromtimestamp(result['end_time'])
    run_time = end_time - start_time
    lines_success = int(result['lines_processed']) - int(result['lines_failed'])

    return status


def create_hosts(config, base_zone, n):
    '''
    '''
    time = 0
    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['version'] + '/record:host' )

    if config['valid_cert'] == 'true':
        valid_cert = True
    else:
        valid_cert = False

    # Avoid error due to a self-signed cert.
    if not valid_cert:
        requests.packages.urllib3.disable_warnings()
    
    wapi_session = requests.session()
    wapi_session.auth = (config['user'], config['pass'])
    wapi_session.verify = valid_cert

    headers = { 'content-type': "application/json" }

    start = datetime.datetime.now()
    print("Start Time: {}".format(start))
    for i in range(1, n+1):
        hostname = 'host' + str(i) + '.' + base_zone
        body = ( '{'
	                + '"name": "' + hostname + '",'
	                + '"ipv4addrs": ['
		            + '{'
                        + '"ipv4addr": {'
                        + '"_object_function": "next_available_ip",'
                        + '"_object": "network",'
                        + '"_object_parameters": {'
                        + '    "network": "10.0.0.0/16"'
                        + '},'
                        + ' "_result_field": "ips",'
                        + ' "_parameters": {'
                        + '     "num": 1'
                        + '}'
                        + '}'
                    + '}'
                    +']'
                + '}' )

        response = wapi_session.post(url, data=body, headers=headers)
        if response.status_code == requests.codes.ok:
            print("Created host: {}".format(hostname), end='\r', flush=True)
        else:
            print ("Resposne Code: {}".format(response.status_code))
            print ("Response Text: {}".format(response.text))
    end = datetime.datetime.now()
    print("End Time: {}".format(end))
    time = end - start
    
    return time


def create_cname(config, base_zone, n):
    '''
    '''
    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['version'] + '/' + csvjob )

    if config['valid_cert'] == 'true':
        valid_cert = True
    else:
        valid_cert = False

    # Avoid error due to a self-signed cert.
    if not valid_cert:
        requests.packages.urllib3.disable_warnings()
    
    wapi_session = requests.session()
    wapi_session.auth = (config['user'], config['pass'])
    wapi_session.verify = valid_cert

    headers = { 'content-type': "application/json" }

    start = datetime.datetime.now()
    print("Start Time: {}".format(start))
    for i in range(1, n+1):
        hostname = 'host' + str(i) + '.' + base_zone
        body = ( '{'
	                + '"name": "' + hostname + '",'
	                + '"ipv4addrs": ['
		            + '{'
                        + '"ipv4addr": {'
                        + '"_object_function": "next_available_ip",'
                        + '"_object": "network",'
                        + '"_object_parameters": {'
                        + '    "network": "10.0.0.0/16"'
                        + '},'
                        + ' "_result_field": "ips",'
                        + ' "_parameters": {'
                        + '     "num": 1'
                        + '}'
                        + '}'
                    + '}'
                    +']'
                + '}' )

        response = wapi_session.post(url, data=body, headers=headers)
        if response.status_code == requests.codes.ok:
            print("Create host: {}".format(hostname))
        else:
            status = 'WAPI_ERROR'
            print ("Error occured: {}".format(response.text))
    
    end = datetime.datetime.now()
    print("End Time: {}".format(end))
    time = end - start

    return time


def create_a_record(config, base_zone, n):
    '''
    '''
    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['version'] + '/' + csvjob )

    if config['valid_cert'] == 'true':
        valid_cert = True
    else:
        valid_cert = False

    # Avoid error due to a self-signed cert.
    if not valid_cert:
        requests.packages.urllib3.disable_warnings()
    
    wapi_session = requests.session()
    wapi_session.auth = (config['user'], config['pass'])
    wapi_session.verify = valid_cert

    headers = { 'content-type': "application/json" }

    start = datetime.datetime.now()
    print("Start Time: {}".format(start))
    for i in range(n+1):
        hostname = 'host' + str(i) + '.' + base_zone
        body = ( '{'
	                + '"name": "' + hostname + '",'
	                + '"ipv4addrs": ['
		            + '{'
                        + '"ipv4addr": {'
                        + '"_object_function": "next_available_ip",'
                        + '"_object": "network",'
                        + '"_object_parameters": {'
                        + '    "network": "10.0.0.0/16"'
                        + '},'
                        + ' "_result_field": "ips",'
                        + ' "_parameters": {'
                        + '     "num": 1'
                        + '}'
                        + '}'
                    + '}'
                    +']'
                + '}' )

        response = wapi_session.post(url, data=body, headers=headers)
        # if response.status_code == requests.codes.ok:
        print("Created host: {}".format(hostname), end='\r', flush=True)
        # else:
        print ("Resposne Code: {}".format(response.status_code))
        print ("Error Text: {}".format(response.text))
    
    end = datetime.datetime.now()
    print()
    print("End Time: {}".format(end))
    time = end - start

    return time

       
def main():
    '''
    Code logic
    '''
    exitcode = 0
    run_time = 0

    # Parse CLI arguments
    args = parseargs()
    inifile = args.config
    n = args.number
    base_zone = args.basezone

    # Read inifile
    config = read_ini(inifile)

    if args.record_type == 'host':
        run_time = create_hosts(config, base_zone, n)
    elif args.record_type == 'a':
        run_time = create_a_records(config, base_zone, n)
    elif args.record_type == 'cname':
        run_time = create_cname(config, base_zone, n)
    else:
        print('Object type {} not yet supported.'.format(args.record_type))
    
    print('Run time: {}'.format(run_time))

    return exitcode


### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)
## End Main ###