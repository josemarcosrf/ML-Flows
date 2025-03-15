import requests
from prefect import task


@task(log_prints=True, task_run_name="PDF-to-Markdown={pdf_path}")
def pdf_2_md(pdf_path: str, parser_conf: dict) -> str:
    """Convert a PDF file to text

    Args:
        pdf_path (Path): Path to the PDF file
        parser_conf (dict): Configuration for the PDF parser. Must contain a "base_url" key.
    """
    parser_base_url = parser_conf["base_url"]
    return requests.get(f"{parser_base_url}/to_markdown?pdf_path={pdf_path}").text
