# Copyright (c) 2023-22024 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations
from dataclasses import dataclass

from faker import Faker


@dataclass
class UserEntry:
    firstname: str
    lastname: str
    cluster: str

    @property
    def login(self):
        return f"{self.firstname.lower()[0]}{self.lastname.lower()}"

    @property
    def email(self):
        return f"{self.firstname.lower()}.{self.lastname.lower()}@{self.cluster}.hpc"

    def _generic(self):
        return {
            "login": self.login,
            "firstname": self.firstname,
            "lastname": self.lastname,
            "email": self.email,
        }

    @classmethod
    def load(cls, cluster: str, user: dict) -> UserEntry:
        return cls(user["firstname"], user["lastname"], cluster)


@dataclass
class GroupEntry:
    name: str
    members: list[UserEntry]
    parent: str = "root"

    def _generic(self):
        return {
            "name": self.name,
            "members": [member.login for member in self.members],
            "parent": self.parent,
        }

    @classmethod
    def load(cls, directory: UsersDirectory, group: dict) -> GroupEntry:
        return cls(
            group["name"],
            [directory.user(member) for member in group["members"]],
            group["parent"],
        )


class UsersDirectory:
    def __init__(self, size: int, cluster: str) -> UsersDirectory:
        self.size = size
        self.users = list()
        self.groups = list()
        fake = Faker()
        self.users = [
            UserEntry(fake.first_name(), fake.last_name(), cluster)
            for _ in range(self.size)
        ]
        if size > 4:
            self.groups = [
                GroupEntry("scientists", self.users),
                GroupEntry("admin", self.users[0:1]),
                GroupEntry("biology", self.users[1 : int(size / 2)]),
                GroupEntry("physic", self.users[int(size / 2) : size]),
                GroupEntry(
                    "acoustic",
                    self.users[int(size / 2) : int(size / 2) + int(size / 4) + 1],
                    "physic",
                ),
                GroupEntry(
                    "optic",
                    self.users[int(size / 2) + int(size / 4) + 1 : size],
                    "physic",
                ),
            ]

    def __iter__(self):
        for user in self.users:
            yield user

    def user(self, login):
        for user in self:
            if user.login == login:
                return user

    def _users_generic(self):
        return [user._generic() for user in self.users]

    def _groups_generic(self):
        return [group._generic() for group in self.groups]

    @classmethod
    def load(cls, cluster: str, users: list, groups: list) -> UsersDirectory:
        directory = cls(0, cluster)
        for user in users:
            directory.users.append(UserEntry.load(cluster, user))
        for group in groups:
            directory.groups.append(GroupEntry.load(directory, group))
        return directory
