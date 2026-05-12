class CadGenerationError(RuntimeError):
    pass


class OpenVspUnavailableError(CadGenerationError):
    pass


class UnsupportedGeometryError(CadGenerationError):
    pass
