#!/usr/bin/env bash
# WildfireGuardian vehicle unit: run the Pi's own Wi-Fi hotspot with NetworkManager (Raspberry Pi OS bookworm).
#
#   sudo WFGVU_PSK='<8-63 char passphrase>' system/hotspot.sh [up|down|status]
#
# WPA2-PSK (RSN/CCMP only), static address 10.42.0.1/24 on wlan0, DHCP for the laptop via NetworkManager's
# "shared" mode. The passphrase comes from the root-only file /etc/wfgvu/hotspot.psk (recommended) or $WFGVU_PSK;
# there is no default passphrase. It must be 8..63 printable ASCII characters, without a backslash and without
# leading or trailing spaces (checked before anything changes).
#
# `up` never leaves the unit without a hotspot because of a bad passphrase or a failed profile: the new profile is
# written as a NetworkManager keyfile (mode 600, so the passphrase never appears on a command line, in ps or in
# /proc/<pid>/cmdline) under a temporary name, loaded and brought up; only then are the old "$CON" profiles deleted
# and the new one renamed. If loading or activation fails, the new profile is removed and the old one re-activated.
# Untested on the target Pi; check `nmcli con show wfgvu-hotspot` after the first run.
set -euo pipefail
export LC_ALL=C

CON="${WFGVU_CON:-wfgvu-hotspot}"
IFACE="${WFGVU_IFACE:-wlan0}"
SSID="${WFGVU_SSID:-WFGVU-01}"
ADDR="${WFGVU_ADDR:-10.42.0.1/24}"
BAND="${WFGVU_BAND:-bg}"          # 2.4 GHz: better range around a vehicle than 5 GHz
CHANNEL="${WFGVU_CHANNEL:-6}"
PSK_FILE="${WFGVU_PSK_FILE:-/etc/wfgvu/hotspot.psk}"
NM_DIR="${WFGVU_NM_DIR:-/etc/NetworkManager/system-connections}"

cmd="${1:-up}"

need_nmcli() {
  command -v nmcli >/dev/null 2>&1 || { echo "nmcli not found: NetworkManager is required" >&2; exit 1; }
}

read_psk() {
  local psk="${WFGVU_PSK:-}"
  if [[ -z "$psk" && -r "$PSK_FILE" ]]; then
    psk="$(head -n1 "$PSK_FILE" | tr -d '\r\n')"
  fi
  if [[ -z "$psk" ]]; then
    echo "no passphrase: set WFGVU_PSK or write it to $PSK_FILE (chmod 600)" >&2; exit 2
  fi
  if ! [[ $psk =~ ^[[:print:]]{8,63}$ ]]; then
    echo "WPA2 passphrase must be 8..63 printable ASCII characters" >&2; exit 2
  fi
  if [[ $psk == *\\* || $psk == " "* || $psk == *" " ]]; then
    echo "passphrase: no backslash and no leading/trailing space (keyfile escaping)" >&2; exit 2
  fi
  printf '%s' "$psk"
}

new_uuid() {
  if [[ -r /proc/sys/kernel/random/uuid ]]; then cat /proc/sys/kernel/random/uuid; else uuidgen; fi
}

# Write the keyfile for connection id $1 / uuid $2 to $3 (mode 600, via a hidden temporary file + rename).
write_keyfile() {
  local id="$1" uuid="$2" path="$3" tmp
  tmp="$(dirname "$path")/.$(basename "$path").tmp"
  ( umask 077
    {
      printf '[connection]\nid=%s\nuuid=%s\ntype=wifi\ninterface-name=%s\nautoconnect=true\n' "$id" "$uuid" "$IFACE"
      printf 'autoconnect-priority=100\n\n'
      printf '[wifi]\nmode=ap\nssid=%s\nband=%s\nchannel=%s\n\n' "$SSID" "$BAND" "$CHANNEL"
      printf '[wifi-security]\nkey-mgmt=wpa-psk\nproto=rsn;\npairwise=ccmp;\ngroup=ccmp;\npsk=%s\n\n' "$PSK"
      printf '[ipv4]\nmethod=shared\naddress1=%s\n\n[ipv6]\nmethod=disabled\n' "$ADDR"
    } > "$tmp" )
  chmod 600 "$tmp"
  mv -f "$tmp" "$path"
}

case "$cmd" in
  up)
    need_nmcli
    PSK="$(read_psk)"                         # validated before anything changes
    install -d -m 700 "$NM_DIR"
    OLD_UUIDS="$(nmcli -t -f NAME,UUID con show | awk -F: -v n="$CON" '$1 == n {print $2}')"
    UUID="$(new_uuid)"
    TMP_ID="$CON-new-${UUID:0:8}"
    FILE="$NM_DIR/$CON-${UUID:0:8}.nmconnection"
    write_keyfile "$TMP_ID" "$UUID" "$FILE"
    unset PSK
    if ! nmcli con load "$FILE" || ! nmcli con up uuid "$UUID"; then
      echo "new hotspot profile failed; keeping the old one" >&2
      nmcli con delete uuid "$UUID" >/dev/null 2>&1 || true
      rm -f "$FILE"
      for u in $OLD_UUIDS; do nmcli con up uuid "$u" >/dev/null 2>&1 || true; done
      exit 1
    fi
    for u in $OLD_UUIDS; do nmcli con delete uuid "$u" >/dev/null || true; done
    nmcli con modify uuid "$UUID" connection.id "$CON"
    echo "hotspot $SSID up on $IFACE at ${ADDR%/*}; stream at ws://${ADDR%/*}:8770/stream"
    ;;
  down)
    need_nmcli
    nmcli con down "$CON" || true
    ;;
  status)
    need_nmcli
    nmcli -f GENERAL.STATE,IP4.ADDRESS con show "$CON" || echo "no connection $CON"
    ;;
  *)
    echo "usage: $0 [up|down|status]" >&2; exit 64
    ;;
esac
