#! /usr/bin/env python2

import ConfigParser
import argparse
import datetime
import errno
import io
import os
import pwd
import sys
import subprocess
import textwrap


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
    "py27": "Programming Language :: Python :: 2.7",
    "py35": "Programming Language :: Python :: 3.5",
    "py36": "Programming Language :: Python :: 3.6",
    "py37": "Programming Language :: Python :: 3.7",
    "py38": "Programming Language :: Python :: 3.8",
    "py39": "Programming Language :: Python :: 3.9",
}


def dedented(*args, **kwargs):
    return textwrap.dedent(*args, **kwargs).lstrip("\n")


parser = argparse.ArgumentParser(
    description="Oh how exciting! Create a new Python package.",
)
parser.add_argument("name", help="the package name")
parser.add_argument(
    "--single", "--no-package",
    action="store_true",
    dest="single_module",
    help="create a single module rather than a package",
)
parser.add_argument(
    "-B", "--bare",
    action="store_true",
    help="only create the core source files",
)
parser.add_argument(
    "--author",
    default=pwd.getpwuid(os.getuid()).pw_gecos.partition(",")[0],
    help="the name of the package author",
)
parser.add_argument(
    "--author-email",
    default=None,
    help="the package author's email",
)
parser.add_argument(
    "--status",
    choices=STATUS_CLASSIFIERS,
    default="alpha",
    help="the initial package development status",
)
parser.add_argument(
    "-S", "--no-style",
    action="store_false",
    dest="style",
    help="Don't run pyflakes by default in tox runs.",
)
parser.add_argument(
    "-V", "--no-sensibility",
    action="store_false",
    dest="sensible",
    help="Don't initialize a VCS.",
)
parser.add_argument(
    "-c", "--cli",
    action="append",
    help="include a CLI in the resulting package with the given name",
    default=[],
)
parser.add_argument(
    "-s", "--supports",
    action="append",
    help="a version of Python supported by the package",
    choices=sorted(VERSION_CLASSIFIERS) + ["jython", "pypy"],
    default=["py27", "py36", "py37", "pypy"],
)
parser.add_argument(
    "-t", "--test-runner",
    help="the test runner to use",
    choices=["pytest", "trial"],
    default="trial",
)
parser.add_argument(
    "--closed",
    action="store_true",
    help="A closed source package.",
)
parser.add_argument(
    "--readme",
    default="",
    help="a (rst) README for the package",
)
parser.add_argument(
    "--docs", "--no-docs",
    action="store_true",
    help="generate a Sphinx documentation template for the new package",
)


