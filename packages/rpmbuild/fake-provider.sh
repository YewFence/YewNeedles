#!/usr/bin/env bash
set -euo pipefail

topdir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
specdir="$topdir/SPECS"
rpmdir="$topdir/RPMS/noarch"
tmpdir="$topdir/TMP"
default_spec="$specdir/mise-nodejs-npm-provider.spec"

die() {
  gum style --foreground 196 "error: $*" >&2
  exit 1
}

need() {
  command -v "$1" >/dev/null 2>&1 || die "missing command: $1"
}

field_from_spec() {
  local field="$1" fallback="$2"
  local value=""
  if [[ -f "$default_spec" ]]; then
    value="$(
      awk -v field="$field" '
      $1 == field ":" {
        $1 = ""
        sub(/^[[:space:]]+/, "")
        print
        exit
      }
    ' "$default_spec"
    )"
  fi

  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$fallback"
  fi
}

lines_from_spec() {
  local tag="$1" fallback="$2"
  local value=""
  if [[ -f "$default_spec" ]]; then
    value="$(
      awk -v tag="$tag" '
        $1 == tag ":" {
          $1 = ""
          sub(/^[[:space:]]+/, "")
          print
        }
      ' "$default_spec"
    )"
  fi

  if [[ -n "$value" ]]; then
    printf '%s\n' "$value"
  else
    printf '%s\n' "$fallback"
  fi
}

input() {
  local header="$1" value="$2" placeholder="$3"
  gum input \
    --header "$header" \
    --value "$value" \
    --placeholder "$placeholder" \
    --char-limit 0
}

write_lines() {
  local header="$1" value="$2" placeholder="$3"
  gum write \
    --header "$header" \
    --value "$value" \
    --placeholder "$placeholder" \
    --height 8 \
    --char-limit 0 \
    --max-lines 0
}

trim_lines() {
  sed -e 's/[[:space:]]*$//' -e '/^[[:space:]]*$/d'
}

validate_name() {
  local name="$1"
  [[ "$name" =~ ^[A-Za-z0-9._+-]+$ ]] || die "package name contains unsupported characters"
}

validate_version() {
  local value="$1" label="$2"
  [[ "$value" =~ ^[A-Za-z0-9._+~%-]+$ ]] || die "$label contains unsupported characters"
}

validate_capabilities() {
  local label="$1"
  local capability_re='^[[:alnum:]._+:/%{}~(),[:space:]=<>-]+$'
  local line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" != *$'\t'* ]] || die "$label contains a tab: $line"
    [[ "$line" =~ $capability_re ]] || die "$label contains unsupported characters: $line"
  done
}

emit_capability_block() {
  local tag="$1" value="$2"
  local line
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    printf '%-15s %s\n' "$tag:" "$line"
  done <<<"$value"
}

write_spec() {
  local spec_file="$1"
  local name="$2"
  local version="$3"
  local release="$4"
  local summary="$5"
  local license="$6"
  local provides="$7"
  local requires="$8"
  local conflicts="$9"
  local obsoletes="${10}"
  local description="${11}"

  {
    printf 'Name:           %s\n' "$name"
    printf 'Version:        %s\n' "$version"
    printf 'Release:        %s%%{?dist}\n' "$release"
    printf 'Summary:        %s\n' "$summary"
    printf 'License:        %s\n' "$license"
    printf 'BuildArch:      noarch\n\n'
    emit_capability_block Provides "$provides"
    emit_capability_block Requires "$requires"
    emit_capability_block Conflicts "$conflicts"
    emit_capability_block Obsoletes "$obsoletes"
    printf '\n%%description\n'
    printf '%s\n\n' "$description"
    printf 'This package intentionally ships no files. It exists only to satisfy RPM dependency capabilities.\n\n'
    printf '%%prep\n\n'
    printf '%%build\n\n'
    printf '%%install\n\n'
    printf '%%files\n\n'
    printf '%%changelog\n'
    printf '* Tue Jul 07 2026 YewFence <yewfence@localhost> - %s-%s\n' "$version" "$release"
    printf -- '- Generated fake provider package\n'
  } >"$spec_file"
}

run_as_root() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  elif command -v pkexec >/dev/null 2>&1; then
    pkexec "$@"
  else
    die "need root privileges, but neither sudo nor pkexec was found"
  fi
}

