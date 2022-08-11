from datetime import datetime
from pathlib import Path
from textwrap import dedent
import os
import pwd
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
    "pypy2": "Programming Language :: Python :: 2.7",
    "pypy3": "Programming Language :: Python :: 3.8",

    "py27": "Programming Language :: Python :: 2.7",
    "py35": "Programming Language :: Python :: 3.5",
    "py36": "Programming Language :: Python :: 3.6",
    "py37": "Programming Language :: Python :: 3.7",
    "py38": "Programming Language :: Python :: 3.8",
    "py39": "Programming Language :: Python :: 3.9",
    "py310": "Programming Language :: Python :: 3.10",
    "py311": "Programming Language :: Python :: 3.11",
    "py312": "Programming Language :: Python :: 3.12",

    "jython": "Programming Language :: Python :: 2.7",
}
TEST_DEPS = {
    "pytest": ["pytest"],
    "twisted.trial": ["twisted"],
    "virtue": ["virtue"],
}
TEMPLATE = Path(__file__).with_name("template")

CODECOV_URL = "https://codecov.io/gh/Julian"
PYPI_TOKEN_URL = "https://pypi.org/manage/account/token/"
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
    default="virtue",
    type=click.Choice(TEST_DEPS.keys()),
    help="the test runner to use",
)
@click.option(
    "-s",
    "--supports",
    multiple=True,
    type=click.Choice(sorted(VERSION_CLASSIFIERS)),
    default=["py37", "py38", "py39", "py310", "py311", "pypy3"],
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
        package_name = name[len("python-"):]
    elif name.endswith(".py"):
        package_name = name[:-len(".py")]
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
            scripts = [f'{cli[0]} = "{package_name}:main"']
            script = env.get_template("package/_cli.py.j2").render(
                program_name=cli[0],
            )
        else:
            scripts = []
            script = u""

        script_name = package_name + ".py"
        core_source_paths = {
            script_name: script,
            "tests.py": env.get_template("tests.py.j2").render(),
        }
        style_paths = ["{toxinidir}/" + script_name, tests]

    else:
        tests = package_name

        core_source_paths = {
            package / "tests" / "__init__.py": u"",
            package / "__init__.py": env.get_template(
                "package/__init__.py.j2",
            ).render(),
        }
        style_paths = ["{toxinidir}/" + package_name]

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
                ) for each in cli
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
        ".coveragerc": env.get_template(".coveragerc.j2").render(),
        "tox.ini": env.get_template("tox.ini.j2").render(
            test_deps=TEST_DEPS[test_runner],
            tests=tests,
            style_paths=style_paths,
        ),
        ".flake8": template(".flake8"),
        ".testr.conf": template(".testr.conf"),
    }

    if not closed:
        for each in (TEMPLATE / ".github" / "workflows").iterdir():
            files[".github/workflows/" + each.name] = each.read_text()
        files[".github/FUNDING.yml"] = template(".github/FUNDING.yml")
        files[".github/SECURITY.md"] = env.get_template(
            ".github/SECURITY.md.j2",
        ).render()
        files["codecov.yml"] = template("codecov.yml")

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
        (root / "docs" / "requirements.in").write_text(
            template("docs", "requirements.in"),
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

        # Fix sphinx-quickstart not writing a trailing newline.
        with root.joinpath("docs", "conf.py").open("a") as file:
            file.write("\n")

        (root / "docs" / "index.rst").write_text(template("docs", "index.rst"))

        click.echo(f"Set up documentation at: {READTHEDOCS_IMPORT_URL}")

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
            click.echo(
                dedent(
                    f"""
                    Set up:

                      * a PyPI token from {PYPI_TOKEN_URL} named
                        'GitHub Actions - {name}'
                      * a CodeCov token from {CODECOV_URL}/{name}

                    and include them in the GitHub secrets at
                    https://github.com/Julian/{name}/settings/secrets
                    """,
                ),
            )


def template(*segments):
    return TEMPLATE.joinpath(*segments).read_text()


def _cname(name):
    if name.endswith("-cffi"):
        name = name[:-len("-cffi")]
    if name.startswith("lib"):
        name = name[len("lib"):]
    return "_" + name