def main():
    def root(*segments):
        return os.path.join(name, *segments)

    def package(*segments):
        return os.path.join(package_name, *segments)

    def _script(name):
        return """
        import click

        from {} import __version__


        @click.command()
        @click.version_option(version=__version__)
        def main():
            pass
        """.format(package_name)

    arguments = parser.parse_args()
    name = arguments.name

    if name.startswith("python-"):
        package_name = name[len("python-"):]
    else:
        package_name = name
    package_name = package_name.lower().replace("-", "_")

    if arguments.single_module:
        contents = "py_modules", name
        tests = "tests.py"

        if len(arguments.cli) > 1:
            sys.exit("Cannot create a single module with multiple CLIs.")
        elif arguments.cli:
            console_scripts = [
                "{} = {}:main".format(arguments.cli[0], package_name),
            ]
            script = """
            import click


            @click.command()
            def main():
                pass
            """
        else:
            console_scripts = []
            script = ""

        core_source_paths = {
            package_name + ".py": script,
            "tests.py": """
            from unittest import TestCase

            import {package_name}


            class Test{name}(TestCase):
                pass
            """.format(name=name.title(), package_name=package_name),
        }

    else:
        contents = "packages", "find:"
        tests = package_name

        core_source_paths = {
            package("tests", "__init__.py"): "",
            package("__init__.py"): """
            from pkg_resources import get_distribution, DistributionNotFound
            try:
                __version__ = get_distribution(__name__).version
            except DistributionNotFound:  # pragma: no cover
                pass
            """.format(name=package_name),
        }

        if len(arguments.cli) == 1:
            console_scripts = [
                "{} = {}._cli:main".format(arguments.cli[0], package_name),
            ]
            core_source_paths[package("_cli.py")] = _script(
                name=arguments.cli[0]
            )
        else:
            console_scripts = [
                "{each} = {package_name}._{each}:main".format(
                    each=each, package_name=package_name,
                ) for each in arguments.cli
            ]
            core_source_paths.update(
                (package("_" + each + ".py"), _script(name=each))
                for each in arguments.cli
            )

    if arguments.test_runner == "pytest":
        test_runner = "py.test"
        test_deps = ["pytest"]
    elif arguments.test_runner == "trial":
        test_runner = "trial"
        test_deps = ["twisted"]


    def ini(*sections, **kwargs):
        """
        Construct an INI-formatted str with the given contents.
        """

        lol_python = io.BytesIO()
        kwargs["defaults"] = dict(kwargs.pop("defaults", {}))
        parser = ConfigParser.SafeConfigParser(**kwargs)
        for section, contents in sections:
            parser.add_section(section)
            for option, value in contents:
                if isinstance(value, list):
                    value = "\n" + "\n".join(value)
                parser.set(section, option, value)
        parser.write(lol_python)
        value = lol_python.getvalue().replace("\t", "    ").replace("= \n", "=\n")
        return value[:-1]


    def classifiers(supports=arguments.supports, closed=arguments.closed):
        supports = sorted(supports)

        yield STATUS_CLASSIFIERS[arguments.status]

        for classifier in (
            "Operating System :: OS Independent",
            "Programming Language :: Python",
        ):
            yield classifier

        if not arguments.closed:
            yield "License :: OSI Approved :: MIT License"

        for version in supports:
            if version in VERSION_CLASSIFIERS:
                yield VERSION_CLASSIFIERS[version]

        if any(
            version.startswith("py2") or version in {"jython", "pypy"}
            for version in supports
        ):
            yield "Programming Language :: Python :: 2"

        if any(version.startswith("py3") for version in supports):
            yield "Programming Language :: Python :: 3"

        yield "Programming Language :: Python :: Implementation :: CPython"

        if "pypy" in supports:
            yield "Programming Language :: Python :: Implementation :: PyPy"

        if "jython" in supports:
            yield "Programming Language :: Python :: Implementation :: Jython"


    tox_envlist = sorted(arguments.supports) + ["readme", "safety"]
    if arguments.style:
        tox_envlist.append("style")
    if arguments.docs:
        tox_envlist.append("docs-{html,doctest,linkcheck,spelling,style}")


    tox_sections = [
        (
            "tox", [
                ("envlist", tox_envlist),
                ("skipsdist", "True"),
            ],
        ), (
            "testenv", [
                ("setenv", ""),
                ("changedir", "{envtmpdir}"),
                (
                    "commands", [
                        "{envbindir}/pip install {toxinidir}",
                        "{envbindir}/" + test_runner + " {posargs:" + tests + "}",
                        "{envpython} -m doctest {toxinidir}/README.rst",
                    ],
                ),
                (
                    "deps", test_deps + [
                        "" if arguments.closed else "codecov," + "coverage: coverage",
                    ]
                ),
            ],
        ), (
            "testenv:coverage", [
                (
                    "setenv", [
                        "{[testenv]setenv}",
                        "COVERAGE_FILE={envtmpdir}/coverage-data",
                    ],
                ),
                (
                    "commands", [
                        "{envbindir}/pip install {toxinidir}",
                        "{envbindir}/coverage run --rcfile={toxinidir}/.coveragerc {envbindir}/" + test_runner + " " + tests,
                        "{envbindir}/coverage report --rcfile={toxinidir}/.coveragerc --show-missing",
                        "{envbindir}/coverage html --directory={envtmpdir}/htmlcov --rcfile={toxinidir}/.coveragerc {posargs}",
                    ],
                ),
            ],
        ), (
            "testenv:readme", [
                ("changedir", "{toxinidir}"),
                ("deps", "readme_renderer"),
                (
                    "commands", [
                        "{envbindir}/python setup.py check --restructuredtext --strict",
                    ],
                ),
            ],
        ), (
            "testenv:safety", [
                ("deps", "safety"),
                (
                    "commands", [
                        "{envbindir}/pip install {toxinidir}",
                        "{envbindir}/safety check",
                    ],
                ),
            ],
        ), (
            "testenv:style", [
                ("deps", "ebb-lint"),
                (
                    "commands",
                    "flake8 {posargs} --max-complexity 10 {toxinidir}/" + tests + " {toxinidir}/setup.py",
                ),
            ],
        ),
    ]

    if arguments.docs:
        tox_sections.extend(
            [
                (
                    "testenv:docs-" + each, [
                        ("changedir", "docs"),
                        ("whitelist_externals", "make"),
                        (
                            "commands", (
                                "make "
                                "-f {toxinidir}/docs/Makefile "
                                "BUILDDIR={envtmpdir}/build "
                                "SPHINXOPTS='-a -c {toxinidir}/docs/ -n -T -W {posargs}' "
                            ) + each,
                        ), (
                            "deps", [
                                "-r{toxinidir}/docs/requirements.txt",
                                "{toxinidir}"
                            ],
                        ),
                    ],
                ) for each in ["html", "doctest", "linkcheck", "spelling"]
            ],
        )
        tox_sections.extend(
            [
                (
                    "testenv:docs-style", [
                        ("changedir", "docs"),
                        ("commands", "doc8 {posargs} {toxinidir}/docs"),
                        ("deps", ["doc8", "pygments", "pygments-github-lexers"]),
                    ],
                ),
            ],
        )


    if arguments.closed:
        license = "All rights reserved.\n"
    else:
        license = dedented(
            """
            Permission is hereby granted, free of charge, to any person obtaining a copy
            of this software and associated documentation files (the "Software"), to deal
            in the Software without restriction, including without limitation the rights
            to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
            copies of the Software, and to permit persons to whom the Software is
            furnished to do so, subject to the following conditions:

            The above copyright notice and this permission notice shall be included in
            all copies or substantial portions of the Software.

            THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
            IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
            FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
            AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
            LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
            OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
            THE SOFTWARE.
            """
        )

        tox_sections.append(
            (
                "testenv:codecov", [
                    (
                        "passenv", "CODECOV* CI TRAVIS TRAVIS_*",
                    ), (
                        "setenv", [
                            "{[testenv]setenv}",
                            "COVERAGE_DEBUG_FILE={envtmpdir}/coverage-debug",
                            "COVERAGE_FILE={envtmpdir}/coverage-data",
                        ],
                    ),
                    (
                        "commands", [
                            "{envbindir}/pip install {toxinidir}",
                            "{envbindir}/coverage run --rcfile={toxinidir}/.coveragerc {envbindir}/" + test_runner + " " + tests,
                            "{envbindir}/coverage xml -o {envtmpdir}/coverage.xml",
                            "{envbindir}/codecov --required --disable gcov --file {envtmpdir}/coverage.xml",
                        ],
                    ),
                ],
            ),
        )


    setup_sections = [
        (
            "metadata", [
                ("name", package_name),
                ("url", "https://github.com/Julian/" + name),

                ("description", ""),
                ("long_description", "file: README.rst"),

                ("author", arguments.author),
                (
                    "author_email", (
                        arguments.author_email or
                        "Julian+" + package_name + "@GrayVines.com"
                    ),
                ),
                ("classifiers", list(classifiers())),
            ],
        ), (
            "options", [
                contents,
                ("setup_requires", "setuptools_scm"),
            ] + (
                [("install_requires", ["click"])] if console_scripts else []
            ),
        )
    ] + (
        [("options.entry_points", [("console_scripts", console_scripts)])]
        if console_scripts
        else []
    ) + [
        ("flake8", [("exclude", package_name + "/__init__.py")]),
    ]


    heading = """
    {bar}
    {name}
    {bar}
    """.format(bar="=" * len(name), name=name)
    README = heading + "" if not arguments.readme else "\n" + arguments.readme

    files = {
        root("README.rst"): README,
        root("COPYING"): (
            "Copyright (c) {now.year} {author}\n\n".format(
                now=datetime.datetime.now(), author=arguments.author,
            ) + license
        ),
        root("MANIFEST.in"): """
            include *.rst
            include COPYING
            include tox.ini
            include .coveragerc
        """,
        root("setup.cfg"): ini(*setup_sections),
        root("setup.py"): """
            from setuptools import setup
            setup(use_scm_version=True)
        """,
        root(".coveragerc"): """
            # vim: filetype=dosini:
            [run]
            branch = True
            source = {package_name}
        """.format(package_name=package_name),
        root("tox.ini"): ini(*tox_sections),
        root(".testr.conf"): ini(
            defaults=[
                (
                    "test_command",
                    "python -m subunit.run discover . $LISTOPT $IDOPTION",
                ), (
                    "test_id_option",
                    "--load-list $IDFILE",
                ), (
                    "test_list_option",
                    "--list",
                ),
            ],
        ),
    }

    if arguments.docs:
        files[root("docs", "requirements.txt")] = """
            pygments-github-lexers
            sphinx
            sphinxcontrib-spelling
        """

    if not arguments.closed:
        files.update(
            {
                # FIXME: Generate this based on supported versions
                root(".travis.yml"): """
                    sudo: false
                    dist: xenial
                    language: python

                    python:
                    - 2.7
                    - 3.5
                    - 3.6
                    - 3.7
                    - pypy2.7-6.0
                    - pypy3.5-6.0

                    install:
                    - pip install tox-travis

                    script:
                    - tox

                    after_success:
                    - tox -e codecov
                """,
                root("codecov.yml"): """
                    coverage:
                    precision: 2
                    round: down
                    status:
                        patch:
                        default:
                            target: 100%

                    comment:
                    layout: "header, diff, uncovered"
                    behavior: default
                """,
            },
        )

    if arguments.bare:
        targets = core_source_paths
    else:
        files.update(
            (root(path), content)
            for path, content in core_source_paths.iteritems()
        )
        targets = files

        try:
            os.mkdir(name)
        except OSError as err:
            if err.errno == errno.EEXIST:
                sys.exit("{0} already exists!".format(name))
            raise

    for path, content in targets.iteritems():
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)))
        except OSError as err:
            if err.errno != errno.EEXIST:
                raise

        with open(path, "wb") as file:
            file.write(dedented(content))

    if arguments.docs:
        subprocess.check_call(
            [
                "sphinx-quickstart",
                "--quiet",
                "--project", name,
                "--author", arguments.author,
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
                os.path.join(name, "docs"),
            ],
        )
        with open(root("docs", "index.rst"), "w") as index:
            index.write(README)
            index.write("\n\n")
            index.write(
                dedented(
                    """
                    Contents
                    --------

                    .. toctree::
                        :glob:
                        :maxdepth: 2
                    """,
                ),
            )

    if arguments.sensible and not arguments.bare:
        subprocess.check_call(["git", "init", name])

        git_dir = root(".git")
        subprocess.check_call(
            ["git", "--git-dir", git_dir, "--work-tree", name, "add", "COPYING"])
        subprocess.check_call(
            ["git", "--git-dir", git_dir, "commit", "-m", "Initial commit"],
        )
