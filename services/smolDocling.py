import tempfile
from pathlib import Path

import fitz  # PyMuPDF
import PIL
from docling_core.types.doc import DoclingDocument
from docling_core.types.doc.document import DocTagsDocument
from fastapi import FastAPI, HTTPException, UploadFile
from PIL import Image
from ray import serve
from vllm import LLM, SamplingParams

# Define a FastAPI app with base route
app = FastAPI(root_path="/to_markdown")


def pdf_to_images(pdf_path: Path, zoom=2):
    """
    Convert each page of a PDF to an image.

    Args:
        pdf_path (Path): Path to the PDF file.
        zoom (int): Zoom factor to apply to the PDF pages.
    """
    doc = fitz.open(pdf_path)
    mat = fitz.Matrix(zoom, zoom)  # Define the zoom factor
    images = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    return images


@serve.deployment
@serve.ingress(app)
class smolDoclingConverter:
    PROMPT_TEXT = "Convert page to Docling."
    CHAT_TEMPLATE = "<|im_start|>User:<image>{PROMPT_TEXT}<end_of_utterance>Assistant:"

    def __init__(self, model_id: str, temperature: float = 0.0, max_tokens: int = 8192):
        # Initialize LLM
        self.llm = LLM(model=model_id, limit_mm_per_prompt={"image": 1})
        self.sampling_params = SamplingParams(
            temperature=temperature, max_tokens=max_tokens
        )

    def _image_to_doctags(self, image: PIL.Image):
        prompt = self.CHAT_TEMPLATE.format(PROMPT_TEXT=self.PROMPT_TEXT)
        llm_input = {"prompt": prompt, "multi_modal_data": {"image": image}}
        output = self.llm.generate([llm_input], sampling_params=self.sampling_params)[0]
        doctags = output.outputs[0].text

        return doctags

    def _convert_from_path(self, pdf_path: Path):
        # Convert PDF to images
        images = pdf_to_images(pdf_path)

        doctags_list = []
        for image in images:
            doctags = self._image_to_doctags(image)
            doctags_list.append(doctags)

        # To convert to Docling Document, MD, HTML, etc.:
        doc_name = pdf_path.stem
        doctags_doc = DocTagsDocument.from_doctags_and_image_pairs(doctags_list, images)
        doc = DoclingDocument(name=doc_name)
        doc.load_from_doctags(doctags_doc)

        return doc.export_to_markdown()

    @app.post("/upload")
    async def convert_from_upload(self, file: UploadFile) -> str:
        """Upload PDF files and convert them to markdown
        This endpoint accepts multiple PDF files and converts each to markdown format.
        It uses the `smolDocling` model to perform the conversion.

        Args:
            files (list[UploadFile]): The list of PDF files to be converted.

        Returns:
            dict: A dictionary mapping each file name to its conversion result.
        """
        try:
            with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
                tmp_file.write(await file.read())
                return self._convert_from_path(tmp_file.name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"💥 Failed to convert {file} to markdown: {e}",
            )

    @app.get("/")
    async def convert_from_path(self, pdf_path: str) -> dict:
        """Convert PDF files to text
        This endpoint accepts multiple PDF file paths and converts each to markdown format.
        It uses the `smolDocling` model to perform the conversion.

        Args:
            pdf_paths (list[str]): The list of PDF file paths to be converted.

        Returns:
            dict: A dictionary mapping each file path to its conversion result.
        """
        try:
            return self._convert_from_path(Path(pdf_path))
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"💥 Failed to convert {pdf_path} to markdown: {e}",
            )


# Deploy (without parameters for now - default values are used)
converter = smolDoclingConverter.bind()
