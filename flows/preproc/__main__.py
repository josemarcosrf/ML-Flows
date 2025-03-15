from pathlib import Path

import click

from flows.common.helpers.auto_download import is_url
from flows.common.helpers.s3 import is_s3_path
from flows.preproc.ocr import ocr_pdf_flow


@click.group()
def cli():
    pass


@cli.command()
@click.argument("pdf_or_dir", type=str)
@click.argument("output_dir", type=click.Path(file_okay=False))
def pdf_to_markdown(pdf_or_dir: str, output_dir: str):
    """
    Convert a PDF file or all PDF files in a directory to markdown

    Args:
        pdf_or_dir (str): Path to the PDF file or directory containing PDF files
        output_dir (str): Path to the directory where the markdown files will be saved
    """
    if is_url(pdf_or_dir) or is_s3_path(pdf_or_dir):
        files = [pdf_or_dir]
    else:
        in_path = Path(pdf_or_dir)
        if in_path.is_dir():
            files = [str(p) for p in in_path.rglob("*.pdf")]
        else:
            files = [pdf_or_dir]

    for file in files:
        markdown, _, _ = ocr_pdf_flow(file)
        file_name = file.split("/")[-1].replace(".pdf", "")

        out_path = Path(output_dir) / (file_name + ".md")
        with out_path.open("w") as outfile:
            outfile.write(markdown + "\n")


if __name__ == "__main__":
    cli()
