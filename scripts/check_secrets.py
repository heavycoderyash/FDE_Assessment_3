"""Scan tracked submission files without printing any matched credential."""
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
patterns = [re.compile(rb"sk-[A-Za-z0-9_-]{20,}"), re.compile(rb"AIza[0-9A-Za-z_-]{35}"), re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
            re.compile(rb"AKIA[0-9A-Z]{16}"), re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")]
bad, count = [], 0
for name in filter(None, names):
    path = ROOT/name
    if path.name == ".env": bad.append(name+": environment file tracked")
    if not path.is_file(): continue
    content = path.read_bytes()
    if b"\0" in content: continue
    count += 1
    if any(pattern.search(content) for pattern in patterns): bad.append(name+": possible credential")
if bad:
    print("Secret scan failed:\n"+"\n".join(bad))
    raise SystemExit(1)
print(f"Secret scan passed: {count} tracked text files; no credential patterns or tracked .env.")
