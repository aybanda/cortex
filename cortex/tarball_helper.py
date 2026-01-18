"""
tarball_helper.py - Tarball/Manual Build Helper for Cortex Linux

Features:
1. Analyze build files (configure, CMakeLists.txt, meson.build, etc.) for requirements
2. Install missing -dev packages automatically
3. Track manual installations for cleanup
4. Suggest package alternatives when available

Usage:
  cortex tarball-helper analyze <path>
  cortex tarball-helper install-deps <path>
  cortex tarball-helper track <package>
  cortex tarball-helper cleanup
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

MANUAL_TRACK_FILE = Path.home() / ".cortex" / "manual_builds.json"
console = Console()


class TarballHelper:
    def __init__(self):
        self.tracked_packages = self._load_tracked_packages()

    def _load_tracked_packages(self) -> list[str]:
        if MANUAL_TRACK_FILE.exists():
            with open(MANUAL_TRACK_FILE) as f:
                return json.load(f).get("packages", [])
        return []

    def _save_tracked_packages(self):
        MANUAL_TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MANUAL_TRACK_FILE, "w") as f:
            json.dump({"packages": self.tracked_packages}, f, indent=2)

    def analyze(self, path: str) -> list[str]:
        """Analyze build files for dependencies."""
        deps = set()
        for root, _, files in os.walk(path):
            for fname in files:
                if fname in (
                    "CMakeLists.txt",
                    "configure.ac",
                    "meson.build",
                    "Makefile",
                    "setup.py",
                ):
                    fpath = os.path.join(root, fname)
                    with open(fpath, errors="ignore") as f:
                        content = f.read()
                        deps.update(self._parse_dependencies(fname, content))
        return list(deps)

    def _parse_dependencies(self, fname: str, content: str) -> list[str]:
        # Simple regex-based extraction for common build files
        patterns = {
            "CMakeLists.txt": r"find_package\((\w+)",
            "meson.build": r"dependency\(['\"](\w+)",
            "configure.ac": r"AC_CHECK_LIB\(\[?(\w+)",
            "Makefile": r"-l(\w+)",
            "setup.py": r"install_requires=\[(.*?)\]",
        }
        deps = set()
        if fname in patterns:
            matches = re.findall(patterns[fname], content, re.DOTALL)
            if fname == "setup.py":
                # Parse Python list
                for m in matches:
                    deps.update(re.findall(r"['\"]([\w\-]+)['\"]", m))
            else:
                deps.update(matches)
        return list(deps)

    def suggest_apt_packages(self, deps: list[str]) -> dict[str, str]:
        """Map dependency names to apt packages (simple heuristic)."""
        mapping = {}
        for dep in deps:
            pkg = f"lib{dep.lower()}-dev"
            mapping[dep] = pkg
        return mapping

    def install_deps(self, pkgs: list[str]):
        """Install missing -dev packages via apt."""
        import subprocess

        for pkg in pkgs:
            console.print(f"[cyan]Installing:[/cyan] {pkg}")
            subprocess.run(["sudo", "apt-get", "install", "-y", pkg], check=False)
            self.track(pkg)

    def track(self, pkg: str):
        if pkg not in self.tracked_packages:
            self.tracked_packages.append(pkg)
            self._save_tracked_packages()
            console.print(f"[green]Tracked:[/green] {pkg}")

    def cleanup(self):
        import subprocess

        for pkg in self.tracked_packages:
            console.print(f"[yellow]Removing:[/yellow] {pkg}")
            subprocess.run(["sudo", "apt-get", "remove", "-y", pkg], check=False)
        self.tracked_packages = []
        self._save_tracked_packages()
        console.print("[green]Cleanup complete.[/green]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Tarball/Manual Build Helper")
    subparsers = parser.add_subparsers(dest="command")

    analyze_p = subparsers.add_parser("analyze", help="Analyze build files for dependencies")
    analyze_p.add_argument("path", help="Path to source directory")

    install_p = subparsers.add_parser("install-deps", help="Install missing -dev packages")
    install_p.add_argument("path", help="Path to source directory")

    cleanup_p = subparsers.add_parser("cleanup", help="Remove tracked packages")

    args = parser.parse_args()
    helper = TarballHelper()

    if args.command == "analyze":
        deps = helper.analyze(args.path)
        mapping = helper.suggest_apt_packages(deps)
        table = Table(title="Suggested apt packages")
        table.add_column("Dependency")
        table.add_column("Apt Package")
        for dep, pkg in mapping.items():
            table.add_row(dep, pkg)
        console.print(table)
    elif args.command == "install-deps":
        deps = helper.analyze(args.path)
        mapping = helper.suggest_apt_packages(deps)
        helper.install_deps(list(mapping.values()))
    elif args.command == "cleanup":
        helper.cleanup()
    else:
        parser.print_help()
