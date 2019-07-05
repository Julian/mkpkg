#! /usr/bin/env python2

import ConfigParser
import datetime
import errno
import io
import os
import pwd
import sys
import subprocess
import textwrap

import click
import jinja2


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
    type=click.Choice(sorted(VERSION_CLASSIFIERS) + ["jython", "pypy"]),
    default=["py36", "py37", "pypy"],
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
    "--no-style/--style",
    "style",
    default=True,
    help="don't run pyflakes by default in tox runs.",
)
@click.option(
    "--no-sensibility",
    "sensible",
    default=True,
    is_flag=True,
    help="don't initialize a VCS.",
)
@click.option("--closed", help="Create a closed source package.")
def main(
    name,
    author,
    author_email,
    cli,
    readme,
    test_runner,
    supports,
    status,
    docs,
    single_module,
    bare,
    style,
    sensible,
    closed,
):
    """
    Oh how exciting! Create a new Python package.
    """

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

    if name.startswith("python-"):
        package_name = name[len("python-"):]
    else:
        package_name = name
    package_name = package_name.lower().replace("-", "_")

    if single_module:
        contents = "py_modules", name
        tests = "tests.py"

        if len(cli) > 1:
            sys.exit("Cannot create a single module with multiple CLIs.")
        elif cli:
            console_scripts = [
                "{} = {}:main".format(cli[0], package_name),
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
            package("__init__.py"): template("package", "__init__.py"),
        }

        if len(cli) == 1:
            console_scripts = [
                "{} = {}._cli:main".format(cli[0], package_name),
            ]
            core_source_paths[package("_cli.py")] = _script(name=cli[0])
        else:
            console_scripts = [
                "{each} = {package_name}._{each}:main".format(
                    each=each, package_name=package_name,
                ) for each in cli
            ]
            core_source_paths.update(
                (package("_" + each + ".py"), _script(name=each))
                for each in cli
            )

    if test_runner == "pytest":
        test_runner = "py.test"
        test_deps = ["pytest"]
    elif test_runner == "trial":
        test_runner = "trial"
        test_deps = ["twisted"]

    def classifiers(supports=supports, closed=closed):
        supports = sorted(supports)

        yield STATUS_CLASSIFIERS[status]

        for classifier in (
            "Operating System :: OS Independent",
            "Programming Language :: Python",
        ):
            yield classifier

        if not closed:
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

    tox_envlist = sorted(supports) + ["readme", "safety"]
    if style:
        tox_envlist.append("style")
    if docs:
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
                        "" if closed else "codecov," + "coverage: coverage",
                    ],
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

    if docs:
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
                                "{toxinidir}",
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

    if closed:
        license = "All rights reserved.\n"
    else:
        license = template("COPYING")

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

                ("author", author),
                (
                    "author_email", (
                        author_email or
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
        ),
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
    README = heading + "" if not readme else "\n" + readme

    files = {
        root("README.rst"): README,
        root("COPYING"): (
            "Copyright (c) {now.year} {author}\n\n".format(
                now=datetime.datetime.now(), author=author,
            ) + license
        ),
        root("MANIFEST.in"): template("MANIFEST.in"),
        root("setup.cfg"): ini(*setup_sections),
        root("setup.py"): template("setup.py"),
        root(".coveragerc"): render(".coveragerc", package_name=package_name),
        root("tox.ini"): ini(*tox_sections),
        root(".testr.conf"): template(".testr.conf"),
    }

    if docs:
        files[root("docs", "requirements.txt")] = template(
            "docs", "requirements.txt",
        )

    if not closed:
        files.update(
            {
                # FIXME: Generate this based on supported versions
                root(".travis.yml"): template(".travis.yml"),
                root("codecov.yml"): template("codecov.yml"),
            },
        )

    if bare:
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

    if docs:
        subprocess.check_call(
            [
                "sphinx-quickstart",
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

    if sensible and not bare:
        subprocess.check_call(["git", "init", name])

        git_dir = root(".git")
        subprocess.check_call(
            ["git", "--git-dir", git_dir, "--work-tree", name, "add", "COPYING"])
        subprocess.check_call(
            ["git", "--git-dir", git_dir, "commit", "-m", "Initial commit"],
        )


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


def template(*segments):
    path = os.path.join(os.path.dirname(__file__), "template", *segments)
    with open(path) as f:
        return f.read()


def render(*segments, **values):
    segments = segments[:-1] + (segments[-1] + ".j2",)
    return jinja2.Template(
        template(*segments),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    ).render(values)
