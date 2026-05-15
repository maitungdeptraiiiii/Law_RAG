from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree

import fitz


OCRLanguage = Literal["vi", "en", "mixed"]


@dataclass
class OCRPage:
    page_number: int
    text: str
    confidence: float
    source: str


@dataclass
class OCRDocument:
    text: str
    confidence: float
    pages: list[OCRPage]
    engine: str


class OCREngineUnavailable(RuntimeError):
    pass


def extract_document_text(path: Path, file_type: str, language: OCRLanguage = "vi") -> OCRDocument:
    if file_type == "pdf":
        return _extract_pdf(path, language)
    if file_type == "image":
        page = _ocr_image_bytes(path.read_bytes(), language, page_number=1)
        return OCRDocument(
            text=page.text,
            confidence=page.confidence,
            pages=[page],
            engine=page.source,
        )
    if file_type == "docx":
        return _extract_docx(path)
    raise ValueError(f"Unsupported file type: {file_type}")


def _extract_pdf(path: Path, language: OCRLanguage) -> OCRDocument:
    pages: list[OCRPage] = []
    with fitz.open(path) as document:
        for page_index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append(OCRPage(page_index, text, 1.0, "pdf_text"))
                continue

            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            pages.append(_ocr_image_bytes(pixmap.tobytes("png"), language, page_index))

    text = "\n\n".join(page.text for page in pages if page.text.strip()).strip()
    confidence = _average_confidence([page.confidence for page in pages])
    engine = "pdf_text" if all(page.source == "pdf_text" for page in pages) else "ocr"
    return OCRDocument(text=text, confidence=confidence, pages=pages, engine=engine)


def _extract_docx(path: Path) -> OCRDocument:
    try:
        with zipfile.ZipFile(path) as archive:
            payload = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile) as exc:
        raise ValueError("DOCX file is invalid or unsupported.") from exc

    root = ElementTree.fromstring(payload)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        parts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        line = "".join(parts).strip()
        if line:
            paragraphs.append(line)

    text = "\n".join(paragraphs).strip()
    page = OCRPage(page_number=1, text=text, confidence=1.0 if text else 0.0, source="docx_text")
    return OCRDocument(text=text, confidence=page.confidence, pages=[page], engine="docx_text")


def _ocr_image_bytes(image_bytes: bytes, language: OCRLanguage, page_number: int) -> OCRPage:
    try:
        return _ocr_with_tesseract(image_bytes, language, page_number)
    except OCREngineUnavailable:
        pass

    try:
        return _ocr_with_paddleocr(image_bytes, language, page_number)
    except OCREngineUnavailable as exc:
        raise OCREngineUnavailable(
            "No OCR engine is available. Install Tesseract with Vietnamese language data "
            "or install PaddleOCR to process scanned PDFs and image uploads."
        ) from exc


def _ocr_with_tesseract(image_bytes: bytes, language: OCRLanguage, page_number: int) -> OCRPage:
    try:
        from PIL import Image
        import pytesseract
        from pytesseract import Output
    except ImportError as exc:
        raise OCREngineUnavailable("pytesseract/Pillow is not installed.") from exc

    image = Image.open(io.BytesIO(image_bytes))
    tesseract_lang = {"vi": "vie+eng", "en": "eng", "mixed": "vie+eng"}[language]
    _configure_tesseract_command(pytesseract)
    try:
        text = pytesseract.image_to_string(image, lang=tesseract_lang).strip()
    except Exception as exc:
        raise OCREngineUnavailable(f"Tesseract OCR is not ready: {exc}") from exc

    confidence = 0.0
    try:
        data = pytesseract.image_to_data(image, lang=tesseract_lang, output_type=Output.DICT)
        values = [float(value) for value in data.get("conf", []) if str(value).strip() not in {"", "-1"}]
        confidence = _average_confidence([value / 100 for value in values])
    except Exception:
        confidence = 0.0

    return OCRPage(page_number=page_number, text=text, confidence=confidence, source="tesseract")


def _configure_tesseract_command(pytesseract_module: object) -> None:
    configured_path = os.getenv("TESSERACT_CMD")
    candidates = [
        configured_path,
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            pytesseract_module.pytesseract.tesseract_cmd = candidate
            return


def _ocr_with_paddleocr(image_bytes: bytes, language: OCRLanguage, page_number: int) -> OCRPage:
    try:
        import numpy as np
        from PIL import Image
        from paddleocr import PaddleOCR
    except ImportError as exc:
        raise OCREngineUnavailable("PaddleOCR dependencies are not installed.") from exc

    paddle_lang = "vi" if language in {"vi", "mixed"} else "en"
    ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)
    image = np.array(Image.open(io.BytesIO(image_bytes)).convert("RGB"))
    result = ocr.ocr(image, cls=True)
    lines = result[0] if result else []

    text_parts: list[str] = []
    confidences: list[float] = []
    for line in lines or []:
        if len(line) < 2:
            continue
        payload = line[1]
        if not isinstance(payload, (list, tuple)) or len(payload) < 2:
            continue
        text_parts.append(str(payload[0]))
        try:
            confidences.append(float(payload[1]))
        except (TypeError, ValueError):
            pass

    return OCRPage(
        page_number=page_number,
        text="\n".join(text_parts).strip(),
        confidence=_average_confidence(confidences),
        source="paddleocr",
    )


def _average_confidence(values: list[float]) -> float:
    valid = [max(0.0, min(1.0, value)) for value in values if value >= 0]
    if not valid:
        return 0.0
    return sum(valid) / len(valid)
