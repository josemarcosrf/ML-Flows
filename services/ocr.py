import tempfile

from fastapi import FastAPI, HTTPException, UploadFile
from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered
from ray import serve

# Define a FastAPI app with base route /convert
app = FastAPI(root_path="/convert")


@serve.deployment
@serve.ingress(app)
class PDFToMarkdown:
    def __init__(
        self,
        use_llm: bool = False,
        llm_backend: str | None = None,
        llm_model: str | None = None,
        artifact_dict: dict | None = None,
    ):
        self.config = {
            "use_llm": use_llm,  # wether to enable LLM for higher accuracy
            "llm_model": llm_model,
        }
        if use_llm:
            if llm_backend is None:
                raise ValueError("If use_llm is True, llm_backend must be provided")
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

    @app.post("/upload")
    async def convert_from_upload(self, files: list[UploadFile]) -> dict:
        """Upload PDF files and convert them to markdown

        Args:
            files (list[UploadFile]): List of PDF files to be converted
        """
        results = {}
        for file in files:
            try:
                with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                    tmp_file.write(await file.read())
                    tmp_file_path = tmp_file.name
                    rendered = self.converter(tmp_file_path)

                text, _, _ = text_from_rendered(rendered)
                results[file.filename] = text
            except Exception as e:
                results[file.filename] = f"💥 Failed to convert: {e}"

        return results

    @app.get("/from_path")
    async def convert_from_path(self, pdf_path: str) -> str:
        """Convert a PDF file to text

        Args:
            pdf_path (str): Path to the PDF file
        """
        try:
            rendered = self.converter(str(pdf_path))
            text, _, _ = text_from_rendered(rendered)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"💥 Failed to convert {pdf_path} to markdown: {e}",
            )

        return text


# Deploy (without parameters for now - default values are used)
converter = PDFToMarkdown.bind()
