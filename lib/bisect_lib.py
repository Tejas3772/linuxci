

import os
import json
import re
import logging
import fcntl
import sys
import subprocess
# import commands
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
# avocado_test_run = config_details.get('Details', 'avocado_test_run')
base_path = config_details.get('Details', 'base_path')
schedQfile = config_details.get('Details', 'schedQfile')
machineQfile = config_details.get('Details', 'machineQfile')
repo_path = config_details.get('Details', 'repo_path')
hostcopy_path = config_details.get('Details', 'hostcopy_path')
subscribersfile = config_details.get('Details', 'subscribersfile')
scp_timeout = int(config_details.get('Details', 'scp_timeout'))
test_timeout = int(config_details.get('Details', 'test_timeout'))


# Function to read JSON data from a file
def read_json(path):
    if os.path.isfile(path):
        try: 
            with open(path, 'r', encoding="utf-8") as subfile:
                json_data = json.load(subfile)
                file_contents = json_data.get('data', {})
        except (FileNotFoundError, json.JSONDecodeError):
            file_contents = {}
        return file_contents
    else:
        return {}


# Function to append JSON data to a file
def append_json(path, json_details):
    file_contents = read_json(path)
    file_contents.append(json_details)
    with open(path, mode='w') as file_json:
        json.dump({'data': file_contents}, file_json)


# Function to append JSON diff data to a file
def append_diff_json(path, json_details):
    file_contents = read_json(path)
    if not file_contents:
        file_contents = {}
    file_contents.update(json_details)
    with open(path, mode='w') as file_json:
        json.dump({'data': file_contents}, file_json)



# Function to update JSON data in a file
def update_json(path, json_details):
    with open(path, mode='w') as file_json:
        json.dump({'data': json_details}, file_json)

# def read_json(path):
#     if os.path.isfile(path):
#         try: 
#             subfile = open(path, 'r', encoding="utf-8")
#             json_data = json.load(subfile)
#             file_contents = json_data['data']
#         except(FileNotFoundError , json.JSONDecodeError):
#             file_contents={}
#         return file_contents
#     else:
#         return []


# def append_json(path, json_details):
#     file_contents = read_json(path)
#     json_data = {}
#     with open(path, mode='w') as file_json:
#         file_contents.append(json_details)
#         json_data['data'] = file_contents
#         json.dump(json_data, file_json)
# def append_diff_json(path, json_details):
#     file_contents = read_json(path)
#     if not file_contents:
#         file_contents = {}
#     file_contents.update(json_details)
#     update_json(path, file_contents)
# # def append_diff_json(path,json_details):
# #     file_contents = read_json(path)
# #     if not file_contents:
# #         file_contents = {}
# #     json_data = {}
# #     with open(path, mode='w') as file_json:
# #         file_contents.update(json_details)
# #         json_data['data'] = file_contents
# #         json.dump(json_data, file_json)
# def update_json(path, json_details):
#     json_data = {}
#     with open(path, mode='w') as file_json:
#         json_data['data'] = json_details
#         json.dump(json_data, file_json)
