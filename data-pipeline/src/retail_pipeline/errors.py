"""Errors that stop a pipeline run with an actionable message."""


class PipelineError(Exception):
    """Base class for expected pipeline failures."""


class SchemaMismatchError(PipelineError):
    """A source file does not match its declared table specification."""


class MissingSourceFileError(PipelineError):
    """A file required by a source specification is absent."""


class ManifestError(PipelineError):
    """A landing manifest is missing, malformed, or incomplete."""


class LakekeeperError(PipelineError):
    """The Lakekeeper management API returned an unexpected response."""


class VerificationError(PipelineError):
    """Committed data does not match the landed source files."""
