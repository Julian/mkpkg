try:
    from tempfile import TemporaryDirectory
    from pathlib import Path
except Exception:
    from backports.tempfile import TemporaryDirectory
    from pathlib2 import Path

from unittest import TestCase
import subprocess
import sys


class TestMkpkg(TestCase):
    def test_it_creates_packages_that_pass_their_own_initial_tests(self):
        root = self.mkpkg("foo")
        subprocess.check_call(
            [sys.executable, "-m", "tox", "--skip-missing-interpreters"],
            cwd=str(root / "foo"),
        )

    def mkpkg(self, *argv):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        subprocess.check_call(
            [sys.executable, "-m", "mkpkg"] + list(argv),
            cwd=directory.name,
            env=dict(
                GIT_AUTHOR_NAME="mkpkg unittests",
                GIT_AUTHOR_EMAIL="mkpkg-unittests@local",
                GIT_COMMITTER_NAME="mkpkg unittests",
                GIT_COMMITTER_EMAIL="mkpkg-unittests@local",
            ),
        )
        return Path(directory.name)
