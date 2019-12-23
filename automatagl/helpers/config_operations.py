import logging
import os
import re
import sys
import yaml
import boto3

from pathlib import Path
from automatagl.helpers.gitlab_operations import GitlabServerConfig, GitlabGroupConfig
from automatagl.helpers.github_operations import GithubServerConfig


# Dictionary to translate logging levels in the config file
log_level_dict = {
    "info": logging.INFO,
    "warning": logging.WARN,
    "debug": logging.DEBUG,
}


class ConfigOps:
    """
    Responsible for parsing the configuration file for information relating to automata.
    """

    filename: str
    raw_config: dict
    gitlab_config: dict
    github_config: dict
    logging_config: dict
    api_token_env: str

    def __init__(self, filename: str, api_token_env: str = 'GL_API_TOKEN') -> None:
        """
        :param filename: Configuration file name
        :param api_token_env: Gitlab API token environment variable.
        """
        self.filename = filename
        self.raw_config = self.__import_config(filename)
        self.gitlab_config = self.raw_config['gitlab']['server']
        self.github_config = self.raw_config['github']['server']
        self.logging_config = self.raw_config['logging']
        self.api_token_env = api_token_env

    def get_logging_config(self) -> dict:
        """
        Returns the logging configuration contained in the `raw_config` variable after some massaging.
        :return: LoggingConfig object
        :raises COInvalidLogLevel: Thrown if log level isn't defined in the log level dictionary.
        """
        if self.logging_config["log_level"] not in log_level_dict.keys():
            raise COInvalidLogLevel
        return {
            "level": log_level_dict[self.logging_config['log_level']],
            "filename": self.logging_config['log_path'],
            "format": self.logging_config['log_format'],
        }

    def get_gitlab_config(self) -> GitlabServerConfig:
        """
        Returns the Gitlab configuration object for the GitlabOps
        :return: GitlabServerConfig object
        """
        # Get Gitlab Group information
        gitlab_group_data = list()
        group_info = self.raw_config['gitlab']['groups']
        for k, v in group_info.items():
            try:
                other_groups = v['other_groups']
            except KeyError:
                other_groups = list()
            temp = GitlabGroupConfig(
                gitlab_group=k,
                linux_group=v['linux_group'],
                sudoers_line=sanitize_sudoers_line(v['sudoers_line']),
                other_groups=other_groups,
                get_users_from_group=v['get_users_from_group']
            )
            gitlab_group_data.append(temp)

        # Token information
        try:
            if "SSM" in self.gitlab_config['api_token']:
                gl_token = self.gitlab_config['api_token']
                gl_ssm = boto3.client('ssm')
                gl_data = gl_token.split(':')
                gl_param = gl_data[1]
                gl_parameter = gl_ssm.get_parameter(Name=param,WithDecryption=True)
                token_info = gl_parameter['Parameter']['Value']
            else:
                token_info = self.gitlab_config['api_token']
        except KeyError:
            token_info = os.environ.get(self.api_token_env)

        # Protected UID/GID Processing
        try:
            protected_uid_start = self.gitlab_config['protected_uid_start']
        except KeyError:
            protected_uid_start = 1000
        try:
            protected_gid_start = self.gitlab_config['protected_gid_start']
        except KeyError:
            protected_gid_start = 1000

        # Gitlab Server config information
        return GitlabServerConfig(
            address=self.gitlab_config['api_address'],
            token=token_info,
            groups=gitlab_group_data,
            sudoers_file=self.gitlab_config['sudoers_file'],
            home_dir_path=self.gitlab_config['home_dir_path'],
            protected_uid_start=protected_uid_start,
            protected_gid_start=protected_gid_start,
            instance_project=self.gitlab_config['instance_list_project'],
            instance_file=self.gitlab_config['instance_file_list'],
        )

    def get_github_config(self) -> GithubServerConfig:
        """
        Returns the Github configuration object for the GithubOps
        :return: GithubServerConfig object
        """
        # Token information
        try:
            if "SSM" in self.github_config['api_token']:
                gh_token = self.github_config['api_token']
                gh_ssm = boto3.client('ssm')
                gh_data = gh_token.split(':')
                gh_param = gh_data[1]
                gh_parameter = gh_ssm.get_parameter(Name=param,WithDecryption=True)
                token_info = gh_parameter['Parameter']['Value']
            else:
                token_info = self.github_config['api_token']
        except KeyError:
            token_info = os.environ.get(self.api_token_env)

        # Github Server config information
        return GithubServerConfig(
            address=self.github_config['api_address'],
            token=token_info,
        )

    @staticmethod
    def __import_config(filename: str) -> dict:
        """
        Parses the configuration file
        :param filename: The file to parse the configuration from
        :return: The contents of the configuration file after being parsed.
        """
        path = Path(filename)
        perms = path.stat().st_mode
        if bool(perms % 0o100):
            print("WARNING: The permissions on '{}' must be set to restrict access from all users. Consider changing "
                  "the permissions to 400 or more secure.".format(filename))
            sys.exit(15)
        with open(filename, 'r') as stream:
            try:
                return yaml.safe_load(stream)
            except yaml.YAMLError as exc:
                print(exc)


def sanitize_username(username: str) -> str:
    """
    Remove non-word characters from a username
    :param username: The username to sanitize
    :return: The sanitized username
    """
    illegal_chars = r'[^\w]'
    return re.sub(illegal_chars, '_', username)


def sanitize_sudoers_line(sudoers_line: str) -> str:
    """
    Sanitize the sudoers file line
    :param sudoers_line: The line of the sudoers file
    :return: The sanitized sudoers file line
    """
    illegal_chars = r'\s+'
    return re.sub(illegal_chars, ' ', sudoers_line)


class COError(Exception):
    pass


class COInvalidLogLevel(COError):
    pass
