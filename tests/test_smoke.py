"""Sanity check — pytest can discover and run tests in this repo."""


def test_pytest_runs():
    assert 1 + 1 == 2


def test_python_version():
    import sys
    assert sys.version_info >= (3, 11)
