#!/usr/bin/env bash
set -euo pipefail
version=$1
dest=$2
base=https://github.com/aquasecurity/trivy/releases
curl_opts=(--fail --silent --show-error --location --retry 3 --connect-timeout 10 --max-time 120)
if [[ $version == latest ]]; then
  url=$(curl "${curl_opts[@]}" -o /dev/null -w '%{url_effective}' "$base/latest")
  version=${url##*/}
fi
version=${version#v}
case $(uname -s) in
  Linux) os=Linux;; Darwin) os=macOS;; FreeBSD) os=FreeBSD;; MINGW*|MSYS*|CYGWIN*) os=windows;; *) echo 'Unsupported operating system' >&2; exit 1;;
esac
case $(uname -m) in
  x86_64|amd64) arch=64bit;; i386|i686) arch=32bit;; aarch64|arm64) arch=ARM64;; armv7l) arch=ARM;; s390x) arch=s390x;; ppc64le) arch=PPC64LE;; *) echo 'Unsupported architecture' >&2; exit 1;;
esac
ext=tar.gz; binary=trivy
if [[ $os == windows ]]; then ext=zip; binary=trivy.exe; fi
archive="trivy_${version}_${os}-${arch}.${ext}"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
curl "${curl_opts[@]}" -o "$work/$archive" "$base/download/v${version}/${archive}"
curl "${curl_opts[@]}" -o "$work/checksums.txt" "$base/download/v${version}/trivy_${version}_checksums.txt"
checksum=$(awk -v file="$archive" '$2 == file {print $1}' "$work/checksums.txt")
[[ $checksum =~ ^[[:xdigit:]]{64}$ ]] || { echo 'Missing or invalid checksum' >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
  actual=$(sha256sum "$work/$archive")
else
  actual=$(shasum -a 256 "$work/$archive")
fi
[[ ${actual%% *} == "$checksum" ]] || { echo 'Checksum mismatch' >&2; exit 1; }
mkdir -p "$dest"
if [[ $ext == zip ]]; then unzip -p "$work/$archive" "$binary" > "$dest/$binary"; else tar -xOzf "$work/$archive" "$binary" > "$dest/$binary"; fi
chmod +x "$dest/$binary"
printf '%s\n' "$dest" >> "$GITHUB_PATH"
