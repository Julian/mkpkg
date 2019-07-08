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
        with (root / "foo" / "README.rst").open("at") as readme:
            readme.write(u"Some description.\n")
        subprocess.check_call(
            [sys.executable, "-m", "tox", "--skip-missing-interpreters"],
            cwd=str(root / "foo"),
        )

    def test_it_creates_single_modules_that_pass_their_own_initial_tests(self):
        root = self.mkpkg("foo", "--single")
        with (root / "foo" / "README.rst").open("at") as readme:
            readme.write(u"Some description.\n")
        subprocess.check_call(
            [sys.executable, "-m", "tox", "--skip-missing-interpreters"],
            cwd=str(root / "foo"),
        )

    def test_it_creates_clis(self):
        foo = self.mkpkg("foo", "--cli", "bar") / "foo"
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
            b"hello\n",
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
            b"hello\n",
        )

    def test_program_names_are_correct(self):
        venv = self.venv(self.mkpkg("foo", "--cli", "foo") / "foo")
        version = subprocess.check_output(
            [str(venv / "bin" / "python"), "-m", "foo", "--version"],
        )
        self.assertTrue(version.startswith(b"foo"))

    def test_it_runs_style_checks_by_default(self):
        root = self.mkpkg("foo")
        envlist = subprocess.check_output(
            [sys.executable, "-m", "tox", "-l"],
            cwd=str(root / "foo"),
        )
        self.assertIn(b"style", envlist)

    def test_it_runs_style_checks_when_explicitly_asked(self):
        root = self.mkpkg("foo", "--style")
        envlist = subprocess.check_output(
            [sys.executable, "-m", "tox", "-l"],
            cwd=str(root / "foo"),
        )
        self.assertIn(b"style", envlist)

    def test_it_skips_style_checks_when_asked(self):
        root = self.mkpkg("foo", "--no-style")
        envlist = subprocess.check_output(
            [sys.executable, "-m", "tox", "-l"],
            cwd=str(root / "foo"),
        )
        self.assertNotIn(b"style", envlist)

    def test_it_initializes_a_vcs_by_default(self):
        root = self.mkpkg("foo")
        self.assertTrue((root / "foo" / ".git").is_dir())

    def test_it_initializes_a_vcs_when_explicitly_asked(self):
        root = self.mkpkg("foo", "--init-vcs")
        self.assertTrue((root / "foo" / ".git").is_dir())

    def test_it_skips_vcs_when_asked(self):
        root = self.mkpkg("foo", "--no-init-vcs")
        self.assertFalse((root / "foo" / ".git").is_dir())

    def test_it_skips_vcs_when_bare(self):
        root = self.mkpkg("foo", "--bare")
        self.assertFalse((root / "foo" / ".git").is_dir())

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
            [
                str(venv / "bin" / "python"), "-m", "pip",
                "install",
                str(package),
            ]
        )
        return venv
