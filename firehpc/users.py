#!/usr/bin/env python3
#
# Copyright (C) 2023 Rackslab
#
# This file is part of FireHPC.
#
# FireHPC is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FireHPC is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FireHPC.  If not, see <https://www.gnu.org/licenses/>.

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


class UsersDirectory:
    def __init__(self, size: int, cluster: str) -> UsersDirectory:
        self.size = size
        self.db = list()
        fake = Faker()
        self.db = [
            UserEntry(fake.first_name(), fake.last_name(), cluster)
            for _ in range(self.size)
        ]

    def __iter__(self):
        for user in self.db:
            yield user

    def _generic(self):
        return [user._generic() for user in self.db]

    @classmethod
    def load(cls, cluster: str, users: list) -> UsersDirectory:
        directory = cls(0, cluster)
        for user in users:
            directory.db.append(UserEntry.load(cluster, user))
        return directory
