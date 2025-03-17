from pathlib import Path

import click

from flows.common.helpers.auto_download import is_url
from flows.common.helpers.s3 import is_s3_path
from flows.preproc import index_files, pdf_2_md
from flows.settings import settings


def gather_paths(pdf_or_dir):
    if is_url(pdf_or_dir) or is_s3_path(pdf_or_dir):
        print("🚀 Will automatically try to download file from URL or S3...")
        files = [pdf_or_dir]
    else:
        in_path = Path(pdf_or_dir)
        if in_path.is_dir():
            print("📁 Gathering all PDF files in the directory...")
            files = [str(p) for p in in_path.rglob("*.pdf")]
            print(" - " + "\n - ".join(files) + "\n")
        else:
            print("📄 Converting a single PDF file to markdown...")
            files = [pdf_or_dir]

    return files


@click.group("preproc")
def preproc_cli():
    """Preprocessing Flows commands"""
    pass


@preproc_cli.command()
@click.argument("pdf_or_dir", type=str)
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.option("--parser_base_url", type=str, default=settings.PDF_PARSER_BASE_URL)
def pdf_to_markdown(pdf_or_dir: str, output_dir: str, parser_base_url: str):
    """
    Convert a PDF file or all PDF files in a directory to markdown

    Args:
        pdf_or_dir (str): Path to the PDF file or directory containing PDF files
        output_dir (str): Path to the directory where the markdown files will be saved
    """
    for file in gather_paths(pdf_or_dir):
        try:
            markdown = pdf_2_md(file, parser_base_url)
        except Exception as e:
            print(f"💥 Failed to convert {file} to markdown: {e}")
        else:
            file_name = file.split("/")[-1].replace(".pdf", "")
            out_path = Path(output_dir) / (file_name + ".md")
            with out_path.open("w") as outfile:
                outfile.write(markdown + "\n")


@preproc_cli.command()
@click.argument("client_id", type=str)
@click.argument("pdf_or_dir", type=str)
@click.option("--collection_name", type=str)
def index_pdfs(client_id: str, pdf_or_dir: str, collection_name: str | None = None):
    """Index a PDF file (local or remote) or all PDF files in a local directory"""
    paths = gather_paths(pdf_or_dir)
    index_files(
        client_id,
        file_paths=paths,
        collection_name=collection_name
        or f"{client_id}-{settings.LLM_BACKEND}-{settings.EMBEDDING_MODEL}",
    )
