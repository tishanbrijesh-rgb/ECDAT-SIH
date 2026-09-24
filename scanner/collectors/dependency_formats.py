"""Pure parsers for supported dependency manifest formats."""

from __future__ import annotations

import json
import re
from typing import Any

import tomllib
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException


def pom_packages(content: str) -> list[tuple[str, str, dict[str, str]]]:
    if "<!DOCTYPE" in content.upper() or "<!ENTITY" in content.upper():
        raise ValueError("unsafe XML declaration")
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise ValueError("invalid POM XML") from exc
    namespace = root.tag.split("}")[0] + "}" if root.tag.startswith("{") else ""
    result = []
    for dependency in root.findall(f"{namespace}dependencies/{namespace}dependency"):
        group = (dependency.findtext(f"{namespace}groupId") or "").strip()
        artifact = (dependency.findtext(f"{namespace}artifactId") or "").strip()
        if group and artifact:
            result.append((group.lower(), f"{group.lower()}:{artifact}", {"groupId": group, "artifactId": artifact}))
    return result


def npm_packages(content: str) -> list[tuple[str, dict[str, str]]]:
    data = json.loads(content)
    version = str(data.get("lockfileVersion", ""))
    combined = dict(data.get("packages", {}) or {})
    for name, info in (data.get("dependencies", {}) or {}).items():
        combined.setdefault(name, info)
    result = []
    for name, info in combined.items():
        if name:
            package = name.rsplit("/", 1)[-1]
            package = re.split(r"[<>=!~\[;@#\s]", package.lower())[0]
            package = re.sub(r"[-_.]+", "-", package.strip())
            item_version = info.get("version", "") if isinstance(info, dict) else ""
            result.append((package, {"package": package, "version": item_version, "lockfile_version": version}))
    return result


def gem_packages(content: str) -> list[tuple[str, dict[str, str]]]:
    result = []
    for line in content.splitlines():
        match = re.match(r"^\s+([A-Za-z0-9_.-]+)\s*\(", line)
        if match:
            package = re.sub(r"[-_.]+", "-", match.group(1).lower())
            result.append((package, {"package": package, "spec": line.strip()}))
    return result


def go_packages(content: str) -> list[tuple[str, dict[str, str]]]:
    result = []
    for line in content.splitlines():
        parts = line.split()
        if len(parts) >= 2:
            module = parts[0].strip()
            result.append((module.lower(), {"package": module}))
    return result


def cargo_packages(content: str) -> list[tuple[str, dict[str, Any]]]:
    packages = tomllib.loads(content).get("package", [])
    if isinstance(packages, dict):
        packages = packages.get("package", [])
    return [
        (str(item.get("name", "")).lower(), {"package": item.get("name", ""), "version": item.get("version", "")})
        for item in packages
        if isinstance(item, dict) and item.get("name")
    ]
