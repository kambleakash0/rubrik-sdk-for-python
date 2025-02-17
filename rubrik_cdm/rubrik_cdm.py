# Copyright 2020 Rubrik, Inc.
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to
#  deal in the Software without restriction, including without limitation the
#  rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
#  sell copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in
#  all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#  FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.

"""
This module contains the Rubrik SDK Connect class.
"""

import base64
import requests
import os
import logging
from random import choice
import time
import socket
import sys
import inspect

from .api import Api
from .cluster import Cluster
from .data_management import Data_Management
from .physical import Physical
from .cloud import Cloud
from .organization import Organization
from .exceptions import InvalidParameterException, RubrikException, APICallException, InvalidTypeException


class Connect(Cluster, Data_Management, Physical, Cloud, Organization):
    """This class acts as the base class for the Rubrik SDK and serves as the main interaction point
    for its end users. It also contains various helper functions used throughout the SDK.

    Arguments:
        Cluster {class} -- This class contains methods related to the management of the Rubrik Cluster itself.
        Data_Management {class} - This class contains methods related to backup and restore operations for the various objects managed by the Rubrik Cluster.
        Physical {class} - This class contains methods related to the management of the Physical objects in the Rubrik Cluster.
        Cloud {class} - This class contains methods for the managment of Cloud related functionality on the Rubrik cluster.
    """

    def __init__(self, node_ip=None, username=None, password=None, api_token=None, enable_logging=False, logging_level="debug"):
        """Constructor for the Connect class which is used to initialize the class variables.

        Keyword Arguments:
            node_ip {str} -- The Hostname or IP Address of a node in the Rubrik cluster you wish to connect to. If a value is not provided we will check for a `rubrik_cdm_node_ip` environment variable. (default: {None})
            username {str} -- The Username you wish to use to connect to the Rubrik cluster. If a value is not provided we will check for a `rubrik_cdm_username` environment variable. (default: {None})
            password {str} -- The Password you wish to use to connect to the Rubrik cluster. If a value is not provided we will check for a `rubrik_cdm_password` environment variable. (default: {None})
            api_token {str} -- The API Token you wish to use to connect to the Rubrik cluster. If populated, the `username` and `password` fields will be ignored. If a value is not provided we will check for a `rubrik_cdm_token` environment variable.  (default: {None})
            enable_logging {bool} -- Flag to determine if logging will be enabled for the SDK. (default: {False})
            logging_level {str} -- Sets the threshold for logging to the provided to level. Logging messages which are less severe than level will be ignored. (default: {debug}) (choices: {debug, critical, error, warning, info})
        """

        set_logging = {
            "debug": logging.DEBUG,
            "critical": logging.CRITICAL,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "info": logging.INFO,
        }

        if logging_level not in set_logging:
            raise InvalidParameterException(
                "'{}' is not a valid logging_level. Valid choices are 'debug', 'critical', 'error', 'warning', or 'info'.".format(logging_level))

        # Enable logging for the SDK
        self.logging_level = logging_level
        if enable_logging:
            logging.getLogger().setLevel(set_logging[self.logging_level])

        if node_ip is None:
            node_ip = os.environ.get('rubrik_cdm_node_ip')
            if node_ip is None:
                raise InvalidParameterException(
                    "The Rubrik CDM Node IP has not been provided.")
            else:
                self.node_ip = node_ip
        else:
            self.node_ip = node_ip

        self.log("Node IP: {}".format(self.node_ip))

        # Initialize empty variable as a placeholder until full IPv6 support is added to Connect()
        self.ipv6_addr = ""

        # List to store how the credentials have been provided
        credentials_manually_provided = []
        credentials_env_var_provided = []
        # Combined list of manually provided and env var provided
        all_credentials_provided = []

        # Flag used to determine if we have enough information to authenticate against the Rubrik cluster
        credentials_needed_for_authentication = False

        if username:
            credentials_manually_provided.append("username")
        else:
            username = os.environ.get('rubrik_cdm_username')
            if username is not None:
                credentials_env_var_provided.append("username")

        if password:
            credentials_manually_provided.append("password")
        else:
            password = os.environ.get('rubrik_cdm_password')
            if password is not None:
                credentials_env_var_provided.append("password")

        if api_token:
            credentials_manually_provided.append("api_token")
        else:
            api_token = os.environ.get('rubrik_cdm_token')
            if api_token is not None:
                credentials_env_var_provided.append("api_token")

        all_credentials_provided = credentials_manually_provided + \
            credentials_env_var_provided

        if len(credentials_manually_provided) == 3:
            raise InvalidParameterException(
                "You have provided both an API token and a username and password for authentication. You may only use one or the other.")

        if "username" in all_credentials_provided and "password" not in all_credentials_provided:
            raise InvalidParameterException(
                "When providing the username argument, either manually or through the environment variables, you must also provide a password. Alternatively, starting with CDM 5.0, you may also use API Token instead of username and password.")

        if "password" in all_credentials_provided and "username" not in all_credentials_provided:
            raise InvalidParameterException(
                "When providing the password argument, either manually or through the environment variables, you must also provide a username. Alternatively, starting with CDM 5.0, you may also use API Token instead of username and password.")

        if "username" in credentials_manually_provided and "password" in credentials_manually_provided:

            self.username = username
            self.password = password
            self.api_token = None

            self.log("Username: {}".format(self.username))
            self.log("Password: ******")

            credentials_needed_for_authentication = True

        if "api_token" in credentials_manually_provided:
            self.api_token = api_token

            self.log("API Token: ******")

            credentials_needed_for_authentication = True

        if credentials_needed_for_authentication is False:
            if len(credentials_env_var_provided) == 3:
                raise InvalidParameterException(
                    "You have provided both an API token and a username and password, in your environment variables, for authentication. You may only use one or the other.")

            if "username" in all_credentials_provided and "password" in all_credentials_provided:

                self.username = username
                self.password = password
                self.api_token = None

                self.log("Username: {}".format(self.username))
                self.log("Password: ******")

                credentials_needed_for_authentication = True

            if "api_token" in credentials_env_var_provided and credentials_needed_for_authentication is False:
                self.api_token = api_token
                self.log("API Token: ******")
                credentials_needed_for_authentication = True

        if credentials_needed_for_authentication is False:
            raise InvalidParameterException(
                "You must provide either a username and password or API Token for authentication.")

        self.sdk_version = "2.0.10"
        self.python_version = sys.version.split("(")[0].strip()
        # function_name will be populated in each function
        self.function_name = ""
        # Optional value to define the Platform using the SDK (Ex. Ansible)
        self.platform = ""

    def log(self, log_message):
        """Create properly formatted debug log messages.

        Arguments:
            log_message {str} -- The message to pass to the debug log.
        """

        log = logging.getLogger(__name__)

        set_logging = {
            "debug": log.debug,
            "critical": log.critical,
            "error": log.error,
            "warning": log.warning,
            "info": log.info

        }
        set_logging[self.logging_level](log_message)

    def _authorization_header(self):
        """Internal method used to create the authorization header used in the API calls.

        Returns:
            dict -- The authorization header that utilizes Basic authentication.
        """

        user_agent = "RubrikPythonSDK--{}--{}".format(
            self.sdk_version, self.python_version)
        if self.platform != "":
            user_agent = user_agent + '--' + self.platform

        self.log("User Agent: {}".format(user_agent))

        authorization_header = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': user_agent,
            'rk-integration': self.function_name
        }

        if self.api_token is None:
            credentials = '{}:{}'.format(self.username, self.password)

            # Encode the Username:Password as base64
            authorization = base64.b64encode(credentials.encode())
            # Convert to String for API Call
            authorization = authorization.decode()

            authorization_header["Authorization"] = 'Basic {}'.format(
                authorization)

        else:

            authorization_header["Authorization"] = 'Bearer {}'.format(
                self.api_token)

        return authorization_header

    def _header(self):
        """Internal method used to create the a header without authorization used in the API calls.

        Returns:
            dict -- The header that does not include any authorization.
        """

        user_agent = "RubrikPythonSDK--{}--{}".format(
            self.sdk_version, self.python_version)
        if self.platform != "":
            user_agent = user_agent + '--' + self.platform

        header = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': user_agent,
            'rk-integration': self.function_name

        }

        self.log("Header: {}".format(header))
        return header

    @staticmethod
    def _api_validation(api_version, api_endpoint):
        """Internal method used to validate the API Version and API Endpoint provided by the end user

        Arguments:
            api_version {str} -- The version of the Rubrik CDM API to call. (choices: {v1, v2, internal})
            api_endpoint {str} -- The endpoint of the Rubrik CDM API to call (ex. /cluster/me).
        """

        valid_api_versions = ['v1', 'v2', 'internal', 'v3']

        # Validate the API Version
        if api_version not in valid_api_versions:
            raise InvalidParameterException(
                "Enter a valid API version {}.".format(valid_api_versions))

        # Validate the API Endpoint Syntax
        if not isinstance(api_endpoint, str):
            raise InvalidTypeException("The API Endpoint must be a string.")
        elif api_endpoint[0] != "/":
            raise InvalidParameterException(
                "The API Endpoint should begin with '/'. (ex: /cluster/me)")
        elif api_endpoint[-1] == "/":
            if api_endpoint[-2] != "=":
                raise InvalidParameterException(
                    "Error: The API Endpoint should not end with '/' unless proceeded by '='. (ex. /cluster/me or /fileset/snapshot/<id>/browse?path=/)")

    def _platform_user_agent(self, platform_name, platform_version):
        """Internal method to used to populated the user-agent string with an
        optional string for the Platform consuming the SDK.

        Arguments:
            platform_name {str} -- The name of the Platform consuming the SDK (Ex. Ansible)
            platform_version {str} -- The version of the Platform consuming the SDK.
        """

        platform_user_agent = ""

        if platform_name != "":
            platform_user_agent = "platform_name--{}".format(platform_name)

        if platform_version != "":
            platform_user_agent = platform_user_agent + \
                "--platform_version--{}".format(platform_version)

        self.platform = platform_user_agent


