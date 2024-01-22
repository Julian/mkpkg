from datetime import UTC, datetime
from pathlib import Path
from random import randint
from textwrap import dedent
import os
import pwd
import re
import subprocess
import sys
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
    "pypy3.9": "Programming Language :: Python :: 3.9",
    "pypy3.10": "Programming Language :: Python :: 3.10",
    "pypy3.11": "Programming Language :: Python :: 3.11",
    "2.7": "Programming Language :: Python :: 2.7",
    "3.5": "Programming Language :: Python :: 3.5",
    "3.6": "Programming Language :: Python :: 3.6",
    "3.7": "Programming Language :: Python :: 3.7",
    "3.8": "Programming Language :: Python :: 3.8",
    "3.9": "Programming Language :: Python :: 3.9",
    "3.10": "Programming Language :: Python :: 3.10",
    "3.11": "Programming Language :: Python :: 3.11",
    "3.12": "Programming Language :: Python :: 3.12",
    "3.13": "Programming Language :: Python :: 3.13",
}
PYVERSION = re.compile(r"\d\.\d+")
TEST_DEP = {
    "pytest": "pytest",
    "twisted.trial": "twisted",
    "virtue": "virtue",
}
TEMPLATE = Path(__file__).with_name("template")

READTHEDOCS_IMPORT_URL = "https://readthedocs.org/dashboard/import/manual/"


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
    default="pytest",
    type=click.Choice(sorted(TEST_DEP)),
    help="the test runner to use",
)
@click.option(
    "-s",
    "--supports",
    multiple=True,
    type=click.Choice(sorted(VERSION_CLASSIFIERS)),
    default=["3.10", "3.11", "3.12", "pypy3.10"],
    help="a version of Python supported by the package",
)
@click.option(
    "--status",
    type=click.Choice(list(STATUS_CLASSIFIERS)),
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
    help="(don't) run pyflakes by default in nox runs.",
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
@click.version_option(prog_name="mkpkg")
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
        package_name = name[len("python-") :]
    elif name.endswith(".py"):
        package_name = name[: -len(".py")]
    else:
        package_name = name
    package_name = package_name.lower().replace("-", "_")

    supports = sorted(
        supports,
        key=lambda v: (
            [int(g) for g in PYVERSION.search(v)[0].split(".")],  # type: ignore[reportOptionalSubscript]
            -len(v),
        ),
    )

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
        now=datetime.now(tz=UTC),
        package_name=package_name,
        single_module=single_module,
        style=style,
        supports=supports,
        test_runner=test_runner,
    )

    package = Path(package_name)

    if single_module:
        tests = "tests.py"

        if len(cli) > 1:
            sys.exit("Cannot create a single module with multiple CLIs.")
        elif cli:
            scripts = [f'{cli[0]} = "{package_name}:main"']
            script = env.get_template("package/_cli.py.j2").render(
                program_name=cli[0],
            )
        else:
            scripts = []
            script = '"""\nFill me in!\n"""\n'

        script_name = package_name + ".py"
        core_source_paths = {
            script_name: script,
            "tests.py": env.get_template("tests.py.j2").render(),
        }

    else:
        tests = package_name

        init, tests = package / "__init__.py", package / "tests"
        integration = env.get_template("package/tests/test_integration.py.j2")
        core_source_paths = {
            init: env.get_template("package/__init__.py.j2").render(),
            tests / "__init__.py": "",
            tests / "test_integration.py": integration.render(),
        }

        if cffi:
            core_source_paths[package / "_build.py"] = env.get_template(
                "package/_build.py.j2",
            ).render(cname=_cname(name))

        if len(cli) == 1:
            scripts = [f'{cli[0]} = "{package_name}._cli:main"']
            core_source_paths[package / "_cli.py"] = env.get_template(
                "package/_cli.py.j2",
            ).render(program_name=cli[0])
            core_source_paths[package / "__main__.py"] = env.get_template(
                "package/__main__.py.j2",
            ).render()
        else:
            scripts = [
                f'{each} = "{package_name}._{each}:main"' for each in cli
            ]
            core_source_paths.update(
                (
                    package / ("_" + each + ".py"),
                    env.get_template("package/_cli.py.j2").render(
                        program_name=each,
                    ),
                )
                for each in cli
            )

    dependencies = []
    if cffi:
        dependencies.append("cffi>=1.0.0")
    if scripts:
        dependencies.append("click")

    files = {
        "README.rst": env.get_template("README.rst.j2").render(
            contents=readme,
        ),
        "COPYING": env.get_template("COPYING.j2").render(),
        "pyproject.toml": env.get_template("pyproject.toml.j2").render(
            dependencies=dependencies,
            scripts=scripts,
            author_email=(
                author_email or "Julian+" + package_name + "@GrayVines.com"
            ),
            status_classifier=STATUS_CLASSIFIERS[status],
            version_classifiers={
                VERSION_CLASSIFIERS[each]
                for each in supports
                if each in VERSION_CLASSIFIERS
            },
            py2=any(
                version.startswith("2.") or version in {"jython", "pypy2"}
                for version in supports
            ),
            py3=any(
                version.startswith(("3.", "pypy3")) for version in supports
            ),
            cpython=any(
                version.startswith(("2.", "3.")) for version in supports
            ),
            pypy=any(version.startswith("pypy") for version in supports),
            jython="jython" in supports,
            minimum_python_version=PYVERSION.search(supports[0])[0],  # type: ignore[reportOptionalSubscript]
        ),
        ".pre-commit-config.yaml": template(".pre-commit-config.yaml"),
        "noxfile.py": env.get_template("noxfile.py.j2").render(
            test_dep=TEST_DEP[test_runner],
            tests=tests,
        ),
    }

    if test_runner == "pytest":
        files["test-requirements.in"] = env.get_template(
            "test-requirements.in.j2",
        ).render(test_dep=TEST_DEP[test_runner])

    if not closed:
        files[".github/workflows/ci.yml"] = env.get_template(
            ".github/workflows/ci.yml.j2",
        ).render(
            schedule_hour=randint(3, 7),
            schedule_minute=randint(0, 59),
        )
        files[".github/dependabot.yml"] = template(".github/dependabot.yml")
        files[".github/FUNDING.yml"] = template(".github/FUNDING.yml")
        files[".github/SECURITY.md"] = env.get_template(
            ".github/SECURITY.md.j2",
        ).render()

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

    if init_vcs and not bare:
        subprocess.check_call(["git", "init", "--quiet", name])

        git_dir = root / ".git"
        subprocess.check_call(
            [
                "git",
                "--git-dir",
                str(git_dir),
                "--work-tree",
                name,
                "add",
                "COPYING",
            ],
        )
        subprocess.check_call(
            [
                "git",
                "--git-dir",
                str(git_dir),
                "commit",
                "--quiet",
                "-m",
                "Initial commit",
            ],
        )

    if docs:
        docs = root / "docs"
        docs.mkdir()

        requirements = env.get_template("docs/requirements.in.j2").render()
        (docs / "requirements.in").write_text(requirements)
        subprocess.check_call(
            ["nox", "-s", "requirements"],
            cwd=root.absolute(),
            stdout=subprocess.DEVNULL,  # nox appears to have no --quiet...
        )
        conf = env.get_template("docs/conf.py.j2").render()
        (docs / "conf.py").write_text(conf)
        (docs / "index.rst").write_text(template("docs/index.rst"))
        (docs / ".readthedocs.yml").write_text(template(".readthedocs.yml"))

        click.echo(f"Set up documentation at: {READTHEDOCS_IMPORT_URL}")

        if not closed:
            click.echo(
                dedent(
                    """
                    Be sure to:

                      * Fill in the description in the pyproject.toml and in
                        the docstring for __init__.py
                      * Set up a pending PyPI publisher from the appropriate
                        PyPI page https://pypi.org/manage/account/publishing/
                        (named 'PyPI')
                    """,
                ),
            )


def template(*segments):
    return TEMPLATE.joinpath(*segments).read_text()


def _cname(name):
    if name.endswith("-cffi"):
        name = name[: -len("-cffi")]
    if name.startswith("lib"):
        name = name[len("lib") :]
    return "_" + name
