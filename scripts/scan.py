#!/usr/bin/env python3
"""Scan system for available programming language runtimes."""

import json
import platform
import shutil
import subprocess
import sys

LANGUAGE_REGISTRY = {
    "python": {
        "label": "Python 3",
        "binaries": ["python3", "python", "py"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install Python.Python.3",
            "linux": "sudo apt install python3",
            "macos": "brew install python3",
        },
    },
    "cpp": {
        "label": "C++17 (g++)",
        "binaries": ["g++"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install MSYS2.MSYS2",
            "linux": "sudo apt install g++",
            "macos": "xcode-select --install",
        },
    },
    "c": {
        "label": "C11 (gcc)",
        "binaries": ["gcc"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install MSYS2.MSYS2",
            "linux": "sudo apt install gcc",
            "macos": "xcode-select --install",
        },
    },
    "java": {
        "label": "Java",
        "binaries": ["java"],
        "extra_binaries": ["javac"],
        "version_cmd": ["{bin}", "-version"],
        "install": {
            "windows": "winget install EclipseAdoptium.Temurin.17.JDK",
            "linux": "sudo apt install openjdk-17-jdk",
            "macos": "brew install openjdk@17",
        },
    },
    "node": {
        "label": "Node.js",
        "binaries": ["node"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install OpenJS.NodeJS.LTS",
            "linux": "sudo apt install nodejs npm",
            "macos": "brew install node",
        },
    },
    "go": {
        "label": "Go",
        "binaries": ["go"],
        "version_cmd": ["{bin}", "version"],
        "install": {
            "windows": "winget install GoLang.Go",
            "linux": "sudo apt install golang-go",
            "macos": "brew install go",
        },
    },
    "rust": {
        "label": "Rust",
        "binaries": ["rustc"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install Rustlang.Rustup",
            "linux": "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
            "macos": "brew install rustup && rustup-init",
        },
    },
    "csharp": {
        "label": "C# (.NET)",
        "binaries": ["dotnet"],
        "version_cmd": ["{bin}", "--version"],
        "install": {
            "windows": "winget install Microsoft.DotNet.SDK.8",
            "linux": "sudo apt install dotnet-sdk-8.0",
            "macos": "brew install dotnet-sdk",
        },
    },
    "ruby": {
        "label": "Ruby",
        "binaries": ["ruby"],
        "version_cmd": ["{bin}", "--version"],
        "optional": True,
        "install": {
            "windows": "winget install RubyInstallerTeam.Ruby.3.2",
            "linux": "sudo apt install ruby",
            "macos": "brew install ruby",
        },
    },
    "php": {
        "label": "PHP",
        "binaries": ["php"],
        "version_cmd": ["{bin}", "--version"],
        "optional": True,
        "install": {
            "windows": "winget install PHP.PHP.8.3",
            "linux": "sudo apt install php-cli",
            "macos": "brew install php",
        },
    },
    "kotlin": {
        "label": "Kotlin",
        "binaries": ["kotlinc"],
        "extra_binaries": ["java"],
        "version_cmd": ["{bin}", "-version"],
        "optional": True,
        "install": {
            "windows": "winget install JetBrains.Kotlin.Compiler",
            "linux": "sudo snap install kotlin --classic",
            "macos": "brew install kotlin",
        },
    },
    "lua": {
        "label": "Lua",
        "binaries": ["lua", "lua54", "lua53"],
        "version_cmd": ["{bin}", "-v"],
        "optional": True,
        "install": {
            "windows": "choco install lua",
            "linux": "sudo apt install lua5.4",
            "macos": "brew install lua",
        },
    },
    "perl": {
        "label": "Perl",
        "binaries": ["perl"],
        "version_cmd": ["{bin}", "--version"],
        "optional": True,
        "install": {
            "windows": "winget install StrawberryPerl.StrawberryPerl",
            "linux": "sudo apt install perl",
            "macos": "brew install perl",
        },
    },
    "r": {
        "label": "R",
        "binaries": ["Rscript"],
        "version_cmd": ["{bin}", "--version"],
        "optional": True,
        "install": {
            "windows": "winget install RProject.R",
            "linux": "sudo apt install r-base",
            "macos": "brew install r",
        },
    },
}

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"


def detect_os():
    s = platform.system().lower()
    if s == "darwin":
        return "macos"
    if s == "linux":
        return "linux"
    return "windows"


def get_version(version_cmd, binary_path):
    try:
        cmd = [binary_path if p == "{bin}" else p for p in version_cmd]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        for line in (r.stdout or r.stderr or "").strip().splitlines():
            if line.strip():
                return line.strip()
    except Exception:
        pass
    return None


def scan():
    results = []
    for key, info in LANGUAGE_REGISTRY.items():
        found = None
        for candidate in info["binaries"]:
            path = shutil.which(candidate)
            if path:
                found = path
                break

        extras_ok = all(
            shutil.which(b) for b in info.get("extra_binaries", [])
        )
        installed = bool(found) and extras_ok
        version = get_version(info["version_cmd"], found) if found else None

        results.append({
            "key": key,
            "label": info["label"],
            "installed": installed,
            "optional": info.get("optional", False),
            "binary_path": found,
            "version": version,
            "install": info["install"],
        })
    return results


def print_status(results):
    current_os = detect_os()
    core = [r for r in results if not r["optional"]]
    optional = [r for r in results if r["optional"]]

    print()
    print(f"{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  Mini OJ - Language Runtime Scanner{RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")
    print(f"  OS: {platform.system()} {platform.release()}")
    print()

    icon = lambda ok: f"{GREEN}OK{RESET}" if ok else f"{RED}--{RESET}"

    print(f"{BOLD}  Core:{RESET}")
    print(f"  {'-' * 46}")
    for r in core:
        ver = f" {DIM}{r['version']}{RESET}" if r["version"] else ""
        path = f"\n     {DIM}{r['binary_path']}{RESET}" if r["binary_path"] else ""
        print(f"  [{icon(r['installed'])}]  {r['label']:<16}{ver}{path}")

    n = sum(1 for r in core if r["installed"])
    print(f"\n  {n}/{len(core)} core languages ready.")

    if optional:
        print(f"\n{BOLD}  Optional:{RESET}")
        print(f"  {'-' * 46}")
        for r in optional:
            ver = f" {DIM}{r['version']}{RESET}" if r["version"] else ""
            print(f"  [{icon(r['installed'])}]  {r['label']:<16}{ver}")

    missing = [r for r in results if not r["installed"]]
    if missing:
        print(f"\n{YELLOW}{BOLD}  Install commands ({current_os}):{RESET}")
        print(f"  {'-' * 46}")
        for r in missing:
            tag = f" {DIM}(optional){RESET}" if r["optional"] else ""
            cmd = r["install"].get(current_os, "N/A")
            print(f"  {r['label']}{tag}")
            print(f"    {YELLOW}$ {cmd}{RESET}")
            print()
    else:
        print(f"\n  {GREEN}{BOLD}All languages installed!{RESET}\n")


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    results = scan()

    if "--json" in sys.argv:
        out = [{k: v for k, v in r.items() if k != "install"} for r in results]
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print_status(results)


if __name__ == "__main__":
    main()
