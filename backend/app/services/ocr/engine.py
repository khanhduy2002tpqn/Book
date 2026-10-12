import io
import logging
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)


class OCREngineService:
    def __init__(self):
        self.paddle_ocr = None
        self.easy_ocr = None
        self.tesseract_available = False
        self._init_engines()

    def _init_engines(self):
        # 1. Check PaddleOCR
        try:
            from paddleocr import PaddleOCR
            self.paddle_ocr = PaddleOCR(use_angle_cls=True, lang="vi", show_log=False)
            logger.info("OCR Engine: PaddleOCR initialized.")
            return
        except Exception:
            pass

        # 2. Check PyTesseract
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            logger.info("OCR Engine: PyTesseract available.")
            return
        except Exception:
            pass

        # Note: EasyOCR will be lazy-loaded on first call to prevent startup delay

    def _get_easy_ocr(self):
        if self.easy_ocr is None:
            try:
                import easyocr
                logger.info("Initializing EasyOCR reader for ['vi', 'en']...")
                self.easy_ocr = easyocr.Reader(["vi", "en"], gpu=False)
                logger.info("EasyOCR initialized successfully.")
            except Exception as e:
                logger.warning(f"Could not initialize EasyOCR: {e}")
        return self.easy_ocr

    def perform_ocr(self, image_bytes: bytes) -> Tuple[str, float, List[Dict[str, Any]]]:
        """
        Perform OCR on an image byte array.
        Returns:
            - text: extracted string
            - confidence: float between 0.0 and 1.0
            - boxes: list of bounding boxes with text and confidence
        """
        if not image_bytes:
            return "", 0.0, []

        boxes: List[Dict[str, Any]] = []

        # 1. Primary: Gemini Multimodal Vision OCR (Super accurate for Vietnamese & Math)
        try:
            from app.services.gemini import gemini_service
            vision_text = gemini_service.extract_text_from_image(image_bytes)
            if vision_text and vision_text.strip():
                logger.info("Gemini Vision OCR extracted text successfully.")
                return vision_text.strip(), 0.98, []
        except Exception as e:
            logger.warning(f"Gemini Vision OCR fallback to local engines: {e}")

        # 2. Fallback: EasyOCR (Local Deep Learning OCR)
        reader = self._get_easy_ocr()
        if reader is not None:
            try:
                import numpy as np
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_np = np.array(image)
                result = reader.readtext(img_np)
                lines = []
                confidences = []
                for item in result:
                    box, txt, score = item
                    if txt.strip():
                        lines.append(txt.strip())
                        confidences.append(float(score))
                        boxes.append({"box": box, "text": txt, "score": float(score)})

                full_text = "\n".join(lines).strip()
                if full_text:
                    avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.8
                    logger.info(f"EasyOCR extracted {len(lines)} lines successfully.")
                    return full_text, avg_conf, boxes
            except Exception as e:
                logger.warning(f"EasyOCR extraction error: {e}")

        # 3. Fallback: PaddleOCR
        if self.paddle_ocr:
            try:
                import numpy as np
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
                img_np = np.array(image)
                result = self.paddle_ocr.ocr(img_np, cls=True)
                lines = []
                confidences = []
                if result and result[0]:
                    for line in result[0]:
                        box = line[0]
                        txt, score = line[1]
                        if txt.strip():
                            lines.append(txt.strip())
                            confidences.append(float(score))
                            boxes.append({"box": box, "text": txt, "score": float(score)})
                full_text = "\n".join(lines).strip()
                if full_text:
                    avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.8
                    return full_text, avg_conf, boxes
            except Exception as e:
                logger.warning(f"PaddleOCR error: {e}")

        # 4. Fallback: PyTesseract
        if self.tesseract_available:
            try:
                import pytesseract
                image = Image.open(io.BytesIO(image_bytes))
                try:
                    data = pytesseract.image_to_data(image, lang="vie+eng", output_type=pytesseract.Output.DICT)
                except Exception:
                    data = pytesseract.image_to_data(image, lang="eng", output_type=pytesseract.Output.DICT)

                n_boxes = len(data["text"])
                lines = []
                confidences = []
                for i in range(n_boxes):
                    txt = data["text"][i].strip()
                    conf = float(data["conf"][i])
                    if txt and conf > 0:
                        lines.append(txt)
                        confidences.append(conf / 100.0)
                        boxes.append({
                            "box": [data["left"][i], data["top"][i], data["width"][i], data["height"][i]],
                            "text": txt,
                            "score": conf / 100.0
                        })
                full_text = " ".join(lines).strip()
                if full_text:
                    avg_conf = float(sum(confidences) / len(confidences)) if confidences else 0.8
                    return full_text, avg_conf, boxes
            except Exception as e:
                logger.error(f"PyTesseract error: {e}")

        return "", 0.0, []
