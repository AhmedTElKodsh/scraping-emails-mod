import re

from email_validator import EmailNotValidError, validate_email

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}")
_JUNK_PREFIXES = frozenset({"noreply", "no-reply", "donotreply", "mailer-daemon", "postmaster"})
_CFEMAIL_RE = re.compile(r'data-cfemail="([0-9a-fA-F]+)"')
_OBFUSCATION_RE = re.compile(r"\s*\[at\]\s*|\s*\(at\)\s*|\s+at\s+", re.IGNORECASE)


def decode_cfemail(encoded: str) -> str:
    data = bytes.fromhex(encoded)
    key = data[0]
    return "".join(chr(b ^ key) for b in data[1:])


def _is_valid(email: str) -> bool:
    local = email.split("@")[0].lower()
    if local in _JUNK_PREFIXES:
        return False
    try:
        validate_email(email, check_deliverability=False)
        return True
    except EmailNotValidError:
        return False


def _add_if_valid(email: str, seen: set[str], found: list[str]) -> None:
    canonical = email.lower().strip()
    if canonical and canonical not in seen and _is_valid(canonical):
        seen.add(canonical)
        found.append(canonical)


def extract_emails(html: str | None, seen: set[str]) -> list[str]:
    if html is None:
        return []
    found: list[str] = []
    for raw in _EMAIL_RE.findall(html):
        _add_if_valid(raw, seen, found)
    for encoded in _CFEMAIL_RE.findall(html):
        try:
            decoded = decode_cfemail(encoded)
            _add_if_valid(decoded, seen, found)
        except (ValueError, IndexError):
            pass
    deobf = _OBFUSCATION_RE.sub("@", html)
    for raw in _EMAIL_RE.findall(deobf):
        _add_if_valid(raw, seen, found)
    return found
