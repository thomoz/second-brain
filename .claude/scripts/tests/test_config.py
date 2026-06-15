"""Tests for config.py — ensures path constants are absolute and CWD-independent."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config


def test_project_root_is_absolute():
    assert config.PROJECT_ROOT.is_absolute()


def test_vault_dir_is_absolute():
    assert config.VAULT_DIR.is_absolute()


def test_data_dir_is_absolute():
    assert config.DATA_DIR.is_absolute()


def test_state_dir_is_absolute():
    assert config.STATE_DIR.is_absolute()


def test_daily_dir_is_absolute():
    assert config.DAILY_DIR.is_absolute()


def test_state_dir_child_of_project_root():
    assert str(config.STATE_DIR).startswith(str(config.PROJECT_ROOT))


def test_vault_dir_child_of_project_root():
    assert str(config.VAULT_DIR).startswith(str(config.PROJECT_ROOT))


def test_data_dir_child_of_project_root():
    assert str(config.DATA_DIR).startswith(str(config.PROJECT_ROOT))
