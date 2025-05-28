from pathlib import Path

import click

from flows.common.helpers import gather_files
from flows.settings import settings


@click.group("preproc")
def preproc_cli():
    """Preprocessing Flows commands"""
    pass


@preproc_cli.command()
@click.argument("file_or_dir", type=str)
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.option("-g", "--gather-glob", type=str, multiple=True, default=["*.pdf"])
@click.option("-u", "--parser_base_url", type=str, default=settings.DOCLING_BASE_URL)
def docfile_to_markdown(
    file_or_dir: str,
    output_dir: str,
    gather_glob: list[str],
    parser_base_url: str | None = None,
):
    """
    Convert a PDF file or all PDF files in a directory to markdown

    Args:
        file_or_dir (str): Path to the PDF file or directory containing PDF files
        output_dir (str): Path to the directory where the markdown files will be saved
    """
    from flows.preproc.convert import docling_2_md

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for file in gather_files(file_or_dir, gather_glob):
        try:
            markdown = docling_2_md(file, parser_base_url)
        except Exception as e:
            print(f"💥 Failed to convert {file} to markdown: {e}")
        else:
            file_name = file.split("/")[-1].replace(".pdf", "")
            out_path = out_dir / (file_name + ".md")
            with out_path.open("w") as outfile:
                outfile.write(markdown + "\n")


@preproc_cli.command()
@click.argument("client_id", type=str)
@click.argument("file_or_dir", type=str)
@click.option("-g", "--file-glob", type=str, multiple=True, default=["*.*"])
def index_docfiles(
    client_id: str,
    file_or_dir: str,
    file_glob: list[str],
):
    """Index a PDF file (local or remote) or all PDF files in a local directory"""
    from flows.preproc import index_files

    paths = gather_files(file_or_dir, file_glob)
    index_files(
        client_id=client_id,
        file_paths=paths,
    )
