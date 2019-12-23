#! /usr/bin/env python2

from datetime import datetime
import configparser
import io
import os
import pwd
import sys
import subprocess
import textwrap

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

import click
import jinja2

from mkpkg import __version__


STATUS_CLASSIFIERS = {
    "planning": "Development Status :: 1 - Planning",
    "prealpha": "Development Status :: 2 - Pre-Alpha",
    "alpha": "Development Status :: 3 - Alpha",
    "beta": "Development Status :: 4 - Beta",
    "stable": "Development Status :: 5 - Production/Stable",
    "mature": "Development Status :: 6 - Mature",
    "inactive": "Development Status :: 7 - Inactive",
}
VERSION_CLASSIFIERS = {
    "pypy2": "Programming Language :: Python :: 2.7",
    "pypy3": "Programming Language :: Python :: 3.6",

    "py27": "Programming Language :: Python :: 2.7",
    "py35": "Programming Language :: Python :: 3.5",
    "py36": "Programming Language :: Python :: 3.6",
    "py37": "Programming Language :: Python :: 3.7",
    "py38": "Programming Language :: Python :: 3.8",
    "py39": "Programming Language :: Python :: 3.9",

    "jython": "Programming Language :: Python :: 2.7",
}
TRAVIS_SUPPORTS = {
    "py27": "2.7",
    "py35": "3.5",
    "py36": "3.6",
    "py37": "3.7",
    "py38": "3.8",
    "py39": "3.9",
}
TEST_DEPS = {
    "py.test": ["pytest"],
    "trial": ["twisted"],
}


def dedented(*args, **kwargs):
    return textwrap.dedent(*args, **kwargs).lstrip("\n")


