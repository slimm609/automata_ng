#!/usr/bin/env python3

import logging
import os
import sys
import yaml

from automatagl.helpers.config_operations import ConfigOps, sanitize_username
from automatagl.helpers.ssh_key_object import SSHKeyObject
from automatagl.helpers.user_operations import *
from automatagl.helpers.gitlab_operations import *
from automatagl.helpers.github_operations import *
from automatagl.helpers.instance_id_object import *


def main():

    working_dir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(working_dir)

    # Grab configuration information
    config_ops = ConfigOps(filename='/etc/automata/automata.conf')

    # Logging configuration
    logging_config = config_ops.get_logging_config()
    logging.basicConfig(**logging_config)

    # Gitlab API and group information
    gitlab_config = config_ops.get_gitlab_config()
    gitlab_ops = GitlabOps(api_token=gitlab_config.token, api_address=gitlab_config.address)
    
    # Github API access
    github_config = config_ops.get_github_config()
    github_ops = GithubOps(api_token=github_config.token, api_address=github_config.address)
    
    # Instance ID
    instance_ops = InstanceIDObject()

    # Set host environment and user operations stuff
    default_shell = '/bin/bash'
    host_env = os.environ.copy()
    host_env["PATH"] = "/bin:/sbin:/usr/bin:/usr/sbin" + host_env["PATH"]
    user_ops = UserOps(
        host_env=host_env,
        default_shell=default_shell,
        base_dir=gitlab_config.home_dir_path,
        protected_uid_start=gitlab_config.protected_uid_start,
        protected_gid_start=gitlab_config.protected_gid_start,
    )

    # Get all members of a given group
    logging.debug("Processing {} groups from the config file.".format(len(gitlab_config.groups)))

    # Create a cache of created users.
    finished_users = list()

    # Start by parsing each group.
    for group in gitlab_config.groups:
        logging.debug("Querying users in group '{}'.".format(group.gitlab_group))
        if group.get_users_from_group == True:
            gl_members = gitlab_ops.get_users_from_group(group.gitlab_group)
            gh_members = [] 
        else:
            gh_list = []
            gl_list = []
            instance_yaml = gitlab_ops.get_file_from_project(gitlab_config.instance_project, gitlab_config.instance_file)
            try:
                instance_list = yaml.safe_load(instance_yaml)
            except yaml.YAMLError as exc:
                print(exc)
            instance_id = instance_ops.find_instance_id()
            if instance_id is not None:
                for key, value in instance_list.items():
                    if instance_id == key:
                        for name in value:
                            if "Github" in name:
                                gh_list.append(str(name[7:]))
                            else:
                                gl_list.append(name)
            gh_members = github_ops.get_id_from_username(gh_list)
            gl_members = gitlab_ops.get_id_from_username(gl_list)

        # Get associated SSH keys for members
        ssh_list = list()
        for gl_member in gl_members:
            ssh_obj = SSHKeyObject(username=gl_member.username)
            logging.debug("Querying user SSH key information for {}.".format(gl_member.username))
            keys = gitlab_ops.get_keys_from_user_id(gl_member.id)
            ssh_obj.add_keys(keys)
            ssh_list.append(ssh_obj)
        
        for gh_member in gh_members:
            ssh_obj = SSHKeyObject(username=gh_member.username)
            logging.debug("Querying user SSH key information for {}.".format(gh_member.username))
            keys = github_ops.get_keys_from_user_id(gh_member.username)
            ssh_obj.add_keys(keys)
            ssh_list.append(ssh_obj)

        # Get list of user accounts in the group from the '/etc/group' file
        try:
            linux_group_id = user_ops.get_group_gid(group.linux_group)
        except UOGroupNotFoundError:
            logging.info("Group not found, creating the '{}' group.".format(group.linux_group))
            user_ops.create_group(group.linux_group)
        finally:
            linux_group_id = user_ops.get_group_gid(group.linux_group)

        # Start removing users with extreme prejudice that are no longer in the GitLab group.
        current_users = user_ops.get_all_users_in_group(linux_group_id)
        gitlab_users = set([sanitize_username(i.username) for i in ssh_list])
        removed_users = current_users - gitlab_users
        if len(removed_users) > 0:
            logging.info("Found {} users to delete in group {}: {}".format(
                len(removed_users),
                group.linux_group,
                ', '.join(removed_users),
            ))
        else:
            logging.info("No users to delete in group {}.".format(group.linux_group))

        # Deleting users that have been removed
        for user in removed_users:
            logging.info("Deleting user {}.".format(user))
            try:
                user_ops.delete_user(user)
            except UOProtectedUserError:
                logging.info("Cannot delete user '{}' as it is a protected system user.".format(user))
                sys.exit(101)

        # Create new users in group
        created_users = gitlab_users - current_users
        if len(created_users) > 0:
            logging.info("Found {} users to create in group {}: {}".format(
                len(created_users),
                group.linux_group,
                ', '.join(created_users),
            ))
        else:
            logging.info("No users to add to group {}.".format(group.linux_group))

        for user in created_users:
            if user not in set(finished_users):
                logging.info("Creating user {}.".format(user))
                user_data = {
                    "user": user,
                    "group": group.linux_group,
                    "groups": group.other_groups,
                }
                try:
                    user_ops.create_user(**user_data)
                except UOUserAlreadyExistsError:
                    logging.info("User '{}' already exists, deleting user.".format(user))
                    try:
                        user_ops.delete_user(user)
                    except UOProtectedUserError:
                        logging.info("Cannot delete user '{}' as it is a protected system user.".format(user))
                        sys.exit(101)
                    logging.info("Recreating user '{}'.".format(user))
                    user_ops.create_user(**user_data)
            else:
                logging.info("Skipping user {}, handled previously in another group.".format(user))

        # Create the SSH authorized_keys file so the user can actually log in.
        for ssh_keys in ssh_list:
            user_ops.populate_ssh_file(
                ssh_keys=ssh_keys,
                gid=linux_group_id,
            )

        # Add users to the finished_users table
        finished_users = list(set(gitlab_users).union(finished_users))
        logging.debug("Finished users list now contains {} members.".format(len(finished_users)))

    # Create the sudoers.d file.
    logging.info("Regenerating the '{}' file.".format(gitlab_config.sudoers_file))
    user_ops.generate_sudoers_file(gitlab_config.sudoers_file, gitlab_config.groups)
