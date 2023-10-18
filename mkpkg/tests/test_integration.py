from tempfile import TemporaryDirectory
from unittest import TestCase
import json
import os
import subprocess
import sys

from mkpkg._cli import Path


class TestMkpkg(TestCase):
    def test_it_creates_packages_that_pass_their_tests(self):
        root = self.mkpkg("foo")
        _fix_readme(root / "foo")
        self.assertNoxSucceeds(root / "foo")

    def test_it_creates_packages_with_docs_that_pass_their_tests(self):
        root = self.mkpkg("foo", "--docs")
        _fix_readme(root / "foo")
        self.assertNoxSucceeds(root / "foo")

    def test_it_creates_single_modules_that_pass_their_tests(self):
        root = self.mkpkg("foo", "--single")
        _fix_readme(root / "foo")
        self.assertNoxSucceeds(root / "foo")

    def test_it_creates_cffi_packages_that_pass_their_tests(self):
        root = self.mkpkg("foo", "--cffi")
        _fix_readme(root / "foo")
        self.assertNoxSucceeds(root / "foo")

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

    def test_default_envs(self):
        envlist = self.envs(self.mkpkg("foo") / "foo")
        self.assertEqual(
            envlist,
            {
                "tests-3.10",
                "tests-3.11",
                "tests-3.12",
                "tests-pypy3.10",
                "audit-3.10",
                "audit-3.11",
                "audit-3.12",
                "audit-pypy3.10",
                "build",
                "secrets",
                "style",
                "typing",
            },
        )

    def test_docs_envs(self):
        envlist = self.envs(self.mkpkg("foo", "--docs") / "foo")
        self.assertEqual(
            envlist,
            {
                "tests-3.10",
                "tests-3.11",
                "tests-3.12",
                "tests-pypy3.10",
                "audit-3.10",
                "audit-3.11",
                "audit-3.12",
                "audit-pypy3.10",
                "build",
                "secrets",
                "style",
                "typing",
                "docs(dirhtml)",
                "docs(doctest)",
                "docs(linkcheck)",
                "docs(man)",
                "docs(spelling)",
                "docs(style)",
            },
        )

    def test_it_runs_style_checks_by_default(self):
        envlist = self.envs(self.mkpkg("foo") / "foo")
        self.assertIn("style", envlist)

    def test_it_runs_style_checks_when_explicitly_asked(self):
        envlist = self.envs(self.mkpkg("foo", "--style") / "foo")
        self.assertIn("style", envlist)

    def test_it_skips_style_checks_when_asked(self):
        envlist = self.envs(self.mkpkg("foo", "--no-style") / "foo")
        self.assertNotIn("style", envlist)

    def assertNoxSucceeds(self, *args, **kwargs):
        try:
            self.nox(*args, **kwargs)
        except subprocess.CalledProcessError as error:
            if error.stdout:
                sys.stdout.buffer.write(b"\nStdout:\n\n")
                sys.stdout.buffer.write(error.stdout)
            if error.stderr:
                sys.stderr.buffer.write(b"\nStderr:\n\n")
                sys.stderr.buffer.write(error.stderr)
            self.fail(error)

    def mkpkg(self, *argv):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        subprocess.run(
            [sys.executable, "-m", "mkpkg", *argv],
            cwd=directory.name,
            env=dict(
                GIT_AUTHOR_NAME="mkpkg unittests",
                GIT_AUTHOR_EMAIL="mkpkg-unittests@local",
                GIT_COMMITTER_NAME="mkpkg unittests",
                GIT_COMMITTER_EMAIL="mkpkg-unittests@local",
                PATH=os.environ.get("PATH", ""),  # needed to find e.g. git
            ),
            stdout=subprocess.DEVNULL,
            check=True,
        )
        return Path(directory.name)

    def nox(self, path, *argv):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "nox",
                "--noxfile",
                str(path / "noxfile.py"),
                "--envdir",
                str(path / "nox-env-dir"),
                *argv,
            ],
            check=True,
            capture_output=True,
        )

    def envs(self, path):
        output = self.nox(path, "--list-sessions", "--json").stdout
        return {each["session"] for each in json.loads(output)}

    def venv(self, package):
        venv = package / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        subprocess.run(
            [
                str(venv / "bin" / "python"),
                "-m",
                "pip",
                "install",
                "--quiet",
                str(package),
            ],
            check=True,
        )
        return venv


def _fix_readme(path):
    # Just the heading on the readme isn't good enough...
    with (path / "README.rst").open("at") as readme:
        readme.write("\n\nSome description.\n")
