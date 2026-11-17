"""Remote file fetching utilities for Iragi.

Allows scan(), analyze(), and batch_analyze() to accept HTTP and HTTPS
URLs transparently. Files are downloaded to a secure temporary location,
processed, then removed automatically.

Example:
    >>> from iragi.core.remote import is_remote_url, resolve_file_source
    >>> is_remote_url("https://data.gov/air_quality.csv")
    True
    >>> is_remote_url("/var/data/local.csv")
    False
"""

import ipaddress
import socket
import tempfile
import urllib.request
from pathlib import Path
from typing import Tuple, Union
from urllib.parse import urljoin, urlsplit

from iragi.core.exceptions import IragiDataError

_REMOTE_SCHEMES = ("http://", "https://")
_DEFAULT_MAX_BYTES = 500 * 1024 * 1024  # 500 MB
_DEFAULT_TIMEOUT = 30  # seconds
_CHUNK_SIZE = 8192
_MAX_REDIRECTS = 5


def _validate_remote_url(url: str, allowed_hosts=None) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise IragiDataError("Only HTTP(S) URLs without embedded credentials are allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if allowed_hosts is not None and host not in {h.rstrip(".").lower() for h in allowed_hosts}:
        raise IragiDataError(f"Remote host is not in allowed_hosts: {host}")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        addresses = {item[4][0] for item in socket.getaddrinfo(host, port)}
    except OSError as exc:
        raise IragiDataError(f"Could not resolve remote host '{host}': {exc}") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise IragiDataError(f"Remote host resolves to a private or non-routable address: {host}")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts=None):
        super().__init__()
        self.allowed_hosts = allowed_hosts
        self.redirects = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.redirects += 1
        if self.redirects > _MAX_REDIRECTS:
            raise IragiDataError(f"Remote URL exceeded {_MAX_REDIRECTS} redirects")
        destination = urljoin(req.full_url, newurl)
        _validate_remote_url(destination, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, destination)


def is_remote_url(source: Union[str, Path]) -> bool:
    """Return True if *source* is an HTTP or HTTPS URL string.

    :param source: File path or URL to check.
    :type source: Union[str, Path]
    :return: True when source is a supported HTTP(S) remote URL.
    :rtype: bool

    Example:
        >>> is_remote_url("https://opendata.health.org/trials.csv")
        True
        >>> is_remote_url(Path("relative/file.xlsx"))
        False
    """
    if not isinstance(source, str):
        return False
    lower = source.lower()
    return any(lower.startswith(scheme) for scheme in _REMOTE_SCHEMES)


def fetch_remote_file(
    url: str,
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout: int = _DEFAULT_TIMEOUT,
    allowed_hosts=None,
) -> Path:
    """Download *url* to a local temporary file and return its :class:`~pathlib.Path`.

    Downloads in fixed-size chunks to bound memory usage. Raises
    :class:`~iragi.core.exceptions.IragiDataError` if the payload exceeds
    *max_bytes* or if the network request fails.

    :param url: Remote URL to fetch (HTTP or HTTPS).
    :type url: str
    :param max_bytes: Maximum allowed download size in bytes (default: 500 MB).
    :type max_bytes: int
    :param timeout: Socket timeout in seconds (default: 30).
    :type timeout: int
    :param allowed_hosts: Optional allowlist of permitted host names.
    :type allowed_hosts: Optional[Iterable[str]]
    :return: Path to the downloaded temporary file (caller must delete it).
    :rtype: Path
    :raises IragiDataError: On network failure or payload size violation.

    Example:
        >>> from unittest.mock import MagicMock, patch
        >>> mock_resp = MagicMock()
        >>> mock_resp.read.side_effect = [b"id,val\\n1,2\\n", b""]
        >>> with patch("urllib.request.urlopen", return_value=mock_resp):
        ...     path, _ = resolve_file_source("https://example.com/data.csv")
        ...     path.unlink()
    """
    # Infer file suffix from URL path (Content-Type is unreliable)
    _validate_remote_url(url, allowed_hosts)
    url_path = urlsplit(url).path
    suffix = Path(url_path).suffix or ".tmp"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp_path = Path(tmp.name)
    try:
        opener = urllib.request.build_opener(_SafeRedirectHandler(allowed_hosts))
        response = opener.open(url, timeout=timeout)
        try:
            total = 0
            while True:
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise IragiDataError(
                        f"Remote file exceeds maximum allowed limit of {max_bytes} bytes: {url}"
                    )
                tmp.write(chunk)
        finally:
            response.close()
    except IragiDataError:
        tmp.close()
        tmp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        tmp.close()
        tmp_path.unlink(missing_ok=True)
        raise IragiDataError(f"Failed to fetch remote file '{url}': {exc}") from exc
    finally:
        tmp.close()

    return tmp_path


def resolve_file_source(
    source: Union[str, Path],
    max_bytes: int = _DEFAULT_MAX_BYTES,
    timeout: int = _DEFAULT_TIMEOUT,
    allowed_hosts=None,
) -> Tuple[Path, bool]:
    """Resolve *source* to a local :class:`~pathlib.Path`, downloading if remote.

    Returns a tuple ``(path, is_temp)`` where *is_temp* is ``True`` when a
    temporary file was created and the caller is responsible for deleting it.

    :param source: Local path or remote URL to resolve.
    :type source: Union[str, Path]
    :param max_bytes: Maximum allowed download size in bytes.
    :type max_bytes: int
    :param timeout: Socket timeout in seconds.
    :type timeout: int
    :param allowed_hosts: Optional allowlist of permitted host names.
    :type allowed_hosts: Optional[Iterable[str]]
    :return: Tuple of (resolved local path, is_temporary).
    :rtype: Tuple[Path, bool]

    Example:
        >>> resolve_file_source("/var/data/local.csv")
        (PosixPath('/var/data/local.csv'), False)
    """
    if is_remote_url(source):
        return fetch_remote_file(
            str(source), max_bytes=max_bytes, timeout=timeout, allowed_hosts=allowed_hosts
        ), True
    return Path(source), False
