"""Tests never inherit the caller's saved configuration.

The app falls back to os.environ for the research root, the modelling Python, the database path and the
GenAI settings and key (GenAI settings are read at call time). A developer machine may have these saved
permanently, so every test that builds an app calls unconfigured(self) first: for the length of the test
those variables are absent and the app config falls back to unset. Tests that need a setting set it
explicitly on app.config or with patch.dict.
"""
import os
from unittest.mock import patch

PREFIXES = ('TXB_',)
NAMES = ('GEMINI_API_KEY', 'GOOGLE_API_KEY', 'CHURN_DB_PATH')


def configuration_name(name):
    return name.upper() in NAMES or name.upper().startswith(PREFIXES)


def unconfigured(test):
    kept = {name: value for name, value in os.environ.items() if not configuration_name(name)}
    patcher = patch.dict(os.environ, kept, clear=True)
    patcher.start()
    test.addCleanup(patcher.stop)
