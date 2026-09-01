from __future__ import annotations


class ProfileLibraryError(Exception):
    """Base error for profile and library operations."""


class NotFoundError(ProfileLibraryError):
    """Requested profile or library row does not exist for the scoped profile."""


class DuplicateProfileNameError(ProfileLibraryError):
    """Profile display name is already in use."""


class SearchExpiredError(ProfileLibraryError):
    """Search identity is no longer available in the in-memory index."""


class SearchJobNotFoundError(ProfileLibraryError):
    """Search exists but does not contain the requested provider job identity."""
