from pathlib import Path

import requests
from loguru import logger
from prefect import task

from flows.common.helpers.auto_download import download_if_remote
from flows.common.types import ExportFormat
from flows.settings import settings


def custom_task_run_name() -> str:
    from prefect.runtime import task_run

    func_name = task_run.get_task_name()
    parameters = task_run.get_parameters()
    pdf_path = parameters.get("pdf_path", "")
    pdf_name = Path(pdf_path).stem
    return f"{func_name}={pdf_name}"


def docling_convert(file_path: str, export_format: str = ExportFormat.Markdown) -> str:
    """Convert a PDF file to text using Docling default conversion.

    Args:
        file_path (str): Path to the PDF file
        export_format (ExportFormat): Export format (Markdown or HTML)
    """
    from docling.document_converter import DocumentConverter

    # Use the default Docling conversion service
    logger.info(f"Using docling to convert {file_path} ➡️ {export_format}")
    converter = DocumentConverter()
    result = converter.convert(file_path)
    if export_format == ExportFormat.Markdown:
        return result.document.export_to_markdown()
    elif export_format == ExportFormat.HTML:
        return result.document.export_to_html()
    else:
        raise ValueError(f"Unsupported format: {export_format}")


def smoldocling_convert(
    pdf_path: str, parser_base_url: str = settings.DOCLING_BASE_URL
) -> str:
    """Convert a PDF file to text using SmolDocling HTTP conversion service.
    See: https://github.com/josemarcosrf/DoPARSE/blob/main/src/doparse/smoldocling_ocr.py.

    Args:
        pdf_path (str): Path to the PDF file
        parser_base_url (str): Base URL of the parser service
    """
    # FIXME: Check request path and if should be /upload or /convert
    logger.info(f"Using 🤗 smoldocling to convert {pdf_path} ➡️ markdown")
    return requests.get(f"{parser_base_url}/convert?pdf_path={pdf_path}").text


@task(log_prints=True, task_run_name=custom_task_run_name)
@download_if_remote(include=["pdf_path"])
def marker_pdf_2_md(
    pdf_path: str, parser_base_url: str = settings.MARKER_PDF_BASE_URL
) -> str:
    """Convert a PDF file to text using the Marker PDF to Markdown HTTP parser service.
        See services/marker.py for more details.
    Args:
        pdf_path (Path): Path to the PDF file
        parser_base_url (str): Base URL of the parser service
    """
    # FIXME: Check request path and if should be /upload or /convert
    return requests.get(f"{parser_base_url}/to_markdown?pdf_path={pdf_path}").text


@task(log_prints=True, task_run_name=custom_task_run_name)
@download_if_remote(include=["pdf_path"])
def docling_2_md(
    file_path: str, parser_base_url: str = settings.DOCLING_BASE_URL
) -> str:
    """Convert a PDF file to text using the Docling. If a vLLM URL is provided,
    it uses the SmolDocling model. Otherwise, it uses the default Docling conversion.

    Args:
        file_path (str): Path to the PDF file
        vis_model_id (str): Model ID of the VLLM server.
            Defaults to `ds4sd/SmolDocling-256M-preview`.
        vllm_url (str): URL of the Docling VLLM service
        export_format (ExportFormat): Export format (Markdown or HTML)

    """
    if parser_base_url is None:
        return docling_convert(file_path)
    else:
        return smoldocling_convert(file_path, parser_base_url)
