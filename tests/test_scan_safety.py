"""Worker lifecycle and resource-bound regression tests."""
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.models.scan_job import ScanJobDB
from backend.services import scan_control
from scanner import main as scanner_main
from scanner.main import scan_with_metrics


class ScanLimitTests(unittest.TestCase):
    def test_source_profile_excludes_virtual_environment_directories_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('import hashlib\nhashlib.sha256(b"x")')
            for name in ('.venv', 'venv', 'env', '.pytest_cache', '.mypy_cache', '.ruff_cache'):
                dependency = root / name
                dependency.mkdir()
                (dependency / 'dependency.py').write_text('import hashlib\nhashlib.md5(b"x")')
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop('ECDAT_SCAN_PROFILE', None)
                evidence, metrics = scan_with_metrics(directory)
            self.assertEqual(metrics['total_files'], 1)
            self.assertEqual(metrics['in_scope_files'], 1)
            self.assertEqual({item['algorithm'] for items in evidence.values() for item in items},
                             {'SHA-256'})

    def test_environment_profile_includes_virtual_environment_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            site_packages = Path(directory) / '.venv' / 'Lib' / 'site-packages'
            site_packages.mkdir(parents=True)
            (site_packages / 'dependency.py').write_text('import hashlib\nhashlib.md5(b"x")')
            with patch.dict(os.environ, {'ECDAT_SCAN_PROFILE': 'environment'}):
                evidence, metrics = scan_with_metrics(directory)
            self.assertEqual(metrics['in_scope_files'], 1)
            self.assertEqual({item['algorithm'] for items in evidence.values() for item in items},
                             {'MD5'})

    def test_unreadable_directory_fails_inventory_instead_of_overstating_coverage(self):
        def inaccessible_walk(_root, onerror=None):
            if onerror is not None:
                onerror(PermissionError('private path must not be exposed'))
            return
            yield  # pragma: no cover - keeps this a generator

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(scanner_main.os, 'walk', inaccessible_walk):
            with self.assertRaisesRegex(OSError, 'inventory repository tree') as raised:
                scan_with_metrics(directory)
        self.assertNotIn('private path', str(raised.exception))

    def test_failure_paths_encode_api_unsafe_filename_characters(self):
        with tempfile.TemporaryDirectory() as directory:
            unsafe = os.path.join(directory, 'unsafe:name.py')
            self.assertEqual(scanner_main._relative_failure_path(directory, unsafe),
                             'unsafe%3Aname.py')

    def test_aggregate_evidence_limit_fails_instead_of_returning_partial_results(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / 'many.py').write_text(
                'import hashlib\nhashlib.sha256(b"x")\nhashlib.md5(b"x")\n'
            )
            with patch.dict(os.environ, {'ECDAT_MAX_EVIDENCE': '1'}):
                with self.assertRaisesRegex(ValueError, 'evidence count limit'):
                    scan_with_metrics(directory)

    def test_unknown_scan_profile_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'ECDAT_SCAN_PROFILE': 'typo'}):
            with self.assertRaisesRegex(ValueError, 'Invalid ECDAT_SCAN_PROFILE'):
                scan_with_metrics(directory)

    def test_oversized_supported_file_is_failed_three_times(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'large.py'
            path.write_text('import hashlib\nhashlib.sha256(b"x")\n' + ' ' * 200)
            with patch.dict(os.environ, {'ECDAT_MAX_FILE_BYTES': '64'}):
                for _ in range(3):
                    evidence, metrics = scan_with_metrics(directory)
                    self.assertEqual(evidence, {})
                    self.assertEqual(metrics['failed_files'], 1)
                    self.assertEqual(metrics['coverage_pct'], 0.0)

    def test_file_count_limit_rejects_before_collection(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(3):
                (Path(directory) / f'{index}.py').write_text('x=1')
            with patch.dict(os.environ, {'ECDAT_MAX_SCAN_FILES': '2'}):
                with self.assertRaisesRegex(ValueError, 'file count limit'):
                    scan_with_metrics(directory)

    def test_linked_file_is_not_read(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.py'
            link = Path(directory) / 'link.py'
            source.write_text('import hashlib\nhashlib.md5(b"x")')
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest('Creating symlinks is unavailable')
            evidence, metrics = scan_with_metrics(directory)
            self.assertTrue(evidence)  # regular source remains scanned
            self.assertEqual(metrics['failed_files'], 1)


class ScanControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / 'worker.db'
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        (self.repo / 'app.py').write_text('import hashlib\nhashlib.sha256(b"x")')
        self.engine = create_engine('sqlite:///' + self.database.as_posix())
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session_patch = patch.object(scan_control, 'SessionLocal', self.Session)
        self.session_patch.start()
        self.environment = patch.dict(os.environ, {
            'DATABASE_URL': 'sqlite:///' + self.database.as_posix(),
            'ECDAT_SCAN_TIMEOUT_SECONDS': '2',
            'ECDAT_MAX_FILE_BYTES': '1024',
            'ECDAT_MAX_SCAN_FILES': '100',
        })
        self.environment.start()
        scan_control._active = None

    def tearDown(self):
        active = scan_control._active
        if active is not None:
            active.cancel.set()
        self.environment.stop()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def job(self):
        with self.Session() as db:
            job = ScanJobDB(repo_path=str(self.repo), status='queued')
            db.add(job); db.commit(); db.refresh(job)
            return job.id

    def control(self, timeout=10):
        control = scan_control.reserve()
        control.timeout = timeout
        control.scan_id = self.job()
        return control

    def status(self, scan_id):
        with self.Session() as db:
            return db.get(ScanJobDB, scan_id).status

    def test_successful_child_scan_isolated_and_repeatable(self):
        for _ in range(3):
            control = self.control()
            scan_control.supervise(str(self.repo), control)
            self.assertEqual(self.status(control.scan_id), 'completed')
            self.assertIsNone(scan_control._active)

    def test_timeout_kills_worker_and_releases_slot(self):
        control = self.control(timeout=1)
        with patch.object(scan_control, 'worker_command', return_value=[
                sys.executable, '-c', 'import time;time.sleep(20)']):
            started = time.monotonic()
            scan_control.supervise(str(self.repo), control)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(self.status(control.scan_id), 'timed_out')
        replacement = scan_control.reserve()
        scan_control.release(replacement)

    def test_cancel_kills_worker_and_releases_slot(self):
        control = self.control(timeout=10)
        started = threading.Event()
        real_popen = subprocess.Popen
        def launch(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            started.set()
            return process
        with patch.object(scan_control, 'worker_command', return_value=[
                sys.executable, '-c', 'import time;time.sleep(20)']), \
             patch.object(scan_control.subprocess, 'Popen', side_effect=launch):
            thread = threading.Thread(target=scan_control.supervise,
                                      args=(str(self.repo), control))
            thread.start()
            self.assertTrue(started.wait(2))
            scan_control.request_cancel(control.scan_id)
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.status(control.scan_id), 'cancelled')
        self.assertIsNone(scan_control._active)

    def test_launch_failure_terminates_job_and_releases_slot(self):
        control = self.control()
        with patch.object(scan_control.subprocess, 'Popen', side_effect=OSError()):
            scan_control.supervise(str(self.repo), control)
        self.assertEqual(self.status(control.scan_id), 'failed')
        self.assertIsNone(scan_control._active)

    def test_termination_failure_still_finalizes_job_and_releases_slot(self):
        class UnstoppableProcess:
            def poll(self):
                return None

            def kill(self):
                raise OSError('termination failed')

            def wait(self, timeout=None):
                raise AssertionError('wait should not follow a failed kill')

        control = self.control(timeout=0)
        with patch.object(scan_control.subprocess, 'Popen', return_value=UnstoppableProcess()):
            scan_control.supervise(str(self.repo), control)
        self.assertEqual(self.status(control.scan_id), 'failed')
        self.assertIsNone(scan_control._active)

    def test_one_active_scan_is_atomic(self):
        barrier, accepted, rejected = threading.Barrier(4), [], []
        def compete():
            barrier.wait()
            try:
                accepted.append(scan_control.reserve())
            except Exception as exc:
                rejected.append(exc)
        threads = [threading.Thread(target=compete) for _ in range(3)]
        for thread in threads: thread.start()
        barrier.wait()
        for thread in threads: thread.join()
        self.assertEqual((len(accepted), len(rejected)), (1, 2))
        scan_control.release(accepted[0])

    def test_invalid_limits_fail_closed(self):
        for key, value in [('ECDAT_SCAN_TIMEOUT_SECONDS', '0'),
                           ('ECDAT_MAX_FILE_BYTES', 'no'),
                           ('ECDAT_MAX_SCAN_FILES', '1000001')]:
            with patch.dict(os.environ, {key: value}):
                with self.assertRaisesRegex(Exception, 'Invalid scan limit'):
                    scan_control.reserve()

    def test_submission_database_failure_releases_slot(self):
        from fastapi import BackgroundTasks
        from backend.routers import scan
        with patch.object(scan, 'resolve_repository', return_value=str(self.repo)), \
             patch.object(scan, 'SessionLocal', side_effect=RuntimeError('database unavailable')):
            with self.assertRaises(RuntimeError):
                scan.post_scan(scan.ScanRequest(repo_path=str(self.repo)), BackgroundTasks(), 'admin')
        self.assertIsNone(scan_control._active)

    def test_cancel_api_auth_roles_and_terminal_states(self):
        from fastapi import FastAPI, Depends
        from fastapi.testclient import TestClient
        from backend.routers import scan
        from backend.security import current_role
        app = FastAPI()
        app.include_router(scan.router, dependencies=[Depends(current_role)])
        control = self.control()
        with patch.object(scan, 'SessionLocal', self.Session), \
             patch.object(scan, 'record_audit'), \
             patch.dict(os.environ, {'ECDAT_ALLOW_ROLE_HEADER': 'false'}), TestClient(app) as client:
            path = f'/api/scans/{control.scan_id}/cancel'
            self.assertEqual(client.post(path).status_code, 401)
            app.dependency_overrides[current_role] = lambda: 'viewer'
            self.assertEqual(client.post(path).status_code, 403)
            self.assertFalse(control.cancel.is_set())
            app.dependency_overrides[current_role] = lambda: 'admin'
            self.assertEqual(client.post('/api/scans/999999/cancel').status_code, 404)
            self.assertEqual(client.post(path).status_code, 202)
            self.assertTrue(control.cancel.is_set())
            scan_control.supervise(str(self.repo), control)
            self.assertEqual(self.status(control.scan_id), 'cancelled')
            self.assertEqual(client.post(path).status_code, 409)

    def test_completed_result_is_not_overwritten_by_late_cancellation(self):
        control = self.control()
        with self.Session() as db:
            db.get(ScanJobDB, control.scan_id).status = 'completed'
            db.commit()
        scan_control.request_cancel(control.scan_id)
        scan_control.supervise(str(self.repo), control)
        self.assertEqual(self.status(control.scan_id), 'completed')
        self.assertIsNone(scan_control._active)
