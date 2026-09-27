"""Write pipeline.svg (light) and pipeline-dark.svg.   python docs/figures/src/make_pipeline.py"""
# Sizes are in viewBox units; the README shows the SVG at about 920px (77%), so titles
# render near 16px, sub-labels near 14px and chips near 12px.
from pathlib import Path
OUT = Path(__file__).parent.parent
STAGES = [("Source", ["public ‘is this true?’", "requests"], "running"),
          ("Survey", ["real browser, fresh chat,", "repeated"], "built, audited"),
          ("Decompose", ["atomic checkable", "claims"], "in progress"),
          ("Check", ["web search, one LLM", "reads all evidence"], "in progress"),
          ("Score", ["per-chatbot,", "evidence attached"], "planned")]
# chip colours per status: (fill, stroke, text), muted so they read on both grounds
CHIPS = {
    "pipeline.svg": {"running": ("#e6f4ea", "#9bd3ae", "#1a6b35"), "built, audited": ("#e3eefb", "#a9c8ef", "#1c5cab"),
                     "in progress": ("#fdf1d8", "#e2c070", "#6e4b00"), "planned": ("#efefed", "#c3c2b7", "#52514e")},
    "pipeline-dark.svg": {"running": ("#12321f", "#2f6b45", "#8fe3aa"), "built, audited": ("#132a45", "#35649c", "#a9cdf5"),
                          "in progress": ("#382a0c", "#7a5a17", "#f0cb74"), "planned": ("#262a30", "#484f58", "#c0c7cf")}}
THEMES = {  # tuned for GitHub's #ffffff and #0d1117 page grounds
    "pipeline.svg":      dict(fill="#eef1f5", stroke="#57606a", title="#1f2328", sub="#424a53", num="#57606a", arrow="#57606a"),
    "pipeline-dark.svg": dict(fill="#21262d", stroke="#8b949e", title="#f0f6fc", sub="#c9d1d9", num="#9198a1", arrow="#8b949e")}
W, H, BW, BH, GAP, X0, Y0 = 1200, 180, 206, 60, 40.5, 4, 8
CW, CH = 150, 30
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"
LABEL = ("Pipeline in five stages: Source public ‘is this true?’ requests (running); Survey each chatbot in a real "
         "browser, fresh chat, repeated (built, audited); Decompose answers into atomic checkable claims (in progress); "
         "Check each claim with web search, one LLM reading all evidence (in progress); Score per chatbot with "
         "evidence attached (planned).")
for name, c in THEMES.items():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="{LABEL}">',
         f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{c["arrow"]}"/></marker></defs>']
    for i, (t, subs, status) in enumerate(STAGES):
        x = X0 + i * (BW + GAP)
        cx = x + BW / 2
        o.append(f'<rect x="{x}" y="{Y0}" width="{BW}" height="{BH}" rx="10" fill="{c["fill"]}" stroke="{c["stroke"]}" stroke-width="1.5"/>')
        o.append(f'<text x="{cx}" y="{Y0 + BH / 2 + 7}" text-anchor="middle" font-family="{FONT}" font-size="21" '
                 f'font-weight="600" fill="{c["title"]}"><tspan font-size="17" font-weight="500" fill="{c["num"]}">{i + 1}</tspan> {t}</text>')
        for j, s in enumerate(subs):
            o.append(f'<text x="{cx}" y="{Y0 + BH + 28 + j * 23}" text-anchor="middle" font-family="{FONT}" '
                     f'font-size="18" fill="{c["sub"]}">{s}</text>')
        fl, st, tx = CHIPS[name][status]
        cy = Y0 + BH + 72
        o.append(f'<rect x="{cx - CW / 2}" y="{cy}" width="{CW}" height="{CH}" rx="{CH / 2}" fill="{fl}" stroke="{st}" stroke-width="1"/>')
        o.append(f'<text x="{cx}" y="{cy + CH / 2 + 5}" text-anchor="middle" font-family="{FONT}" font-size="16" '
                 f'font-weight="500" fill="{tx}">{status}</text>')
        if i < len(STAGES) - 1:
            o.append(f'<line x1="{x + BW + 4}" y1="{Y0 + BH / 2}" x2="{x + BW + GAP - 4}" y2="{Y0 + BH / 2}" '
                     f'stroke="{c["arrow"]}" stroke-width="2" marker-end="url(#ah)"/>')
    o.append("</svg>")
    (OUT / name).write_text("\n".join(o) + "\n")
