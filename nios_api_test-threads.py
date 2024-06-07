#!/usr/bin/env python3
#vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
'''

 Description:

    NIOS WAPI Benchmark Script
    Note: Uses next available IP for host and A records
    Uses threading with multiple sessions

 Requirements:
   Python 3.6+

 Author: Chris Marrison

 Date Last Updated: 20210901

 Todo:

 Copyright (c) 2021 Chris Marrison / Infoblox

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
__version__ = '0.1.2'
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
import concurrent.futures
import ipaddress
import tqdm


def parseargs():
    '''
    Parse Arguments Using argparse

    Parameters:
        None

    Returns:
        Returns parsed arguments
    '''
    parse = argparse.ArgumentParser(description='Test API DNS Object creation in NIOS')
    parse.add_argument('-c', '--config', type=str, default='gm.ini',
                        help="Override ini file")
    parse.add_argument('-r', '--record_type', type=str, default="host",
                        help="Specify Object Type [host, a, cname, networks]")
    parse.add_argument('-z', '--basezone', type=str, default="apitest.poc",
                        help="Specify base zone for objects")
    parse.add_argument('-n', '--number', type=int, default=1,
                        help="Number of Objects to create")
    parse.add_argument('-t', '--threads', type=int, default=5,
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
    ini_keys = ['gm', 'api_version', 'valid_cert', 'user', 
                'pass', 'network', 'sleep']

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


def create_session(config):
    '''
    '''
    headers = { 'content-type': "application/json" }

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
    wapi_session.headers = headers

    return wapi_session


def wapi_call(session, hostname, **params):
    '''
    '''
    response = session.post(**params)
    if response.status_code == 201:
        result = hostname + ': Success'
    else:
        result = hostname + ': Failed :' + response.text

    return result

def make_wapi_calls(sessions, hostnames, url, body):
    '''
    '''
    results = []

    for z in range(0, 4):
        results.append(wapi_call(sessions[z], hostnames[z], url=url, data=body[z]))

    return results


def create_hosts(config, base_zone, n, threads=20):
    '''
    '''
    time = 0
    results = []
    sessions = []
    hostname = []
    body = []
    tasks = []

    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['api_version'] + '/record:host' )

    for i in range(0, 5):
        sessions.append(create_session(config))

    start = datetime.datetime.now()
    with tqdm.tqdm(total=n) as pbar:
        for i in range(1, n+1, 5):
            hostnames = []
            body = []
            for x in range(0, 4):
                host = 'host' + str(i+x) + '.' + base_zone
                hostnames.append(host)
                data = ( '{'
                            + '"name": "' + host + '",'
                            + '"ipv4addrs": ['
                            + '{'
                                + '"ipv4addr": {'
                                + '"_object_function": "next_available_ip",'
                                + '"_object": "network",'
                                + '"_object_parameters": {'
                                + '    "network": "' + config['network'] + '"'
                                + '},'
                                + ' "_result_field": "ips",'
                                + ' "_parameters": {'
                                + '     "num": 1'
                                + '}'
                                + '}'
                            + '}'
                            +']'
                        + '}' )
                body.append(data)

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for z in range(0, 4):
                    tasks.append(executor.submit(wapi_call, session=sessions[z], hostname=hostnames[z], url=url, data=body[z]))

            pbar.update(5)

            
        '''
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), end='\r', flush=True)
        if response.status_code == 201:
            print("Created host: {}".format(hostname), end='\r', flush=True)
        else:
            print ("Resposne Code: {}".format(response.status_code))
            print ("Response Text: {}".format(response.text))
        '''

    end = datetime.datetime.now()
    print()
    for task in concurrent.futures.as_completed(tasks):
        # print("Result for host: {} ".format(future.result()), end='\r', flush=True)
        print("Result for host: {} ".format(task.result()))
    print()
    print("Start Time: {}".format(start))
    print("End Time: {}".format(end))
    time = end - start

    
    return time


def create_networks(config, n, threads=20):
    '''
    '''
    time = 0
    results = []
    sessions = []
    hostname = []
    body = []
    tasks = []

    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['api_version'] + '/network' )

    net = ipaddress.ip_network(config['network'])
    subnets = list(net.subnets(new_prefix=24))

    for i in range(0, 5):
        sessions.append(create_session(config))

    start = datetime.datetime.now()
    with tqdm.tqdm(total=n) as pbar:
        position = 0
        for i in range(1, n+1, 5):
            networks = []
            body = []
            for x in range(0, 4):
                network = str(subnets[ position + x ])
                networks.append(network)
                data = ( '{'
                            + '"network": "' + network + '",'
                            + '"extattrs": { "Building": { "value": "Lab" } }'
                        + '}' )
                body.append(data)
            position += 5

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for z in range(0, 4):
                    tasks.append(executor.submit(wapi_call, session=sessions[z], hostname=networks[z], url=url, data=body[z]))

            pbar.update(5)

            
        '''
        for future in concurrent.futures.as_completed(futures):
            print(future.result(), end='\r', flush=True)
        if response.status_code == 201:
            print("Created host: {}".format(hostname), end='\r', flush=True)
        else:
            print ("Resposne Code: {}".format(response.status_code))
            print ("Response Text: {}".format(response.text))
        '''

    end = datetime.datetime.now()
    print()
    for task in concurrent.futures.as_completed(tasks):
        # print("Result for host: {} ".format(future.result()), end='\r', flush=True)
        print("Result for host: {} ".format(task.result()))
    print()
    print("Start Time: {}".format(start))
    print("End Time: {}".format(end))
    time = end - start

    
    return time


def create_cnames(config, base_zone, n, threads=20):
    '''
    '''
    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['api_version'] + '/record:cname' )

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
                        + '    "network": "' + config["network"] + '"'
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


def create_a_records(config, base_zone, n, threads=20):
    '''
    '''
    time = 0
    results = []
    sessions = []
    hostnames = []
    body = []
    tasks = []
    net = ipaddress.ip_network(config['network'])
    ips = list(net.hosts())

    url = ( 'https://' + config['gm'] + '/wapi/' 
          + config['api_version'] + '/record:a' )

    for i in range(0, 5):
        sessions.append(create_session(config))

    start = datetime.datetime.now()
    with tqdm.tqdm(total=n) as pbar:
        for i in range(1, n+1, 5):
            hostnames = []
            body = []
            for x in range(0, 4):
                host = 'ahost' + str(i+x) + '.' + base_zone
                ip = str(ips[x + i])
                hostnames.append(host)
                data = ( '{'
                            + '"name": "' + host + '",'
                            + '"ipv4addr": '
                            + '"' + ip +'"'
                        + '}' )
                body.append(data)

            with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
                for z in range(0, 4):
                    tasks.append(executor.submit(wapi_call, session=sessions[z], hostname=hostnames[z], url=url, data=body[z]))

            pbar.update(5)

            
    end = datetime.datetime.now()
    print()
    for task in concurrent.futures.as_completed(tasks):
        # print("Result for host: {} ".format(future.result()), end='\r', flush=True)
        print("Result for a-record: {} ".format(task.result()))
    print()
    print("Start Time: {}".format(start))
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
        run_time = create_hosts(config, base_zone, n, threads=args.threads)
    elif args.record_type == 'a':
        run_time = create_a_records(config, base_zone, n, threads=args.threads)
    elif args.record_type == 'cname':
        run_time = create_cnames(config, base_zone, n, threads=args.threads)
    elif args.record_type == 'networks':
        run_time = create_networks(config, n, threads=args.threads)
    else:
        print('Object type {} not yet supported.'.format(args.record_type))
    
    print('Run time: {}'.format(run_time))

    return exitcode


### Main ###
if __name__ == '__main__':
    exitcode = main()
    exit(exitcode)
## End Main ###