class Bootstrap(Api):
    """This class contains all functions related to the Bootstrapping of a Rubrik Cluster.

    Arguments:
        Api {class} - This class contains the base API methods that can be called independently or internally in standalone functions.
    """

    def __init__(self, node_ip, interface=None, enable_logging=False):
        """Constructor for the Bootstrap class which is used to initialize the class variables.
        """
        if enable_logging:
            logging.getLogger().setLevel(logging.DEBUG)

        self.node_ip = node_ip
        self.log("User Provided Node IP: {}".format(self.node_ip))
        if interface is not None:
            self.log("User Provided Interface: {}".format(interface))
            try:
                socket.if_nametoindex(interface)
            except OSError:
                sys.exit("Error: Invalid interface supplied")

        node_resolution = False
        self.ipv6_addr = ""

        try:
            # Attempt to resolve and/or obtain scope for supplied address
            ip_info = socket.getaddrinfo(self.node_ip, 443, socket.AF_INET6)
            # Extract address from response
            self.ipv6_addr = ip_info[0][4][0]
            if '::ffff' in self.ipv6_addr:
                self.ipv6_addr = ""
                self.log("Resolved Node IPv4 address: {}".format(self.node_ip))
                node_resolution = True
            else:
                self.log('Resolved IPv6 address')
                if interface is not None:
                    # Use user provided interface as scope
                    self.ipv6_scope = socket.if_nametoindex(interface)
                    self.log("IPv6 scope: {}".format(self.ipv6_scope))
                else:
                    # Extract scope from socket.getaddrinfo
                    self.ipv6_scope = str(ip_info[0][4][3])
                    self.log("IPv6 scope: {}".format(self.ipv6_scope))
                    if self.ipv6_scope == "0":
                        # Scope 0 is invalid, so find the first non-loopback interface and use that as the scope
                        self.log(
                            'IPv6 link local scope not resolved, searching for a usable scope')
                        interfaces = socket.if_nameindex()
                        for sock_interface, name in interfaces:
                            if 'lo' not in name:
                                self.log("Using scope {}, interface {}".format(
                                    sock_interface, name))
                                self.ipv6_scope = sock_interface
                                break
                        if self.ipv6_scope == 0:
                            sys.exit(
                                "Error: Unable to find a usable IPv6 link local scope")
                # Properly format link-local IPv6 address with scope
                self.node_ip = ('[{}%{}]').format(
                    self.ipv6_addr, self.ipv6_scope)
                self.log("Resolved Node IP: {}".format(self.node_ip))
                node_resolution = True
        except socket.gaierror:
            self.log('Could not resolve link-local IPv6 address for cluster.')

        # IPv6 resolution failed, verify IPv4
        if node_resolution == False:
            try:
                ip_info = socket.getaddrinfo(self.node_ip, 443, socket.AF_INET)
                self.log("Resolved Node IP: {}".format(self.node_ip))
                node_resolution = True
            except socket.gaierror:
                self.log('Could not resolve IPv4 address for cluster.')

        if node_resolution is False:
            raise RubrikException(
                "Error: Could not resolve address for cluster, or invalid IP/address supplied")

        self.sdk_version = "2.0.10"
        self.python_version = sys.version.split("(")[0].strip()
        # function_name will be populated in each function
        self.function_name = ""
        # Optional value to define the Platform using the SDK (Ex. Ansible)
        self.platform = ""

    def setup_cluster(self, cluster_name, admin_email, admin_password, management_gateway, management_subnet_mask, node_config, enable_encryption=True, dns_search_domains=None, dns_nameservers=None, ntp_servers=None, wait_for_completion=True, management_vlan=None, ipmi_gateway=None, ipmi_subnet_mask=None, ipmi_vlan=None, node_ipmi_ips=None, data_gateway=None, data_subnet_mask=None, data_vlan=None, node_data_ips=None, timeout=30):  # pylint: ignore
        """Issues a bootstrap request to a specified Rubrik cluster: Edge, Cloud Cluster or Physical nodes
            Edge: no IPMI, no DATA and no Encryption set. One node only. IPv4 or IPv6 possible.
            CloudCluster: same as Edge but more nodes possible. Only IPv4 bootstrap.
            Physical: Management and IPMI networks mandatory. IPv6 only.
            Node names needed are in IPv6 mDNS broadcast traffic (SERIAL.local) which can be used for automation.

        Arguments:
            cluster_name {str} -- Unique name to assign to the Rubrik cluster. No FQDN allowed with dots.
            admin_email {str} -- The Rubrik cluster sends messages for the admin account to this email address.
            admin_password {str} --  Password for the admin account.
            management_gateway {str} --  IP address assigned to the management network gateway.
            management_subnet_mask {str} -- Subnet mask assigned to the management network.
            node_config {dict} -- The Node Name(s) and IP(s) formatted as a dictionary for Management addresses.

        Keyword Arguments:
            management_vlan {int} -- VLAN assigned to the management network. (default: {None})
            ipmi_gateway {str} --  IP address assigned to the ipmi network gateway. (default: {None})
            ipmi_subnet_mask {str} -- Subnet mask assigned to the ipmi network. (default: {None})
            ipmi_vlan {int} -- VLAN assigned to the ipmi network. (default: {None})
            node_ipmi_ips {dict} -- The Node Name and IP formatted as a dictionary for IPMI addresses. Optional. (default: {None})
            data_gateway {str} --  IP address assigned to the ipmi network gateway. (default: {None})
            data_subnet_mask {str} -- Subnet mask assigned to the ipmi network. (default: {None})
            data_vlan {int} -- VLAN assigned to the data network. (default: {None})
            node_data_ips {dict} -- The Node Name and IP formatted as a dictionary for Data addresses. Optional. (default: {None})
            enable_encryption {bool} -- Enable software data encryption at rest. When bootstraping a Cloud Cluster or Edge this value needs to be False. (default: {True})
            dns_search_domains {str} -- The search domain that the DNS Service will use to resolve hostnames that are not fully qualified. (default: {None})
            dns_nameservers {list} -- IPv4 addresses of DNS servers. (default: {['8.8.8.8']})
            ntp_servers {list} -- FQDN or IPv4 address of a network time protocol (NTP) server. (default: {['pool.ntp.org']})
            wait_for_completion {bool} -- Flag to determine if the function should wait for the bootstrap process to complete. (default: {True})
            timeout {int} -- The number of seconds to wait to establish a connection the Rubrik cluster before returning a timeout error. (default: {30})

        Returns:
            dict -- The response returned by `POST /internal/cluster/me/bootstrap`.
        """

        self.function_name = inspect.currentframe().f_code.co_name

        if node_config is None or isinstance(node_config, dict) is not True:
            raise InvalidParameterException(
                'You must provide a valid dictionary for "node_config" holding node names and management IPs.')

        if dns_search_domains is None:
            dns_search_domains = []
        elif isinstance(dns_search_domains, list) is not True:
            raise InvalidParameterException(
                'You must provide a valid list for "dns_search_domains".')

        if dns_nameservers is None:
            dns_nameservers = ['8.8.8.8']
        elif isinstance(dns_nameservers, list) is not True:
            raise InvalidParameterException(
                'You must provide a valid list for "dns_nameservers".')

        if ntp_servers is None:
            ntp_servers = ['pool.ntp.org']
        elif isinstance(ntp_servers, list) is not True:
            raise InvalidParameterException(
                'You must provide a valid list for "ntp_servers".')

        using_ipmi_config = False
        using_data_config = False

        if ipmi_gateway is not None and ipmi_subnet_mask is not None and isinstance(node_ipmi_ips, dict):
            using_ipmi_config = True
        if data_gateway is not None and data_subnet_mask is not None and isinstance(node_data_ips, dict):
            using_data_config = True

        bootstrap_config = {}
        bootstrap_config["enableSoftwareEncryptionAtRest"] = enable_encryption
        bootstrap_config["name"] = cluster_name
        bootstrap_config["dnsNameservers"] = dns_nameservers
        bootstrap_config["dnsSearchDomains"] = dns_search_domains

        if float(self.get('v1', '/cluster/me/version', timeout, authentication=False)['version'][:3]) < float(5.0):
            bootstrap_config["ntpServers"] = ntp_servers
        else:
            bootstrap_config["ntpServerConfigs"] = []
            for server in ntp_servers:
                bootstrap_config["ntpServerConfigs"].append({"server": server})

        bootstrap_config["adminUserInfo"] = {}
        bootstrap_config["adminUserInfo"]['password'] = admin_password
        bootstrap_config["adminUserInfo"]['emailAddress'] = admin_email
        bootstrap_config["adminUserInfo"]['id'] = "admin"

        bootstrap_config["nodeConfigs"] = {}

        for node_name, node_ip in node_config.items():
            bootstrap_config["nodeConfigs"][node_name] = {}
            bootstrap_config["nodeConfigs"][node_name]['managementIpConfig'] = {}
            bootstrap_config["nodeConfigs"][node_name]['managementIpConfig']['netmask'] = management_subnet_mask
            bootstrap_config["nodeConfigs"][node_name]['managementIpConfig']['gateway'] = management_gateway
            bootstrap_config["nodeConfigs"][node_name]['managementIpConfig']['address'] = node_ip
            if management_vlan is not None:
                bootstrap_config["nodeConfigs"][node_name]['managementIpConfig']['vlan'] = management_vlan

        if (using_ipmi_config):
            for node_name, ipmi_ip in node_ipmi_ips.items():
                if node_name not in bootstrap_config["nodeConfigs"]:
                    raise InvalidParameterException(
                        'Non-existent node name specified in IPMI addresses.')
                bootstrap_config["nodeConfigs"][node_name]['ipmiIpConfig'] = {}
                bootstrap_config["nodeConfigs"][node_name]['ipmiIpConfig']['netmask'] = ipmi_subnet_mask
                bootstrap_config["nodeConfigs"][node_name]['ipmiIpConfig']['gateway'] = ipmi_gateway
                bootstrap_config["nodeConfigs"][node_name]['ipmiIpConfig']['address'] = ipmi_ip
                if ipmi_vlan is not None:
                    bootstrap_config["nodeConfigs"][node_name]['ipmiIpConfig']['vlan'] = ipmi_vlan

        if (using_data_config):
            for node_name, data_ip in node_data_ips.items():
                if node_name not in bootstrap_config["nodeConfigs"]:
                    raise InvalidParameterException(
                        'Non-existent node name specified in DATA addresses.')
                bootstrap_config["nodeConfigs"][node_name]['dataIpConfig'] = {}
                bootstrap_config["nodeConfigs"][node_name]['dataIpConfig']['netmask'] = data_subnet_mask
                bootstrap_config["nodeConfigs"][node_name]['dataIpConfig']['gateway'] = data_gateway
                bootstrap_config["nodeConfigs"][node_name]['dataIpConfig']['address'] = data_ip
                if data_vlan is not None:
                    bootstrap_config["nodeConfigs"][node_name]['dataIpConfig']['vlan'] = data_vlan

        number_of_attempts = 1

        # Get the first node IP address so we can use it to check bootstrap status if IPv6 is disabled.
        self.ipv4_addr = list(node_config.values())[0]

        while True:

            try:
                self.log('bootstrap: Starting the bootstrap process.')
                api_request = self.post(
                    'internal',
                    '/cluster/me/bootstrap',
                    bootstrap_config,
                    timeout,
                    authentication=False)
                break
            except APICallException as bootstrap_error:
                if "Failed to establish a new connection: [Errno 111] Connection refused" in str(
                        bootstrap_error):
                    self.log(
                        'bootstrap: Connection refused. Waiting 30 seconds for the node to initialize before trying again.')
                    number_of_attempts += 1
                    time.sleep(30)
                elif "Cannot bootstrap from an already bootstrapped node" in str(bootstrap_error):
                    return "No change required. The Rubrik cluster is already bootstrapped."
                else:
                    self.log('bootstrap: Connection refused.')
                    raise RubrikException(bootstrap_error)

            if number_of_attempts == 12:
                raise APICallException(
                    "Unable to establish a connection to the Rubrik cluster.")

        request_id = api_request['id']

        if wait_for_completion:
            self.log('bootstrap: Waiting for the bootstrap process to complete.')
            while True:
                status = self.status(request_id, ipv4_addr=self.ipv4_addr)

                if status['status'] == 'IN_PROGRESS':
                    self.log("bootstrap_status: {}\n".format(status))
                    time.sleep(30)
                    continue
                elif status['status'] == 'FAILURE' or status['status'] == "FAILED":
                    raise RubrikException("{}".format(status['message']))
                else:
                    self.log("{}".format(status))
                    return status

        return api_request

    def status(self, request_id="1", timeout=15, ipv4_addr=None):
        """Retrieves status of in progress bootstrap requests

        Keyword Arguments:
            request_id {str} -- ID of the bootstrap request(default: {"1"})
            timeout {int} -- The response timeout value, in seconds, of the API call. (default: {15})

        Returns:
            dict -- The response returned by `GET /internal/cluster/me/bootstrap?request_id={request_id}`.
        """

        self.function_name = inspect.currentframe().f_code.co_name

        self.log('status: Getting the status of the Rubrik Cluster bootstrap.')
        bootstrap_status_api_endpoint = '/cluster/me/bootstrap?request_id={}'.format(
            request_id)
        self.log(bootstrap_status_api_endpoint)
        try:
            api_request = self.get(
                'internal', bootstrap_status_api_endpoint, timeout=timeout, authentication=False)

        except APICallException:
            # if connection failed, then try to reconnect on the IPv4 address of one of the nodes
            ipv4_conn = Connect(node_ip=ipv4_addr, api_token='abcd')
            api_request = ipv4_conn.get(
                'internal', bootstrap_status_api_endpoint, timeout=timeout, authentication=False)
            return api_request

        return api_request

    @staticmethod
    def log(log_message):
        """Create properly formatted debug log messages.

        Arguments:
            log_message {str} - - The message to pass to the debug log.
        """
        log = logging.getLogger(__name__)
        log.debug(log_message)

    def _header(self):
        """Internal method used to create the a header without authorization used in the API calls.

        Returns:
            dict - - The header that does not include any authorization.
        """

        user_agent = "RubrikPythonSDK--{}--{}".format(
            self.sdk_version, self.python_version)
        if self.platform != "":
            user_agent = user_agent + '--' + self.platform

        if self.ipv6_addr != "":
            header = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': user_agent,
                'Host': '[' + self.ipv6_addr + ']',
                'rk-integration': self.function_name

            }
        else:
            header = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': user_agent,
                'rk-integration': self.function_name

            }

        self.log("Header: {}".format(header))
        return header

    @staticmethod
    def _api_validation(api_version, api_endpoint):
        """Internal method used to validate the API Version and API Endpoint provided by the end user

        Arguments:
            api_version {str} - - The version of the Rubrik CDM API to call.
            api_endpoint {str} - - The endpoint(ex. cluster / me) of the Rubrik CDM API to call.
        """

        valid_api_versions = ['v1', 'internal']

        # Validate the API Version
        if api_version not in valid_api_versions:
            raise InvalidParameterException(
                "Enter a valid API version {}.".format(valid_api_versions))

        # Validate the API Endpoint Syntax
        if not isinstance(api_endpoint, str):
            raise InvalidTypeException("The API Endpoint must be a string.")
        elif api_endpoint[0] != "/":
            raise InvalidParameterException(
                "The API Endpoint should begin with '/'. (ex: /cluster/me)")
        elif api_endpoint[-1] == "/":
            if api_endpoint[-2] != "=":
                raise InvalidParameterException(
                    "Error: The API Endpoint should not end with '/' unless proceeded by '='. (ex. /cluster/me or /fileset/snapshot/<id>/browse?path=/)")
