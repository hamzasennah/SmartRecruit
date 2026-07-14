class SmartRecruitError(RuntimeError):
    pass


class DocumentParsingError(SmartRecruitError):
    pass


class ProviderUnavailableError(SmartRecruitError):
    pass


class OutputValidationError(SmartRecruitError):
    pass

