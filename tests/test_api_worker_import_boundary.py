import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from api.routers import pipeline


ROOT = Path(__file__).resolve().parents[1]

HEAVY_WORKER_MODULES = (
    "workers.tasks",
    "workers.pipeline",
    "workers.scrapers.jobs",
    "workers.celery_app",
    "celery.result",
)


class ApiWorkerImportBoundaryTests(
    unittest.TestCase
):
    def test_database_queue_is_default_backend(
        self,
    ):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            self.assertEqual(
                pipeline._execution_backend(),
                pipeline.DATABASE_BACKEND,
            )

    def test_legacy_celery_backend_remains_available(
        self,
    ):
        with patch.dict(
            os.environ,
            {
                "MONITORING_EXECUTION_BACKEND":
                    "celery",
            },
        ):
            self.assertEqual(
                pipeline._execution_backend(),
                pipeline.CELERY_BACKEND,
            )

    def test_api_import_does_not_load_worker_runtime(
        self,
    ):
        module_names = repr(
            HEAVY_WORKER_MODULES
        )

        script = f"""
import sys
import api.main

names = {module_names}
loaded = [
    name
    for name in names
    if name in sys.modules
]

print("LOADED=" + ",".join(loaded))
"""

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            check=True,
        )

        marker = next(
            line
            for line in result.stdout.splitlines()
            if line.startswith("LOADED=")
        )

        self.assertEqual(
            marker,
            "LOADED=",
            result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
