"""Metadata-only QQ Finance handoff probe. Never import or execute target code."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess
import sys

EXPECTED_HERMES = "4ca5aa4f9a5f347446a537a7b00df81c3e0ef559"
SERVICES = ("hermes-gateway.service", "hermes-finance.service")


def read_regular(path: Path, limit: int = 4096) -> bytes:
    """Reject links, devices and FIFOs before opening bounded metadata."""
    path = path.absolute()
    for parent in reversed(path.parents):
        if stat.S_ISLNK(parent.lstat().st_mode):
            raise ValueError("unsafe_metadata")
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise ValueError("unsafe_metadata")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                         | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if (not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)):
            raise ValueError("metadata_changed")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("oversized_metadata")
    return data


def source_pointer(directory: Path) -> str:
    """Read only HEAD/ref metadata; no Git, config, filters or hooks execute."""
    git = directory / ".git"
    head = read_regular(git / "HEAD").decode("ascii").strip()
    if re.fullmatch(r"[0-9a-f]{40}", head):
        return head
    if not head.startswith("ref: "):
        raise ValueError("unknown_head")
    ref = head[5:]
    if (not re.fullmatch(r"refs/heads/[A-Za-z0-9_./-]+", ref)
            or any(part in ("", ".", "..") for part in ref.split("/"))):
        raise ValueError("unsafe_ref")
    try:
        value = read_regular(git / ref).decode("ascii").strip()
    except FileNotFoundError:
        lines = read_regular(git / "packed-refs", 262144).decode("ascii").splitlines()
        matches = [line.split()[0] for line in lines if line.endswith(" " + ref)]
        if len(matches) != 1:
            raise ValueError("unknown_ref")
        value = matches[0]
    if not re.fullmatch(r"[0-9a-f]{40}", value):
        raise ValueError("invalid_ref")
    return value


def service_metadata(service: str) -> dict[str, str]:
    if service not in SERVICES:
        raise ValueError("unsupported_service")
    runtime = "/run/user/" + str(os.getuid())
    result = subprocess.run(
        ["/usr/bin/systemctl", "--user", "--no-pager", "show",
         "--property=ActiveState,SubState,MainPID", "--", service],
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "XDG_RUNTIME_DIR": runtime,
             "DBUS_SESSION_BUS_ADDRESS": "unix:path=" + runtime + "/bus"},
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=5, check=False,
    )
    if result.returncode or len(result.stdout) > 1024:
        raise ValueError("service_unavailable")
    fields = dict(line.split("=", 1) for line in result.stdout.decode("ascii").splitlines())
    if set(fields) != {"ActiveState", "SubState", "MainPID"}:
        raise ValueError("invalid_service_metadata")
    return fields


def process_metadata(pid: int) -> tuple[str, Path, bytes]:
    root = Path("/proc") / str(pid)
    # /proc links are intentionally resolved only to identify this service's
    # executable/cwd. No argv, environ, maps, descriptors or user files are read.
    raw = read_regular(root / "stat")
    # Field 22 (starttime) remains stable while CPU counters change.
    suffix = raw.rsplit(b") ", 1)[1].split()
    stamp = suffix[19]
    if not stamp.isdigit():
        raise ValueError("invalid_process_stamp")
    return os.readlink(root / "exe"), (root / "cwd").resolve(strict=True), stamp


def inspect_source(directory: Path) -> list[tuple[str, str, str]]:
    rows = []
    try:
        matches = source_pointer(directory) == EXPECTED_HERMES
        rows.append(("PASS" if matches else "BLOCKED", "gateway_source_pointer",
                     "REVIEWED_POINTER" if matches else "POINTER_MISMATCH"))
    except (OSError, ValueError, UnicodeError):
        rows.append(("UNVERIFIED", "gateway_source_pointer", "POINTER_UNAVAILABLE"))
    try:
        read_regular(directory / "gateway/platforms/qqbot/finance_intent_router.py", 65536)
        rows.append(("UNVERIFIED", "intake_factory", "SOURCE_PRESENT_NOT_LOADED"))
    except (OSError, ValueError):
        rows.append(("BLOCKED", "intake_factory", "SOURCE_UNAVAILABLE"))
    rows.append(("UNVERIFIED", "source_integrity", "WORKTREE_NOT_ATTESTED"))
    return rows


def collect() -> list[tuple[str, str, str]]:
    rows = []
    if not sys.platform.startswith("linux"):
        return [("UNVERIFIED", "platform", "LINUX_REQUIRED")]
    for service in SERVICES:
        label = "gateway" if service == SERVICES[0] else "finance"
        try:
            fields = service_metadata(service)
            pid = fields["MainPID"]
            if fields["ActiveState"] != "active" or fields["SubState"] != "running" or not re.fullmatch(r"[1-9][0-9]{0,9}", pid):
                rows.append(("BLOCKED", label + "_service", "NOT_RUNNING"))
                continue
            executable, cwd, stamp = process_metadata(int(pid))
            observed = []
            if label == "gateway":
                observed = inspect_source(cwd)
            # Verify the same service PID and process snapshot after metadata IO.
            if service_metadata(service) != fields or process_metadata(int(pid)) != (executable, cwd, stamp):
                raise ValueError("process_changed")
            rows.append(("PASS", label + "_service", "ACTIVE_RUNNING_SNAPSHOT"))
            name = Path(executable).name
            match = re.fullmatch(r"python(3\.(?:10|11|12|13|14))", name)
            reason = "PYTHON_" + match[1].replace(".", "_") + "_NAME_ONLY" if match else "INTERPRETER_UNATTESTED"
            rows.append(("UNVERIFIED", label + "_python", reason))
            rows.extend(observed)
        except (OSError, ValueError, UnicodeError, IndexError, subprocess.SubprocessError):
            rows.append(("UNVERIFIED", label + "_service", "METADATA_UNAVAILABLE_OR_CHANGED"))
    rows.extend([
        ("UNVERIFIED", "companion", "RUNNING_IMPORT_NOT_ATTESTED"),
        ("UNVERIFIED", "runtime_version", "RUNNING_BYTES_NOT_ATTESTED"),
        ("UNVERIFIED", "configuration", "LOCAL_PRIVATE_REVIEW_REQUIRED"),
        ("UNVERIFIED", "qq_acceptance", "MANUAL_ACCEPTANCE_REQUIRED"),
    ])
    return rows


def main(argv=None) -> int:
    # No path/config arguments: unknown arguments also receive constant output.
    if argv is None:
        argv = sys.argv[1:]
    try:
        rows = [("BLOCKED", "tool", "NO_ARGUMENTS_ALLOWED")] if argv else collect()
    except (Exception, KeyboardInterrupt):
        rows = [("UNVERIFIED", "tool", "PROBE_UNAVAILABLE")]
    for status, check, reason in rows:
        print(status, check, reason)
    return 3 if any(row[0] == "BLOCKED" for row in rows) else 2 if any(row[0] == "UNVERIFIED" for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
