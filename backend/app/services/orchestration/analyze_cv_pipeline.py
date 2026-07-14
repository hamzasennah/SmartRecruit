from app.schemas.document import DocumentKind
from app.services.documents.docling_parser import DoclingParser
from app.services.extraction.cv_extractor import CVExtractor


class AnalyzeCVPipeline:
    def __init__(self, parser: DoclingParser, llm_provider) -> None:
        self._parser = parser
        self._extractor = CVExtractor(llm_provider)

    def run(self, path):
        document = self._parser.extract(path, kind=DocumentKind.cv)
        return document, self._extractor.extract(document)

