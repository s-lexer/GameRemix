"""Download a pinned official GameRemix release and extract only its managed resources.

The signed executable is never run. PowerShell ReflectionOnlyLoadFrom reads .NET
metadata/resources, allowing a complete *compile* from public C# sources
without separately redistributing copyrighted third-party binaries.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RELEASES = {
    "1.0.38": {
        "sha256": "304952ae944e8acc0d0230c0cd33d12abc415b51c4302a4182e4bfd8f5f8f2c7",
        "url": "https://gameremix.pro/dl/GameRemix-1.0.38.exe",
        "resources": 106,
    },
    "1.0.39": {
        "sha256": "9d13de533b28432d9ba3ca72b7056042781b6a3f3c18b8add126ade380ded729",
        "url": "https://gameremix.pro/dl/GameRemix-1.0.39.exe",
        "resources": 106,
    },
}


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download_official(url, target):
    req = urllib.request.Request(url, headers={"User-Agent": "GameRemix-source-build/1.0"})
    tmp = target.with_suffix(".download")
    tmp.unlink(missing_ok=True)
    size = 0
    try:
        with urllib.request.urlopen(req, timeout=45) as resp, open(tmp, "wb") as out:
            if resp.geturl().split("/")[2].lower() != "gameremix.pro":
                raise RuntimeError("Unexpected download redirect host")
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > 40 * 1024 * 1024:
                    raise RuntimeError("Release exceeds expected size limit")
                out.write(chunk)
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)


def validate_manifest(folder, expected_hash, expected_count, trusted):
    manifest_file = folder / "manifest.json"
    if not manifest_file.is_file():
        return None
    try:
        obj = json.loads(manifest_file.read_text(encoding="utf-8-sig"))
        if obj.get("release_sha256") != expected_hash:
            return None
        items = obj["resources"]
        if items != trusted["resources"]:
            return None
        if len(items) != expected_count or len({r["name"] for r in items}) != len(items):
            return None
        if any(
            not r["filename"].endswith(".bin")
            or Path(r["filename"]).name != r["filename"]
            or not (folder / r["filename"]).is_file()
            or file_sha256(folder / r["filename"]) != r["sha256"]
            for r in items
        ):
            return None
        return obj
    except (OSError, ValueError, KeyError, TypeError):
        return None


def bootstrap(version, release_exe=None):
    release = RELEASES[version]
    expected_hash = release["sha256"]
    folder = ROOT / "dist" / "release-assets" / version
    folder.mkdir(parents=True, exist_ok=True)
    trusted_file = ROOT / "tools" / ("release-resources-" + version + ".json")
    trusted = json.loads(trusted_file.read_text(encoding="utf-8-sig"))
    if trusted["release_sha256"] != expected_hash or len(trusted["resources"]) != release["resources"]:
        raise RuntimeError("The version-pinned source resource manifest is inconsistent")
    cached = validate_manifest(folder, expected_hash, release["resources"], trusted)
    if cached:
        print("Cached signed-release resources verified (%d resources)" % len(cached["resources"]), flush=True)
        return folder

    if release_exe:
        exe = Path(release_exe).resolve()
        if not exe.is_file():
            raise FileNotFoundError(exe)
    else:
        exe = folder / ("GameRemix-" + version + "-official.exe")
        if not exe.is_file() or file_sha256(exe) != expected_hash:
            print("Downloading official signed GameRemix " + version, flush=True)
            download_official(release["url"], exe)
    digest = file_sha256(exe)
    if digest != expected_hash:
        raise RuntimeError("Release SHA-256 mismatch: " + digest + " expected " + expected_hash)
    print("Official release SHA-256 verified: " + digest, flush=True)

    extractor = ROOT / "tools" / "extract_release_assets.ps1"
    powershell = os.environ.get("SystemRoot", r"C:\Windows") + r"\System32\WindowsPowerShell\v1.0\powershell.exe"
    if not os.path.isfile(powershell):
        powershell = "powershell"
    result = subprocess.run([
        powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", str(extractor), "-AssemblyPath", str(exe), "-Destination", str(folder),
        "-ReleaseSha256", expected_hash,
    ], text=True, encoding="utf-8", errors="replace", capture_output=True)
    if result.returncode:
        raise RuntimeError("Resource extraction failed: " + result.stdout[-2500:] + result.stderr[-2500:])
    cached = validate_manifest(folder, expected_hash, release["resources"], trusted)
    if not cached:
        raise RuntimeError("Extracted resource hashes do not match pinned source manifest")
    print("Extracted and SHA-256 checked %d manifest resources" % len(cached["resources"]), flush=True)
    return folder


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--version", choices=sorted(RELEASES), required=True)
    p.add_argument("--release-exe", help="Use a locally obtained official release rather than downloading")
    args = p.parse_args()
    print(bootstrap(args.version, args.release_exe))


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        sys.exit("BOOTSTRAP FAILED: " + str(ex))
