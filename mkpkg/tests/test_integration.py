try:
    from tempfile import TemporaryDirectory
except Exception:
    from backports.tempfile import TemporaryDirectory

from unittest import TestCase
import subprocess
import sys

from mkpkg._cli import Path


class TestMkpkg(TestCase):
    def test_it_creates_packages_that_pass_their_tests(self):
        root = self.mkpkg("foo")
        _fix_readme(root / "foo")
        self.assertToxSucceeds(root / "foo", "--skip-missing-interpreters")

    def test_it_creates_packages_with_docs_that_pass_their_tests(self):
        root = self.mkpkg("mkpkg", "--docs")
        _fix_readme(root / "mkpkg")
        self.assertToxSucceeds(root / "mkpkg", "--skip-missing-interpreters")

    def test_it_creates_single_modules_that_pass_their_tests(self):
        root = self.mkpkg("foo", "--single")
        _fix_readme(root / "foo")
        self.assertToxSucceeds(root / "foo", "--skip-missing-interpreters")

    def test_it_creates_cffi_packages_that_pass_their_tests(self):
        root = self.mkpkg("foo", "--cffi")
        _fix_readme(root / "foo")
        self.assertToxSucceeds(root / "foo", "--skip-missing-interpreters")

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

    def test_default_tox_envs(self):
        envlist = self.tox(self.mkpkg("foo") / "foo", "-l").stdout
        self.assertEqual(
            set(envlist.splitlines()),
            {
                b"py37-build",
                b"py37-audit",
                b"py37-tests",
                b"py38-build",
                b"py38-audit",
                b"py38-tests",
                b"py39-build",
                b"py39-audit",
                b"py39-tests",
                b"py310-build",
                b"py310-audit",
                b"py310-tests",
                b"py311-build",
                b"py311-audit",
                b"py311-tests",
                b"pypy3-build",
                b"pypy3-audit",
                b"pypy3-tests",
                b"readme",
                b"secrets",
                b"style",
            },
        )

    def test_docs_tox_envs(self):
        envlist = self.tox(self.mkpkg("foo", "--docs") / "foo", "-l").stdout
        self.assertEqual(
            set(envlist.splitlines()),
            {
                b"py37-build",
                b"py37-audit",
                b"py37-tests",
                b"py38-build",
                b"py38-audit",
                b"py38-tests",
                b"py39-build",
                b"py39-audit",
                b"py39-tests",
                b"pypy3-build",
                b"pypy3-audit",
                b"pypy3-tests",
                b"readme",
                b"secrets",
                b"style",
                b"docs-dirhtml",
                b"docs-doctest",
                b"docs-linkcheck",
                b"docs-spelling",
                b"docs-style",
            },
        )

    def test_it_runs_style_checks_by_default(self):
        root = self.mkpkg("foo")
        envlist = self.tox(root / "foo", "-l").stdout
        self.assertIn(b"style", envlist)

    def test_it_runs_style_checks_when_explicitly_asked(self):
        root = self.mkpkg("foo", "--style")
        envlist = self.tox(root / "foo", "-l").stdout
        self.assertIn(b"style", envlist)

    def test_it_skips_style_checks_when_asked(self):
        root = self.mkpkg("foo", "--no-style")
        envlist = self.tox(root / "foo", "-l").stdout
        self.assertNotIn(b"style", envlist)

    def assertToxSucceeds(self, *args, **kwargs):
        try:
            self.tox(*args, **kwargs)
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
            [sys.executable, "-m", "mkpkg"] + list(argv),
            cwd=directory.name,
            env=dict(
                GIT_AUTHOR_NAME="mkpkg unittests",
                GIT_AUTHOR_EMAIL="mkpkg-unittests@local",
                GIT_COMMITTER_NAME="mkpkg unittests",
                GIT_COMMITTER_EMAIL="mkpkg-unittests@local",
            ),
            stdout=subprocess.DEVNULL,
            check=True,
        )
        return Path(directory.name)

    def tox(self, path, *argv):
        return subprocess.run(
            [
                sys.executable, "-m", "tox",
                "-c", str(path / "tox.ini"),
                "-p", "auto",
                "--workdir", str(path / "tox-work-dir"),
            ] + list(argv),
            check=True,
            capture_output=True,
        )

    def venv(self, package):
        venv = package / "venv"
        subprocess.run(
            [sys.executable, "-m", "virtualenv", "--quiet", str(venv)],
            check=True,
        )
        subprocess.run(
            [
                str(venv / "bin" / "python"), "-m", "pip",
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
        readme.write(u"\n\nSome description.\n")
