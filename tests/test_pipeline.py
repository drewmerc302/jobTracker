from unittest.mock import patch, MagicMock
import pytest

from src.pipeline import parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.dry_run is False
    assert args.renotify is False
    assert args.step is None


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_step():
    args = parse_args(["--step", "scrape"])
    assert args.step == "scrape"
