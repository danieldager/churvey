#!/bin/zsh
# Visual-iteration loop without Node: headless Firefox screenshots of the popup
# with a mocked extension API (dev/mock.js). Usage: ./shoot.sh
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
POPUP="$HERE/../src/popup"
FF="/Applications/Firefox.app/Contents/MacOS/firefox"
mkdir -p "$HERE/shots"

# preview page = popup.html with the mock injected before the real scripts
python3 - "$POPUP" "$HERE" << 'EOF'
import sys, re
popup, here = sys.argv[1], sys.argv[2]
html = open(popup + "/popup.html").read()
html = html.replace('<script src="../shared/ext.js"></script>',
                    '<script src="../../dev/mock.js"></script>\n    <script src="../shared/ext.js"></script>')
open(popup + "/_preview.html", "w").write(html)
print("preview page written")
EOF

for scheme in light dark; do
  PROF="$(mktemp -d)/ffprof"
  mkdir -p "$PROF"
  # 1 = light, 0 = dark (content-level prefers-color-scheme override)
  [ "$scheme" = light ] && { v=1; Q=""; } || { v=0; Q="?theme=dark"; }
  cat > "$PROF/user.js" << EOP
user_pref("layout.css.prefers-color-scheme.content-override", $v);
user_pref("datareporting.policy.firstRunURL", "");
user_pref("browser.shell.checkDefaultBrowser", false);
EOP
  "$FF" --headless --no-remote --profile "$PROF" \
    --window-size=480,1050 \
    --screenshot "$HERE/shots/popup-$scheme.png" \
    "file://$POPUP/_preview.html$Q" 2>/dev/null
  echo "shot: $HERE/shots/popup-$scheme.png"
done
