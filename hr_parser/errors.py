class ParseError(Exception):
    """The resume could not be turned into a profile (message is user-facing)."""


class LLMUnavailable(Exception):
    """The language model server could not be reached (message is user-facing)."""
