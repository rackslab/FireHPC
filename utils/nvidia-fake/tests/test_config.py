# Copyright (c) 2026 Rackslab
#
# This file is part of FireHPC.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import pytest

from firehpc_nvidia_fake.config import ConfigError, load_config, parse_config


def test_load(config_file):
    config = load_config(str(config_file))
    assert config.flavor == "4.8.4"
    assert config.driver_version == "570.86.15"
    assert [gpu.index for gpu in config.gpus] == [0, 1, 2]
    assert config.gpus[0].memory_bytes == 81559 * 2**20
    assert config.gpus[2].device == "nvidia2"


def test_defaults():
    config = parse_config({})
    assert config.gpus == []
    assert config.flavor == "4.8.4"


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="unable to read"):
        load_config(str(tmp_path / "missing.json"))


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{")
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_config(str(path))


def test_invalid_flavor(config_data):
    config_data["flavor"] = "5.0"
    with pytest.raises(ConfigError, match="unsupported flavor"):
        parse_config(config_data)


def test_missing_key(config_data):
    del config_data["gpus"][1]["uuid"]
    with pytest.raises(ConfigError, match="GPU #1: missing key uuid"):
        parse_config(config_data)


def test_bool_rejected(config_data):
    config_data["gpus"][0]["memory_mib"] = True
    with pytest.raises(ConfigError, match="invalid value for memory_mib"):
        parse_config(config_data)


def test_index_position(config_data):
    config_data["gpus"][1]["index"] = 5
    with pytest.raises(ConfigError, match="does not match its position"):
        parse_config(config_data)


def test_duplicate_uuid(config_data):
    config_data["gpus"][1]["uuid"] = config_data["gpus"][0]["uuid"]
    with pytest.raises(ConfigError, match="unique"):
        parse_config(config_data)


def test_power_bounds(config_data):
    config_data["gpus"][0]["power_idle_w"] = 800
    with pytest.raises(ConfigError, match="power_idle_w"):
        parse_config(config_data)
