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

import jinja2


class Templater:
    """Class to abstract backend templating library."""

    def __init__(self):
        # Enable trim_blocks and lstrip_blocks in template as it is easier to
        # add spaces (or disable them occasionnaly in templates) than removing
        # them, and it is usually the expected behaviour with templates blocks.
        # Also keep trailing newline in EOF to avoid breaking prompt with cat.
        self.env = jinja2.Environment(
            trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True
        )

    def srender(self, str, **kwargs):
        """Render a string template."""
        try:
            return self.env.from_string(str).render(kwargs)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise RuntimeError(f"Unable to render template string {str}: {err}")

    def frender(self, path, **kwargs):
        """Render a file template."""
        self.env.loader = jinja2.FileSystemLoader(path.parent)
        try:
            return self.env.get_template(path.name).render(kwargs)
        except jinja2.exceptions.TemplateSyntaxError as err:
            raise RuntimeError(f"Unable to render template file {path}: {err}")
