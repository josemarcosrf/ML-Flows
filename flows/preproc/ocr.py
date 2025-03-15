from pathlib import Path

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from prefect import flow

from flows.common.clients.llms import get_llm_backend
from flows.common.helpers.auto_download import download_if_remote
from flows.settings import settings


# TODO: This is best implemented as a Ray Actor...
class PDFToMarkdown:
    def __init__(
        self,
        use_llm: bool = False,
        llm_backend: str = get_llm_backend(),
        llm_model: str | None = settings.VISION_MODEL,
        artifact_dict: dict | None = None,
    ):
        self.config = {
            "use_llm": use_llm,  # wether to enable LLM for higher accuracy
            "llm_model": llm_model,
        }

        if use_llm:
            if llm_backend == "openai":
                llm_service = "marker.services.openai.OpenAIService"
            elif llm_backend == "ollama":
                llm_service = "marker.services.ollama.OllamaService"

            self.config["llm_service"] = llm_service

            # TODO: Implement LLM connectivity
            raise NotImplementedError("LLM connectivity is not implemented yet")

        self.config_parser = ConfigParser(self.config)
        self.artifact_dict = artifact_dict or create_model_dict()
        self.converter = PdfConverter(
            config=self.config_parser.generate_config_dict(),
            llm_service=self.config_parser.get_llm_service(),
            artifact_dict=create_model_dict(),
        )

    def convert(self, pdf_path: Path | str) -> tuple:
        """Convert a PDF file to text

        Args:
            pdf_path (str): Path to the PDF file
        """
        rendered = self.converter(str(pdf_path))
        text, metadata, images = text_from_rendered(rendered)

        return text, metadata, images


@flow(log_prints=True)
@download_if_remote
def ocr_pdf_flow(pdf_path: str, use_llm: bool = False) -> tuple:
    """Convert a PDF file to text

    Args:
        pdf_path (Path): Path to the PDF file
    """
    # pdf_converter = initialize_pdf_to_markdown(use_llm=False)
    print(f"🪄 Converting {pdf_path} to markdown")
    return "hello 👋", None, None
    # return pdf_converter.convert(pdf_path)
