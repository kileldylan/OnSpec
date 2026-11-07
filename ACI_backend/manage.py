#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))


def main():
    """Run administrative tasks."""
    test_settings_explicit = any(
        argument == "--settings" or argument.startswith("--settings=")
        for argument in sys.argv[2:]
    )
    if (
        len(sys.argv) > 1
        and sys.argv[1] == "test"
        and not test_settings_explicit
        and "DJANGO_SETTINGS_MODULE" not in os.environ
    ):
        os.environ["DJANGO_SETTINGS_MODULE"] = "ACI_backend.test_settings"
    else:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ACI_backend.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
