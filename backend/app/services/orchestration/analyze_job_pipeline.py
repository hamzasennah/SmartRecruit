from app.schemas.document import DocumentKind
from app.services.documents.docling_parser import DoclingParser
from app.services.extraction.job_extractor import JobExtractor


class AnalyzeJobPipeline:
    def __init__(self, parser: DoclingParser, llm_provider) -> None:
        self._parser = parser
        self._extractor = JobExtractor(llm_provider)

    def run(self, path):
        return self._extractor.extract(self._parser.extract(path, kind=DocumentKind.job))

