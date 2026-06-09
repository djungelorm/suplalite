from tlslite.utils.rsakey import RSAKey

class X509:
    def parse(self, s: str) -> None: ...

class X509CertChain:
    def __init__(self, certs: list[X509] = ...) -> None: ...

class SessionCache: ...

def parsePEMKey(s: str, private: bool = ...) -> RSAKey: ...  # noqa: N802