install_rpm() {
  local rpm_path="$1"
  if command -v dnf >/dev/null 2>&1; then
    run_as_root dnf install -y "$rpm_path"
  elif command -v dnf5 >/dev/null 2>&1; then
    run_as_root dnf5 install -y "$rpm_path"
  else
    run_as_root rpm -Uvh --replacepkgs "$rpm_path"
  fi
}

need gum
need rpmbuild
need rpm

mkdir -p "$specdir" "$rpmdir" "$tmpdir"

gum style \
  --foreground 212 \
  --border normal \
  --padding "1 2" \
  "Fake RPM provider builder"

name="$(input "Package name" "$(field_from_spec Name mise-nodejs-npm-provider)" "mise-nodejs-npm-provider")"
version="$(input "Version" "$(field_from_spec Version 1.0)" "1.0")"
release_default="$(field_from_spec Release 1)"
release_default="${release_default%%%{?dist}}"
release="$(input "Release without distro suffix" "$release_default" "1")"
summary="$(input "Summary" "$(field_from_spec Summary "Virtual RPM provider backed by mise")" "Virtual RPM provider backed by mise")"
license="$(input "License" "$(field_from_spec License MIT)" "MIT")"

provides="$(write_lines "Provides, one per line" "$(lines_from_spec Provides nodejs-npm)" "nodejs-npm"$'\n'"npm")"
requires="$(write_lines "Requires, one per line, leave empty if none" "" "mise")"
conflicts="$(write_lines "Conflicts, one per line, leave empty if none" "" "nodejs-npm < 10")"
obsoletes="$(write_lines "Obsoletes, one per line, leave empty if none" "" "old-provider")"
description="$(write_lines "Description" "Virtual RPM package that satisfies dependency capabilities. The real commands are expected to be provided by mise shims." "Describe why this fake package exists")"

provides="$(printf '%s\n' "$provides" | trim_lines)"
requires="$(printf '%s\n' "$requires" | trim_lines)"
conflicts="$(printf '%s\n' "$conflicts" | trim_lines)"
obsoletes="$(printf '%s\n' "$obsoletes" | trim_lines)"
description="$(printf '%s\n' "$description" | sed -e 's/[[:space:]]*$//')"

[[ -n "$name" ]] || die "package name is required"
[[ -n "$version" ]] || die "version is required"
[[ -n "$release" ]] || die "release is required"
[[ -n "$summary" ]] || die "summary is required"
[[ -n "$license" ]] || die "license is required"
[[ -n "$provides" ]] || die "at least one Provides entry is required"
[[ -n "$description" ]] || die "description is required"

validate_name "$name"
validate_version "$version" version
validate_version "$release" release
validate_capabilities Provides <<<"$provides"
validate_capabilities Requires <<<"$requires"
validate_capabilities Conflicts <<<"$conflicts"
validate_capabilities Obsoletes <<<"$obsoletes"

spec_file="$specdir/$name.spec"
write_spec "$spec_file" "$name" "$version" "$release" "$summary" "$license" "$provides" "$requires" "$conflicts" "$obsoletes" "$description"

gum style --foreground 250 "Spec written to $spec_file"

gum spin \
  --title "Building RPM" \
  --show-error \
  -- rpmbuild \
    --define "_topdir $topdir" \
    --define "_tmppath $tmpdir" \
    -bb "$spec_file"

rpm_path="$rpmdir/$name-$version-$release.$(rpm --eval '%{dist}' | sed 's/^\.//').noarch.rpm"
if [[ ! -f "$rpm_path" ]]; then
  shopt -s nullglob
  rpm_matches=("$rpmdir"/"$name"-"$version"-"$release".*.noarch.rpm)
  shopt -u nullglob

  [[ "${#rpm_matches[@]}" -gt 0 ]] || die "built RPM was not found"
  rpm_path="${rpm_matches[0]}"
  for rpm_match in "${rpm_matches[@]}"; do
    [[ "$rpm_match" -nt "$rpm_path" ]] && rpm_path="$rpm_match"
  done
fi

gum style --foreground 82 "Built $rpm_path"
rpm -qpi "$rpm_path"
rpm -qp --provides "$rpm_path"

if gum confirm "Install this fake provider RPM?" --negative "Skip" --affirmative "Install"; then
  gum style --foreground 250 "Installing $rpm_path"
  install_rpm "$rpm_path"
  gum style --foreground 82 "Installed $name"
else
  gum style --foreground 250 "Skipped install"
fi
