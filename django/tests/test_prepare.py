from pathlib import Path

current_dir = Path(__file__).parent.resolve()

from src.prepare import init_django_settings_env

def test_init_django_settings_env():

    not_valid

    assert False
