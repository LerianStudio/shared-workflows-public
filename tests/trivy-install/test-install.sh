#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/stub" "$tmp/assets" "$tmp/payload"
printf '#!/bin/sh\necho fixture\n' > "$tmp/payload/trivy"
printf '#!/bin/sh\necho fixture\n' > "$tmp/payload/trivy.exe"
cat > "$tmp/stub/uname" <<'STUB'
#!/usr/bin/env bash
case "$1" in -s) echo "$TEST_OS";; -m) echo "$TEST_ARCH";; esac
STUB
cat > "$tmp/stub/curl" <<'STUB'
#!/usr/bin/env bash
set -euo pipefail
out= url=
while (($#)); do
  case "$1" in -o|--output) out=$2; shift 2;; https://*) url=$1; shift;; *) shift;; esac
done
printf '%s\n' "$url" >> "$TEST_LOG"
case "$url" in
  */releases/latest) printf '%s' 'https://github.com/aquasecurity/trivy/releases/tag/v0.69.3';;
  *checksums.txt) [[ ${FAIL_DOWNLOAD:-} != checksums ]] && cp "$TEST_ASSETS/checksums.txt" "$out";;
  *) [[ ${FAIL_DOWNLOAD:-} != archive ]] && cp "$TEST_ASSETS/archive" "$out";;
esac
STUB
chmod +x "$tmp/stub/"*
export PATH="$tmp/stub:$PATH" TEST_ASSETS="$tmp/assets" TEST_LOG="$tmp/log"
run_case() {
  local os=$1 arch=$2 release_os=$3 release_arch=$4 version=$5 ext=$6 binary=$7
  export TEST_OS=$os TEST_ARCH=$arch
  local name="trivy_0.69.3_${release_os}-${release_arch}.${ext}"
  if [[ $ext == zip ]]; then (cd "$tmp/payload" && zip -q - "$binary" > "$tmp/assets/archive"); else tar -czf "$tmp/assets/archive" -C "$tmp/payload" "$binary"; fi
  printf '%s  %s\n' "$(sha256sum "$tmp/assets/archive" | cut -d' ' -f1)" "$name" > "$tmp/assets/checksums.txt"
  : > "$tmp/path"; : > "$tmp/log"
  GITHUB_PATH="$tmp/path" bash "$root/src/security/install-trivy.sh" "$version" "$tmp/install"
  test -f "$tmp/install/$binary"
  grep -Fx "$tmp/install" "$tmp/path" >/dev/null
  grep -F "/$name" "$tmp/log" >/dev/null
  rm -rf "$tmp/install" "$tmp/assets/archive"
}
run_case Linux x86_64 Linux 64bit v0.69.3 tar.gz trivy
run_case Linux aarch64 Linux ARM64 0.69.3 tar.gz trivy
run_case Linux ppc64le Linux PPC64LE v0.69.3 tar.gz trivy
run_case Darwin arm64 macOS ARM64 latest tar.gz trivy
run_case Darwin x86_64 macOS 64bit v0.69.3 tar.gz trivy
run_case FreeBSD x86_64 FreeBSD 64bit v0.69.3 tar.gz trivy
run_case MINGW64_NT-10.0 x86_64 windows 64bit v0.69.3 zip trivy.exe
export TEST_OS=Linux TEST_ARCH=x86_64
tar -czf "$tmp/assets/archive" -C "$tmp/payload" trivy
name=trivy_0.69.3_Linux-64bit.tar.gz
for failure in archive checksums mismatch missing invalid no-binary; do
  printf '%s  %s\n' "$(sha256sum "$tmp/assets/archive" | cut -d' ' -f1)" "$name" > "$tmp/assets/checksums.txt"
  case $failure in
    mismatch) printf '%064d  %s\n' 0 "$name" > "$tmp/assets/checksums.txt";;
    missing) echo 'no matching checksum' > "$tmp/assets/checksums.txt";;
    invalid) echo invalid > "$tmp/assets/archive"; printf '%s  %s\n' "$(sha256sum "$tmp/assets/archive" | cut -d' ' -f1)" "$name" > "$tmp/assets/checksums.txt";;
    no-binary) tar -czf "$tmp/assets/archive" -C "$tmp/payload" trivy.exe; printf '%s  %s\n' "$(sha256sum "$tmp/assets/archive" | cut -d' ' -f1)" "$name" > "$tmp/assets/checksums.txt";;
  esac
  : > "$tmp/path"
  if FAIL_DOWNLOAD=$failure GITHUB_PATH="$tmp/path" bash "$root/src/security/install-trivy.sh" v0.69.3 "$tmp/install"; then echo "unexpected success: $failure" >&2; exit 1; fi
  test ! -s "$tmp/path"
  rm -rf "$tmp/install"
done
echo 'installer behavioral tests passed'
