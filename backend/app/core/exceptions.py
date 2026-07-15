class SmartRecruitError(RuntimeError):
    pass


class DocumentParsingError(SmartRecruitError):
    pass


class ExternalServiceError(SmartRecruitError):
    pass


class OutputValidationError(SmartRecruitError):
    pass
