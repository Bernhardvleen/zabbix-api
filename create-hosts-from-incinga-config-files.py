#######################################################################
### loads hosts from icinga style cfg files and creates them 
### in zabbix via https requests to the zabbix api 
### host groups will be created if not exists 
### hosts are checked for existence prior to creating 
### proxy host is set by its ID 
### template is set by its ID
### @LBE 2024-01 Gekko GmbH 
#######################################################################

import os
import re
import requests
import json
from typing import List
from pydantic import BaseModel

class HostInterface(BaseModel):
    type: int
    main: int
    useip: int
    ip: str
    dns: str = ''
    port: str

class HostGroup(BaseModel):
    groupid: str

class Template(BaseModel):
    templateid: str

class ZabbixHostCreateRequest(BaseModel):
    jsonrpc: str = '2.0'
    method: str = 'host.create'
    params: dict
    auth: str
    id: int = 1

class ZabbixHostCreateParams(BaseModel):
    host: str
    proxy_hostid: str 
    interfaces: List[HostInterface]
    groups: List[HostGroup]
    templates: List[Template]

# Zabbix API URL
url = 'http://192.168.77.10/zabbix/api_jsonrpc.php'

# Zabbix API credentials
username = 'bernhard-api'
password = 'wirklichsehrsupergutesapipasswordalda009!'

def logout_user_with_session_token(auth_token):
    
    auth_data = {
        'jsonrpc': '2.0',
        'method': 'user.logout',
        'params': {},
        'id': 1,
        'auth': auth_token        
    }

    # Convert the data to JSON
    auth_json = json.dumps(auth_data)

    # Make the API authentication request
    auth_response = requests.post(url, data=auth_json, headers={'Content-Type': 'application/json'})
    auth_result = auth_response.json()
    return auth_result  

def create_host_if_not_exists(host_name, auth_token, template_id, host_group_id, ip_address, proxy_address):
    get_host_data = {
        'jsonrpc': '2.0',
        'method': 'host.get',
        'params': {
            'filter': {'host': host_name},
        },
        'auth': auth_token,
        'id': 1,
    }

    response = requests.post(url, data=json.dumps(get_host_data), headers={'Content-Type': 'application/json'})
    existing_hosts = response.json().get('result', [])

    print('host exisits?:')
    print(existing_hosts)

    if existing_hosts:
        print(f"Host '{host_name}' already exists with hostid: {existing_hosts[0]['hostid']}")
    else:
        # Create the host
        request_params = ZabbixHostCreateParams(
            host=host_name,
            proxy_hostid=proxy_address,
            interfaces=[HostInterface(type=1, main=1, useip=1, ip=ip_address, dns='', port='10050')],
            groups=[HostGroup(groupid=host_group_id)],
            templates=[Template(templateid=template_id)],
        )

        data = ZabbixHostCreateRequest(
            params=request_params.dict(),
            auth=auth_token,
        )

        # Convert the data to JSON
        data_json = json.dumps(data.dict())

        # Make the API request
        response = requests.post(url, data=data_json, headers={'Content-Type': 'application/json'})

        # Print the API response
        print('response:')
        print(response.json())

def get_file_names_from_folder(folder_path):
    if not os.path.exists(folder_path):
        print(f"The folder '{folder_path}' does not exist.")
        return None

    # Get a list of filenames in the specified folder (without subfolders)
    filenames = [filename for filename in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, filename))]

    return filenames

def get_host_group_id(group_name: str, auth_token: str) -> str:
    get_host_group_data = {
        'jsonrpc': '2.0',
        'method': 'hostgroup.get',
        'params': {
            'output': 'extend',
            'filter': {'name': group_name},
        },
        'auth': auth_token,
        'id': 1,
    }

    response = requests.post(url, data=json.dumps(get_host_group_data), headers={'Content-Type': 'application/json'})
    existing_host_groups = response.json().get('result', [])
    print('does host-group exist?:')
    print(existing_host_groups)

    if existing_host_groups:
        return existing_host_groups[0]['groupid']
    else:
        # Create the host group
        create_host_group_data = {
            'jsonrpc': '2.0',
            'method': 'hostgroup.create',
            'params': {
                'name': group_name,
            },
            'auth': auth_token,
            'id': 1,
        }

        response = requests.post(url, data=json.dumps(create_host_group_data), headers={'Content-Type': 'application/json'})
        created_group_id = response.json().get('result', {}).get('groupids', [])[0]

        if not created_group_id:
            raise Exception(f"Failed to create host group: {group_name}")
        
        print('created group id:')
        print(created_group_id)
        return created_group_id

