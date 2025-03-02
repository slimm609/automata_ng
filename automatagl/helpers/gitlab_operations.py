import json
import os
import requests
import base64
from collections import namedtuple
from typing import List

__all__ = [
    'GitlabOps',
    'GitlabGroupConfig',
    'GitlabServerConfig',
    'GLConnectionError',
    'GLApiQueryError',
]

# Quick structures for holding config information (readability)
GitlabUser = namedtuple('GitlabUser', ['id', 'username'])
GitlabGroupConfig = namedtuple("GitlabGroupConfig", ['gitlab_group', 'linux_group', 'sudoers_line', 'other_groups', 'get_users_from_group'])
GitlabServerConfig = namedtuple(
    "GitlabServerConfig", [
        'address',
        'token',
        'groups',
        'sudoers_file',
        'home_dir_path',
        'protected_uid_start',
        'protected_gid_start',
        'instance_file',
        'instance_project'
    ]
)


class GitlabOps:
    """
    This module handles all of the communications for users and groups in Gitlab.
    """

    api_token: str
    api_address: str
    payload_params: dict

    def __init__(self,
                 api_token: str,
                 api_address: str) -> None:
        """
        :param api_token: The Gitlab API authentication token for access
        :param api_address: The address of the Gitlab server
        """
        self.api_token = api_token
        self.api_address = api_address
        self.payload_token = {
            'private_token': self.api_token,
        }

    def get_users_from_group(self, group: str, only_active: bool = True) -> List[GitlabUser]:
        """
        Get all users from a Gitlab Group
        :param group: The group name in Gitlab
        :param only_active: Whether to pull all users or only the active ones in Gitlab
        :return: A GitlabUser object with the user information
        """
        path = os.path.join(self.api_address, 'groups/{}/members'.format(group))
        response = self.process_response_from_server(path)
        if only_active:
            members = [GitlabUser(id=i['id'], username=i['username']) for i in response if i['state'] == 'active']
        else:
            members = [GitlabUser(id=i['id'], username=i['username']) for i in response]
        return members

    def get_id_from_username(self, user_name: str) -> List[GitlabUser]:
        """
        Get the ID of a user based on a username
        :param user_name: The username of the Gitlab User
        :return: the id of the user
        """
        res = []
        for user in user_name:
            if ":" in user:
                data = user.split(':')
                user = data[0]
                ssh_name = data[1]
            else:
                ssh_name = user
            path = os.path.join(self.api_address, 'users/?username={}'.format(user))
            response = self.process_response_from_server(path)
            for el in response:
                el.update(username=ssh_name)
                res.append(el)
        members = [GitlabUser(id=i['id'], username=i['username']) for i in res]
        return members

    def get_keys_from_user_id(self, user_id: int) -> list:
        """
        Get all SSH public keys associated with a given user ID.
        :param user_id: The user ID to query
        :return: A list of SSH public keys associated with the user ID.
        """
        path = os.path.join(self.api_address, 'users/{}/keys'.format(user_id))
        response = self.process_response_from_server(path)
        keys = [i["key"] for i in response]
        return keys

    def get_file_from_project(self, project_id: int, file_path: str):
        """
        Get a file from the gitlab server and return the content.
        :param project_id: The gitlab project id for the file
        :param file_path: The file in the repo that needs to be pulled
        """
        path = os.path.join(self.api_address, 'projects/{}/repository/files/{}?ref=master'.format(project_id, file_path))
        response = self.process_response_from_server(path)
        content = base64.b64decode(response['content'])
        return content

    def process_response_from_server(self, path) -> List[dict]:
        """
        Performs queries to the Gitlab server and process the response for common errors/issues
        :param path: The path to query
        :return: The response object
        :raises GLApiQueryError: On any errors returned by the GL server query
        :raises GLConnectionError: On any connection issues with the GL server
        """
        try:
            response = json.loads(requests.get(path, params=self.payload_token).text)
        except requests.exceptions.ConnectionError:
            raise GLConnectionError
        if type(response) is dict:
            if "error" in response.keys():
                raise GLApiQueryError(message=response["error_description"])
            elif "message" in response.keys():
                raise GLApiQueryError(response["message"])
        return response


class GLError(Exception):
    pass


class GLConnectionError(GLError):
    pass


class GLApiQueryError(GLError):

    def __init__(self, message):
        self.message = message
