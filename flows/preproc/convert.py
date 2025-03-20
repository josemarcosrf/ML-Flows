from pathlib import Path

import requests
from prefect import task

from flows.common.helpers.auto_download import download_if_remote
from flows.settings import settings


def custom_task_run_name() -> str:
    from prefect.runtime import flow_run, task_run

    # func_name = flow_run.flow_name or task_run.task_name
    parameters = flow_run.get_parameters() or task_run.get_parameters()
    pdf_path = parameters.get("pdf_path", "")
    pdf_name = Path(pdf_path).stem
    return f"pdf-to-markdown={pdf_name}"


@task(log_prints=True, task_run_name=custom_task_run_name)
@download_if_remote(include=["pdf_path"])
def pdf_2_md(pdf_path: str, parser_base_url: str = settings.PDF_PARSER_BASE_URL) -> str:
    """Convert a PDF file to text using the Marker PDF to Markdown parser service.

    Args:
        pdf_path (Path): Path to the PDF file
        parser_base_url (str): Base URL of the parser service
    """
    return requests.get(f"{parser_base_url}/to_markdown?pdf_path={pdf_path}").text
