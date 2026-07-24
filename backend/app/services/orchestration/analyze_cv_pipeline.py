from app.schemas.document import DocumentKind
from app.services.documents.docling_parser import DoclingParser
from app.services.extraction.cv_extractor import CVExtractor


class AnalyzeCVPipeline:
    def __init__(self, parser: DoclingParser, llm_client) -> None:
        self._parser = parser
        self._extractor = CVExtractor(llm_client)

    def run(self, path, filename_override: str | None = None):
        document = self._parser.extract(path, kind=DocumentKind.cv, filename_override=filename_override)
        return document, self._extractor.extract(document)
