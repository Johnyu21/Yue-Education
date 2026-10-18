"""Launcher regression tests, without connecting to a database or installing packages."""
import contextlib
import importlib.util
import io
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('setup_project', Path(__file__).resolve().parents[1] / 'setup_project.py')
setup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yue checkout 中文 ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in setup.REQUIRED:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('{}' if name.endswith('.json') else 'fixture', encoding='utf-8')
        self.backend = self.root / 'backend'
        self.frontend = self.root / 'frontend'
        (self.backend / '.env.example').write_text(
            'POSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=education\n'
            'POSTGRES_USER=education\nPOSTGRES_PASSWORD=replace-with-strong-password\n'
            'JWT_SECRET=replace-with-random-secret-at-least-32-characters\n', encoding='utf-8')
        values = {'ROOT': self.root, 'BACKEND': self.backend, 'FRONTEND': self.frontend,
                  'VENV': self.backend / '.venv', 'PYTHON': self.backend / '.venv/Scripts/python.exe',
                  'LOGS': self.backend / 'logs', 'STAMP': self.backend / 'logs/local-setup.json'}
        for name, value in values.items():
            mock = patch.object(setup, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        output = contextlib.redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def configure(self):
        (self.backend / '.env').write_text(
            'POSTGRES_HOST=localhost\nPOSTGRES_PORT=5432\nPOSTGRES_DB=education\n'
            'POSTGRES_USER=education\nPOSTGRES_PASSWORD=fixture-only-password\n'
            'JWT_SECRET=fixture-only-secret-12345678901234567890\n', encoding='utf-8')

    def test_fresh_checkout_generates_private_config_but_never_overwrites_it(self):
        self.assertTrue(setup.ensure_env())
        content = (self.backend / '.env').read_text(encoding='utf-8')
        self.assertNotIn('JWT_SECRET=replace-', content)
        self.assertIn('POSTGRES_PASSWORD=replace-', content)
        self.assertFalse(setup.ensure_env())
        self.assertEqual(content, (self.backend / '.env').read_text(encoding='utf-8'))
        self.assertEqual(['请填写 POSTGRES_PASSWORD'], setup.config_problems())

    def test_missing_repository_worker_is_reported(self):
        (self.root / 'tools/frontend_dev_runner.cjs').unlink()
        with self.assertRaisesRegex(RuntimeError, 'frontend_dev_runner.cjs'):
            setup.check_files()

    def test_check_is_read_only_on_fresh_checkout(self):
        with patch.object(setup, 'node_commands', return_value=('node', 'npm')):
            with self.assertRaisesRegex(RuntimeError, '.venv'):
                setup.check()
        self.assertFalse((self.backend / '.env').exists())
        self.assertFalse((self.backend / '.venv').exists())

    def test_fresh_checkout_creates_venv_and_installs_both_lockfiles(self):
        self.configure()
        with patch.object(setup, 'node_commands', return_value=('node', 'npm.cmd')), \
             patch.object(setup, 'python_ready', return_value=False), \
             patch.object(setup, 'dependencies_ready', return_value=True), \
             patch.object(setup, 'run') as run, patch.object(setup.subprocess, 'run') as npm:
            setup.prepare()
        commands = [' '.join(map(str, call.args[0])) for call in run.call_args_list]
        self.assertTrue(any('-m venv' in command for command in commands))
        self.assertTrue(any('requirements.lock.txt' in command for command in commands))
        self.assertEqual(['npm.cmd', 'ci', '--no-audit', '--no-fund'], npm.call_args.args[0])
        self.assertEqual(self.frontend, npm.call_args.kwargs['cwd'])
        self.assertEqual({'backend', 'frontend'}, set(setup.read_stamp()))
        self.assertFalse(any('migrate' in command or 'seed' in command for command in commands))

    def test_unchanged_dependencies_are_reused(self):
        self.configure()
        vite = self.frontend / 'node_modules/vite/dist/node/index.js'
        vite.parent.mkdir(parents=True)
        vite.touch()
        setup.write_stamp({'backend': setup.digest(self.backend / 'requirements.lock.txt'),
                           'frontend': setup.digest(self.frontend / 'package.json', self.frontend / 'package-lock.json')})
        with patch.object(setup, 'node_commands', return_value=('node', 'npm')), \
             patch.object(setup, 'python_ready', return_value=True), \
             patch.object(setup, 'dependencies_ready', return_value=True), \
             patch.object(setup, 'run') as run, patch.object(setup.subprocess, 'run') as npm:
            setup.prepare()
        run.assert_not_called()
        npm.assert_not_called()

    def test_failed_install_is_not_marked_complete(self):
        self.configure()
        with patch.object(setup, 'node_commands', return_value=('node', 'npm')), \
             patch.object(setup, 'python_ready', return_value=True), \
             patch.object(setup, 'run', side_effect=subprocess.CalledProcessError(1, ['pip'])):
            with self.assertRaises(subprocess.CalledProcessError):
                setup.prepare()
        self.assertEqual({}, setup.read_stamp())

    def test_changed_lockfile_triggers_reinstall(self):
        self.configure()
        setup.write_stamp({'backend': 'old-version', 'frontend': 'old-version'})
        with patch.object(setup, 'node_commands', return_value=('node', 'npm')), \
             patch.object(setup, 'python_ready', return_value=True), \
             patch.object(setup, 'dependencies_ready', return_value=True), \
             patch.object(setup, 'run') as run, patch.object(setup.subprocess, 'run') as npm:
            setup.prepare()
        self.assertTrue(any('requirements.lock.txt' in str(c.args[0]) for c in run.call_args_list))
        npm.assert_called_once()

    @unittest.skipUnless(os.name == 'nt', 'Windows CMD entry')
    def test_cmd_entry_works_in_checkout_with_spaces_and_chinese(self):
        source = Path(__file__).resolve().parents[2]
        for name in ('一键准备环境.cmd', 'tools/project_entry.cmd', 'tools/setup_project.py'):
            (self.root / name).write_bytes((source / name).read_bytes())
        env = os.environ.copy()
        env.update(YUE_NO_PAUSE='1', YUE_PYTHON=sys.executable)
        result = subprocess.run([str(self.root / '一键准备环境.cmd'), '--help'],
                                cwd=self.root, env=env, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn('--no-browser', result.stdout)
        self.assertFalse((self.backend / '.venv').exists())

    def test_broken_venv_is_not_deleted(self):
        self.configure()
        setup.VENV.mkdir()
        marker = setup.VENV / 'keep.txt'
        marker.write_text('keep')
        with patch.object(setup, 'node_commands', return_value=('node', 'npm')), \
             patch.object(setup, 'python_ready', return_value=False):
            with self.assertRaisesRegex(RuntimeError, '项目外备份'):
                setup.prepare()
        self.assertEqual('keep', marker.read_text())


if __name__ == '__main__':
    unittest.main()
