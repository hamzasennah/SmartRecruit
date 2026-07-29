class SmartRecruitError(RuntimeError):
    pass


class DocumentParsingError(SmartRecruitError):
    pass


class ExternalServiceError(SmartRecruitError):
    pass


class OutputValidationError(SmartRecruitError):
    pass

# Role dans le projet:
# Ce fichier definit les exceptions metier. Il permet aux routes de transformer les echecs internes en reponses HTTP coherentes.
