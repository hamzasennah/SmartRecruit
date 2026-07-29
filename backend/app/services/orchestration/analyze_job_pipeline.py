from app.schemas.document import DocumentKind
from app.services.documents.docling_parser import DoclingParser
from app.services.extraction.job_extractor import JobExtractor


class AnalyzeJobPipeline:
    def __init__(self, parser: DoclingParser, llm_client) -> None:
        self._parser = parser
        self._extractor = JobExtractor(llm_client)

    def run(self, path, filename_override: str | None = None):
        return self._extractor.extract(
            self._parser.extract(path, kind=DocumentKind.job, filename_override=filename_override)
        )

# Role dans le projet:
# Ce fichier assemble parsing et extraction d'une fiche de poste. Le BatchRankingPipeline l'appelle avant d'analyser les CV.
