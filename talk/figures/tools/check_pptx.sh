#!/usr/bin/env bash
# Render kcf_talk_figures.pptx with headless LibreOffice and write one PNG per slide to $1 (default /tmp/pptx-check).
set -euo pipefail
OUT="${1:-/tmp/pptx-check}"; mkdir -p "$OUT/fc-cache"
HERE="$(cd "$(dirname "$0")" && pwd)"
sed "s|/private/tmp/claude-501/fc/cache|$OUT/fc-cache|; s|/Users/jp|$HOME|" "$HERE/fonts.conf.template" > "$OUT/fonts.conf"
FONTCONFIG_FILE="$OUT/fonts.conf" /Applications/LibreOffice.app/Contents/MacOS/soffice --headless \
  --convert-to pdf --outdir "$OUT" "$HERE/../kcf_talk_figures.pptx"
pdftoppm -r 80 -png "$OUT/kcf_talk_figures.pdf" "$OUT/slide"
pdffonts "$OUT/kcf_talk_figures.pdf"