@click.command()
@click.argument("name")
@click.option(
    "--author",
    default=pwd.getpwuid(os.getuid()).pw_gecos.partition(",")[0],
    help="the name of the package author",
)
@click.option(
    "--author-email",
    default=None,
    help="the package author's email",
)
@click.option(
    "-c",
    "--cli",
    multiple=True,
    help="include a CLI in the resulting package with the given name",
)
@click.option(
    "--readme",
    default="",
    help="a (rst) README for the package",
)
@click.option(
    "-t",
    "--test-runner",
    default="trial",
    type=click.Choice(["pytest", "trial"]),
    help="the test runner to use",
)
@click.option(
    "-s",
    "--supports",
    multiple=True,
    type=click.Choice(sorted(VERSION_CLASSIFIERS)),
    default=["py36", "py37", "py38", "pypy2", "pypy3"],
    help="a version of Python supported by the package",
)
@click.option(
    "--status",
    type=click.Choice(STATUS_CLASSIFIERS),
    default="alpha",
    help="the initial package development status",
)
@click.option(
    "--docs/--no-docs",
    default=False,
    help="generate a Sphinx documentation template for the new package",
)
@click.option(
    "--single",
    "--no-package",
    "single_module",
    is_flag=True,
    default=False,
    help="create a single module rather than a package.",
)
@click.option(
    "--bare/--no-bare",
    "bare",
    default=False,
    help="only create the core source files.",
)
@click.option(
    "--cffi/--no-cffi",
    default=False,
    help="include a build script for CFFI modules",
)
@click.option(
    "--style/--no-style",
    "style",
    default=True,
    help="(don't) run pyflakes by default in tox runs.",
)
@click.option(
    "--init-vcs/--no-init-vcs",
    default=True,
    help="don't initialize a VCS.",
)
@click.option(
    "--closed/--open",
    default=False,
    help="create a closed source package.",
)
@click.version_option(prog_name="mkpkg", version=__version__)
def main(
    name,
    author,
    author_email,
    cffi,
    cli,
    readme,
    test_runner,
    supports,
    status,
    docs,
    single_module,
    bare,
    style,
    init_vcs,
    closed,
):
    """
    Oh how exciting! Create a new Python package.
    """

    if name.startswith("python-"):
        package_name = name[len("python-"):]
    else:
        package_name = name
    package_name = package_name.lower().replace("-", "_")

    env = jinja2.Environment(
        loader=jinja2.PackageLoader("mkpkg", "template"),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.globals.update(
        author=author,
        cffi=cffi,
        cli=cli,
        closed=closed,
        docs=docs,
        name=name,
        now=datetime.now(),
        package_name=package_name,
        single_module=single_module,
        style=style,
        supports=supports,
        test_runner=test_runner,
    )

    package = Path(package_name)

    if single_module:
        tests = u"{toxinidir}/tests.py"

        if len(cli) > 1:
            sys.exit("Cannot create a single module with multiple CLIs.")
        elif cli:
            console_scripts = [u"{} = {}:main".format(cli[0], package_name)]
            script = env.get_template("package/_cli.py.j2").render(
                program_name=cli[0],
            )
        else:
            console_scripts = []
            script = u""

        core_source_paths = {
            package_name + ".py": script,
            "tests.py": env.get_template("tests.py.j2").render(),
        }

    else:
        tests = package_name

        core_source_paths = {
            package / "tests" / "__init__.py": u"",
            package / "__init__.py": env.get_template(
                "package/__init__.py.j2",
            ).render(),
        }

        if cffi:
            core_source_paths[package / "_build.py"] = env.get_template(
                "package/_build.py.j2",
            ).render(cname=_cname(name))

        if len(cli) == 1:
            console_scripts = [
                "{} = {}._cli:main".format(cli[0], package_name),
            ]
            core_source_paths[package / "_cli.py"] = env.get_template(
                "package/_cli.py.j2",
            ).render(program_name=cli[0])
            core_source_paths[package / "__main__.py"] = env.get_template(
                "package/__main__.py.j2",
            ).render()
        else:
            console_scripts = [
                "{each} = {package_name}._{each}:main".format(
                    each=each, package_name=package_name,
                ) for each in cli
            ]
            core_source_paths.update(
                (
                    package / ("_" + each + ".py"),
                    env.get_template("package/_cli.py.j2").render(
                        program_name=each,
                    ),
                ) for each in cli
            )

    files = {
        "README.rst": env.get_template("README.rst.j2").render(
            contents=readme,
        ),
        "COPYING": env.get_template("COPYING.j2").render(),
        "MANIFEST.in": template("MANIFEST.in"),
        "pyproject.toml": template("pyproject.toml"),
        "setup.cfg": env.get_template("setup.cfg.j2").render(
            console_scripts=console_scripts,
            author_email=(
                author_email or u"Julian+" + package_name + u"@GrayVines.com"
            ),
            status_classifier=STATUS_CLASSIFIERS[status],
            version_classifiers={
                VERSION_CLASSIFIERS[each]
                for each in supports
                if each in VERSION_CLASSIFIERS
            },
            py2=any(
                version.startswith("py2")
                or version in {"jython", "pypy2"}
                for version in supports
            ),
            py3=any(
                version.startswith("py3")
                or version == "pypy3"
                for version in supports
            ),
            cpython=any(
                version not in {"jython", "pypy2", "pypy3"}
                for version in supports
            ),
            pypy="pypy2" in supports or "pypy3" in supports,
            jython="jython" in supports,
        ),
        "setup.py": env.get_template("setup.py.j2").render(),
        ".coveragerc": env.get_template(".coveragerc.j2").render(),
        "tox.ini": env.get_template("tox.ini.j2").render(
            test_deps=TEST_DEPS[test_runner],
            tests=tests,
        ),
        ".testr.conf": template(".testr.conf"),
        Path(".github") / "workflows" / "packaging.yml": template(
            ".github/workflows/packaging.yml"
        ),
    }

    if not closed:
        files.update(
            {
                ".travis.yml": env.get_template(".travis.yml.j2").render(
                    travis_supports=sorted(
                        TRAVIS_SUPPORTS.get(each, each)
                        for each in supports
                    ),
                ),
                "codecov.yml": template("codecov.yml"),
            },
        )

    root = Path(name)
    if bare:
        targets = core_source_paths
    else:
        files.update(core_source_paths)
        targets = files
        root.mkdir()

    for path, content in targets.items():
        path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedented(content))

    if docs:
        (root / "docs").mkdir()
        (root / "docs" / "requirements.txt").write_text(
            template("docs", "requirements.txt"),
        )

        subprocess.check_call(
            [
                sys.executable,
                "-m", "sphinx.cmd.quickstart",
                "--quiet",
                "--project", name,
                "--author", author,
                "--release", "",
                "--ext-autodoc",
                "--ext-coverage",
                "--ext-doctest",
                "--ext-intersphinx",
                "--ext-viewcode",
                "--extensions", "sphinx.ext.napoleon",
                "--extensions", "sphinxcontrib.spelling",
                "--makefile",
                "--no-batchfile",
                str(root / "docs"),
            ],
        )
        (root / "docs" / "index.rst").write_text(template("docs", "index.rst"))

        click.echo(
            "Set up documentation at: https://readthedocs.org/dashboard/import/manual/",
        )

    if init_vcs and not bare:
        subprocess.check_call(["git", "init", "--quiet", name])

        git_dir = root / ".git"
        subprocess.check_call(
            [
                "git",
                "--git-dir", str(git_dir),
                "--work-tree", name,
                "add", "COPYING",
            ])
        subprocess.check_call(
            [
                "git",
                "--git-dir", str(git_dir),
                "commit", "--quiet", "-m", "Initial commit",
            ],
        )

        if not closed:
            click.echo("Set up CI at: https://travis-ci.com/Julian/" + name)


def template(*segments):
    path = Path(__file__).with_name("template").joinpath(*segments)
    return path.read_text()


def _cname(name):
    if name.endswith("-cffi"):
        name = name[:-len("-cffi")]
    if name.startswith("lib"):
        name = name[len("lib"):]
    return "_" + name
