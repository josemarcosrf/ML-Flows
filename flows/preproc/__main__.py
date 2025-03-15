from pathlib import Path

import click

from flows.common.helpers.auto_download import is_url
from flows.common.helpers.s3 import is_s3_path
from flows.preproc import pdf_2_md


@click.group()
def cli():
    pass


@cli.command()
@click.argument("pdf_or_dir", type=str)
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.argument("parser_base_url", type=str)
def pdf_to_markdown(pdf_or_dir: str, output_dir: str, parser_base_url: str):
    """
    Convert a PDF file or all PDF files in a directory to markdown

    Args:
        pdf_or_dir (str): Path to the PDF file or directory containing PDF files
        output_dir (str): Path to the directory where the markdown files will be saved
    """
    if is_url(pdf_or_dir) or is_s3_path(pdf_or_dir):
        print("🚀 Downloading PDF file from URL or S3...")
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

    for file in files:
        try:
            markdown = pdf_2_md(file, {"base_url": parser_base_url})
        except Exception as e:
            print(f"💥 Failed to convert {file} to markdown: {e}")
        else:
            file_name = file.split("/")[-1].replace(".pdf", "")
            out_path = Path(output_dir) / (file_name + ".md")
            with out_path.open("w") as outfile:
                outfile.write(markdown + "\n")


if __name__ == "__main__":
    cli()
