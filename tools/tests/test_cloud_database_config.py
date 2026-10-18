"""Configuration regression checks; no database connection is opened."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
with patch.dict(os.environ, {'POSTGRES_PASSWORD': 'fixture-only-password'}, clear=True):
    from app.core.config import Settings


class CloudConfigTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_defaults_match_cloud_business_database_template(self):
        settings = Settings(_env_file=None, postgres_password='fixture-only-password')
        from dotenv import dotenv_values
        template = dotenv_values(ROOT / 'backend/.env.example')
        for name in ('host', 'port', 'user', 'db'):
            self.assertEqual(str(getattr(settings, 'postgres_' + name)), template['POSTGRES_' + name.upper()])
        self.assertEqual(settings.postgres_port, 5433)
        self.assertEqual(settings.postgres_db, 'yue_education')

    def test_local_database_overrides_remain_supported(self):
        settings = Settings(_env_file=None, postgres_host='localhost', postgres_port=5432,
                            postgres_db='education_test', postgres_user='fixture', postgres_password='fixture')
        self.assertEqual(settings.postgres_host, 'localhost')
        self.assertEqual(settings.postgres_port, 5432)

    def test_dify_system_databases_and_missing_password_are_rejected(self):
        for db in ('dify', 'dify_plugin', 'postgres', 'template0', 'template1'):
            with self.subTest(database=db), self.assertRaises(ValueError):
                Settings(_env_file=None, postgres_db=db, postgres_password='fixture-only-password')
        for password in ('', 'replace-with-password'):
            with self.subTest(password_kind='empty-or-placeholder'), self.assertRaises(ValueError):
                Settings(_env_file=None, postgres_password=password)

    def test_connection_url_preserves_special_password_characters(self):
        from sqlalchemy.engine import make_url
        password = 'fixture@:#/%?with spaces'
        settings = Settings(_env_file=None, postgres_password=password)
        parsed = make_url(settings.database_url)
        self.assertEqual(parsed.password, password)
        self.assertEqual(parsed.database, 'yue_education')


if __name__ == '__main__':
    unittest.main()
