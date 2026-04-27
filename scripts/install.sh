#!/usr/bin/env bash
set -e

echo "========================================"
echo "  Mini OJ - Install Language Runtimes"
echo "========================================"
echo ""

if [[ "$OSTYPE" == "darwin"* ]]; then
    PM="brew install"
elif command -v apt &>/dev/null; then
    PM="sudo apt install -y"
elif command -v dnf &>/dev/null; then
    PM="sudo dnf install -y"
elif command -v pacman &>/dev/null; then
    PM="sudo pacman -S --noconfirm"
else
    echo "No supported package manager found."
    exit 1
fi

install_if_missing() {
    local name="$1"
    local bin="$2"
    local pkg="$3"

    if command -v "$bin" &>/dev/null; then
        echo "[OK]  $name  ($(command -v "$bin"))"
    else
        echo "[--]  $name not found. Installing..."
        $PM $pkg
        if command -v "$bin" &>/dev/null; then
            echo "      -> installed successfully"
        else
            echo "      -> FAILED, install manually: $PM $pkg"
        fi
    fi
}

echo "--- Core languages ---"
install_if_missing "Python 3"   python3  python3
install_if_missing "g++"        g++      g++
install_if_missing "gcc"        gcc      gcc
install_if_missing "Node.js"    node     nodejs

echo ""
echo "--- Optional (uncomment to install) ---"
# install_if_missing "Java JDK"  javac    openjdk-17-jdk
# install_if_missing "Go"        go       golang-go
# install_if_missing "Rust"      rustc    rustc
# install_if_missing "Ruby"      ruby     ruby
# install_if_missing "PHP"       php      php-cli
# install_if_missing "Perl"      perl     perl
# install_if_missing "Lua"       lua      lua5.4

echo ""
echo "Done. Restart Django to pick up changes."
