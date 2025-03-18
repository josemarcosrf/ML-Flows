import requests
from prefect import task

from flows.common.helpers.auto_download import download_if_remote
from flows.settings import settings


@task(log_prints=True, task_run_name="PDF-to-Markdown={pdf_path}")
@download_if_remote(include=["pdf_path"])
def pdf_2_md(pdf_path: str, parser_base_url: str = settings.PDF_PARSER_BASE_URL) -> str:
    """Convert a PDF file to text using the Marker PDF to Markdown parser service.

    Args:
        pdf_path (Path): Path to the PDF file
        parser_base_url (str): Base URL of the parser service
    """
    return requests.get(f"{parser_base_url}/to_markdown?pdf_path={pdf_path}").text
