try:
    from tempfile import TemporaryDirectory
except Exception:
    from backports.tempfile import TemporaryDirectory

from unittest import TestCase
import subprocess
import sys

from mkpkg._cli import Path


class TestMkpkg(TestCase):
    def test_it_creates_packages_that_pass_their_own_initial_tests(self):
        root = self.mkpkg("foo")
        with open(str(root / "foo" / "README.rst"), "a") as readme:
            readme.write("Some description.\n")
        subprocess.check_call(
            [sys.executable, "-m", "tox", "--skip-missing-interpreters"],
            cwd=str(root / "foo"),
        )

    def test_it_creates_single_modules_that_pass_their_own_initial_tests(self):
        root = self.mkpkg("foo", "--single")
        with open(str(root / "foo" / "README.rst"), "a") as readme:
            readme.write("Some description.\n")
        subprocess.check_call(
            [sys.executable, "-m", "tox", "--skip-missing-interpreters"],
            cwd=str(root / "foo"),
        )

    def test_it_creates_clis(self):
        foo = self.mkpkg("foo", "--cli", "bar") / "bar"
        cli = foo / "foo" / "_cli.py"
        cli.write_text(
            cli.read_text().replace(
                "def main():\n    pass",
                "def main():\n    click.echo('hello')",
            ),
        )
        venv = self.venv(foo)
        self.assertEqual(
            subprocess.check_output([str(venv / "bin" / "bar")]),
            "hello\n",
        )

    def test_it_creates_main_py_files_for_single_clis(self):
        foo = self.mkpkg("foo", "--cli", "foo") / "foo"
        cli = foo / "foo" / "_cli.py"
        cli.write_text(
            cli.read_text().replace(
                "def main():\n    pass",
                "def main():\n    click.echo('hello')",
            ),
        )
        venv = self.venv(foo)
        self.assertEqual(
            subprocess.check_output(
                [str(venv / "bin" / "python"), "-m", "foo"],
            ),
            "hello\n",
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

    def venv(self, package):
        venv = package / "venv"
        subprocess.check_call(
            [sys.executable, "-m", "virtualenv", str(venv)],
        )
        subprocess.check_call(
            [str(venv / "bin"/ "python"), "-m", "pip", "install", str(package)]
        )
        return venv
