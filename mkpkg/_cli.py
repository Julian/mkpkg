import click

from mkpkg import __version__


@click.command()
@click.version_option(version=__version__)
def main():
    pass