def load_host_data_from_file(filename, file_path):
    file_path_combo = file_path + filename
    with open(file_path_combo, 'r') as file:
        inside_definition = False
        extracted_hosts = []

        for line in file:
            if line.strip().startswith("define host{"):
                inside_definition = True
            elif inside_definition and line.strip() == "}":
                inside_definition = False
                continue
            # end host marker für erzeugen von zabbix host part für import file 
            elif inside_definition:
                #if line.strip().startswith("name") or line.strip().startswith("host_name"):
                if line.strip().startswith("host_name"):
                    parts = line.split(r'\s+', 1)
                    name = [
                        re.sub(r'[^\w.-]+', '', word.strip())
                        for line in parts
                        for word in line.split()
                    ]
                    extracted_hosts.append(name)
                elif line.strip().startswith("address"):
                    parts = line.split(r'\s+', 1)
                    name = [
                        re.sub(r'[^\w.-]+', '', word.strip())
                        for line in parts
                        for word in line.split()
                    ]
                    extracted_hosts.append(name)
                #else:
                #    # If no "address" field is found, append a default value
                #    extracted_addresses.append("no address")
                #extracted_names.append("\n")
                    # since we read key and value line by line we do can not create hostname as key and ip as value in one go 
                    # for now we merge the two parts together - but it would be better to create the array in the desired form with a toggle or something
                
        merged_list = {extracted_hosts[idx][1]: extracted_hosts[idx + 1][1] for idx in range(0, len(extracted_hosts), 2)}
        return merged_list
        #return extracted_hosts



# Step 1: Get Zabbix API token
auth_data = {
    'jsonrpc': '2.0',
    'method': 'user.login',
    'params': {
        'username': username,
        'password': password,
    },
    'id': 1,
}

auth_response = requests.post(url, data=json.dumps(auth_data), headers={'Content-Type': 'application/json'})
auth_token = auth_response.json().get('result')
print(auth_token)

if not auth_token:
    raise Exception("Failed to authenticate. Check your credentials.")


# Step 2: Check if the host group exists and create it if not
host_group_name = 'Universal/Availabilty/ponte/siscon'
host_group_id = get_host_group_id(host_group_name, auth_token)

## path to where the cfg files exist 
folder_path = r"C:\Users\b.leenhoff\Documents\python\zabbix\production\verarbeitung\siscon\\"

# Step 3: Iterate over the cfg files in the folder and extract hostname & address lines and then check if the host exists and create it if not
host_name = 'new-host-003'

ip_address = '192.168.7.8'

## the above values are ignored when importing from a file 
## only this is important to make sure the correct proxy is used!
proxy_hostid = '10416'

##
## did we set the correct proxy? 
## hostgroup and template id?
## did we set the correct folder_path for import? 
## 

template_id = '11664'
## todo: make overview like this for templates - atm we only use icmp gen av 
##### get-template-id-from-name.ps1
## Template ID for 'GEKKO - Base Module - Network - ICMP - Availability' is: 11099
## Template ID for 'OEJAB - Role - Virtual Machine - Windows - Printserver' is: 11657


##########################################
##########################################
##
## proxie IDs
## Zabbix-Proxy01.service.gekko.at 
## proxy_hostid = '10416'

## Zabbix-Proxy01.ad.oejab.at
## proxy_hostid = '10820'

## Zabbix-Proxy01.ad.senecura 
## proxy_hostid = '10821'

## Zabbix-Proxy01.office.gekko.at
## proxy_hostid = '10376'

## Zabbix-Proxy02.office.gekko.at
## proxy_hostid = '18042'
##
##########################################


for file in get_file_names_from_folder(folder_path):
    read_host_data = load_host_data_from_file(file, folder_path)
    print('found stuff:')
    print(read_host_data)
    print('length:')
    print(len(read_host_data))
    if len(read_host_data) == 1:
        name, ip = next(iter(read_host_data.items()))
        create_host_if_not_exists(name, auth_token, template_id, host_group_id, ip, proxy_hostid)
    else:
        for name, ip in read_host_data.items():
            if ip != '' and name != '':
                create_host_if_not_exists(name, auth_token, template_id, host_group_id, ip, proxy_hostid)
            

# Step 4: logout -> wir haben zwar ein autologout für den user definiert, aber muss ja nicht sein ^^
# will man die results irgendwie im programm weiterverarbeiten, kann man diese IDs hochzählen und merken 
                

logout_user_with_session_token(auth_token)
