from pathlib import Path
from unittest.mock import patch

import pytest

from flows.preproc.convert import docling_2_md

PDF_FILE = Path("data/LeaseAgreements/E17_LEASE AGREEMENT.pdf")
DOCX_FILE = Path("data/LeaseAgreements/Agreement.docx.pdf")


@pytest.mark.parametrize(
    "file_path,parser_base_url,is_smol",
    [
        (PDF_FILE, "http://dummy-url", True),  # SmolDocling path
        (PDF_FILE, None, False),  # Docling path
        (DOCX_FILE, None, False),  # Docling path for DOCX
    ],
)
def test_docling_2_md(file_path, parser_base_url, is_smol):
    if is_smol:
        with patch("flows.preproc.convert.smoldocling_convert") as mock_smol:
            mock_smol.return_value = "SMOL_RESULT"
            result = docling_2_md(str(file_path), parser_base_url)
            mock_smol.assert_called_once_with(str(file_path), parser_base_url)
            assert result == "SMOL_RESULT"
    else:
        # Allow real docling_convert to run, but patch DocumentConverter to avoid real file IO
        with patch("flows.preproc.convert.docling_convert") as mock_doc:
            mock_doc.return_value = "DOC_RESULT"
            result = docling_2_md(str(file_path), parser_base_url)
            mock_doc.assert_called_once_with(str(file_path))
            assert result == "DOC_RESULT"
