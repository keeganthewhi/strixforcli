"""File-permission enforcement on secrets / config files.

On POSIX: any group or other bits set is a fail.
On Windows: we cannot portably check NTFS ACLs without pywin32; treat as
advisory (return True) unless STRIX_ENFORCE_WINDOWS_ACL=1.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path


def check_permissions(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f"{path} does not exist"
    if os.name == "nt":
        if os.environ.get("STRIX_ENFORCE_WINDOWS_ACL", "0") == "1":
            return _check_windows(path)
        return True, "windows: ACL check skipped"
    return _check_posix(path)


def _check_posix(path: Path) -> tuple[bool, str]:
    mode = path.stat().st_mode & 0o777
    offenders = mode & 0o077
    if offenders:
        return False, f"mode {oct(mode)} is loose; run `chmod 600 {path}`"
    return True, f"mode {oct(mode)}"


def _check_windows(path: Path) -> tuple[bool, str]:
    try:
        import win32api  # type: ignore
        import win32security  # type: ignore
    except ImportError:
        return True, "windows: pywin32 not installed, ACL check skipped"

    sd = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION)
    dacl = sd.GetSecurityDescriptorDacl()
    if dacl is None:
        return False, "no DACL present"
    user_sid, _, _ = win32security.LookupAccountName(None, win32api.GetUserName())
    for i in range(dacl.GetAceCount()):
        ace = dacl.GetAce(i)
        sid = ace[2]
        if sid != user_sid:
            sid_name, _, _ = win32security.LookupAccountSid(None, sid)
            if sid_name.lower() not in {"system", "administrators"}:
                return False, f"extra ACE grants access to {sid_name}"
    return True, "windows: user-only DACL"


def enforce_0o600(path: Path) -> None:
    """Chmod a file to 0o600 on POSIX. No-op on Windows."""
    if os.name == "nt":
        return
    path.chmod(0o600)


def verify_or_raise(path: Path) -> None:
    if os.environ.get("STRIX_ENFORCE_PERMISSIONS", "1") != "1":
        return
    ok, reason = check_permissions(path)
    if not ok:
        raise PermissionError(f"permission check failed on {path}: {reason}")
