import json
import os
import requests
from collections import namedtuple
from typing import List

__all__ = [
    'GithubOps',
    'GithubServerConfig',
    'GHConnectionError',
    'GHApiQueryError',
]

# Quick structures for holding config information (readability)
GithubUser = namedtuple('GithubUser', ['id', 'username'])
GithubServerConfig = namedtuple("GithubServerConfig", ['address', 'token'])


class GithubOps:
    """
    This module handles all of the communications for users and groups in Github.
    """

    api_token: str
    api_address: str
    payload_params: dict

    def __init__(self,
                 api_token: str,
                 api_address: str) -> None:
        """
        :param api_token: The Github API authentication token for access
        :param api_address: The address of the Github server
        """
        self.api_token = api_token
        self.api_address = api_address
        self.payload_token = {
            'private_token': self.api_token,
        }

    def get_users_from_group(self, group: str, only_active: bool = True) -> List[GithubUser]:
        """
        Get all users from a Github Group
        :param group: The group name in Github
        :param only_active: Whether to pull all users or only the active ones in Github
        :return: A GithubUser object with the user information
        """
        path = os.path.join(self.api_address, 'teams/{}/members'.format(group))
        response = self.process_response_from_server(path)
        if only_active:
            members = [GithubUser(id=i['id'], username=i['username']) for i in response if i['state'] == 'active']
        else:
            members = [GithubUser(id=i['id'], username=i['username']) for i in response]
        return members

    def get_id_from_username(self, user_name: str) -> List[GithubUser]:
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
            path = os.path.join(self.api_address, 'users/{}'.format(user))
            response = self.process_response_from_server(path)
            response.update(login=ssh_name)
            res.append(response)
        members = [GithubUser(id=i['id'], username=i['login']) for i in res]
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

    def process_response_from_server(self, path) -> List[dict]:
        """
        Performs queries to the Github server and process the response for common errors/issues
        :param path: The path to query
        :return: The response object
        :raises GHApiQueryError: On any errors returned by the GL server query
        :raises GHConnectionError: On any connection issues with the GL server
        """
        gh_header = {'Accept': 'application/vnd.github.v3+json'}
        try:
            response = json.loads(requests.get(path, headers=gh_header, params=self.payload_token).text)
        except requests.exceptions.ConnectionError:
            raise GHConnectionError
        if type(response) is dict:
            if "error" in response.keys():
                raise GHApiQueryError(message=response["error_description"])
            elif "message" in response.keys():
                raise GHApiQueryError(response["message"])
        return response


class GHError(Exception):
    pass


class GHConnectionError(GHError):
    pass


class GHApiQueryError(GHError):

    def __init__(self, message):
        self.message = message
