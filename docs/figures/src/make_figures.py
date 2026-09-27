"""Draw the README figures from docs/figures/figdata.json (derived from
data/michigan_2026/grades.csv) plus the reach constants below. No network.
    uv run --with matplotlib python docs/figures/src/make_figures.py"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

OUT = Path(__file__).parent.parent
D = json.loads((OUT / "figdata.json").read_text())
MODELS = D["model_order"]
M = {m["model"]: m for m in D["models"]}

# Reach, as published; sources and dates in docs/reach.md.
APPS = [("ChatGPT", 900e6, "900M weekly users"), ("Gemini app", 950e6, "950M monthly users"),
        ("DeepSeek (China)", 130e6, "130M monthly users"), ("Grok (incl. inside X)", 117e6, "117M monthly users")]
APIS = [("Google model APIs", 9e6, "9M developers a month"), ("OpenAI API", 4e6, "4M developers")]
WORLD_AI_USERS = 2e9  # Menlo Ventures, State of Consumer AI 2026

# Question-sourcing funnel, run of 24-25 Sep 2026 (14.5 feed-hours, filter v1.2), whole window
# including the pilot hour; counts from the run's summary file (harvest_2026-09-25_passes.md.json, "fa").
FUNNEL = [("Replies harvested", 2038), ("Traced back to the post and the request", 2035),
          ("Passed the rule filters", 1856), ("Passed the LLM filter, two runs agreeing", 492),
          ("Rated quality 4 or 5", 459), ("Kept after per-asker cap and deduplication", 275)]

# Short question labels (full text in data/michigan_2026/questions.md).
SHORT = {"P1": "Election date, poll hours, line rule", "P2": "Where to register in Ann Arbor",
         "P3": "Can I register on Election Day", "P4": "Early-voting dates and Ann Arbor sites",
         "P5": "How votes are counted and certified", "P6": "Who runs elections in Michigan",
         "P7": "Which races are on the ballot", "C1": "Democratic Senate candidates: policy differences",
         "C2": "El-Sayed vs Stevens on healthcare", "C3": "El-Sayed vs Stevens on Israel, Gaza",
         "C4": "El-Sayed vs Stevens on immigration", "C5": "Republican governor candidates: platform differences",
         "C6": "What Benson's governor platform focuses on", "C7": "Benson vs Swanson platform differences"}

# dataviz reference palette (light surface)
BLUE, ORANGE, AQUA, YELLOW, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
NEUTRAL = "#b8b7b0"
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
       "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
W, DPI = 8.0, 200  # 1600 px wide
plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"], "font.size": 11,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlecolor": INK, "axes.titlelocation": "left",
    "axes.titlepad": 12, "axes.labelsize": 11, "axes.labelcolor": INK2, "xtick.labelsize": 10.5,
    "ytick.labelsize": 10.5, "xtick.color": INK2, "ytick.color": INK2, "legend.fontsize": 10.5,
    "legend.frameon": False, "text.color": INK2, "axes.edgecolor": AXIS, "axes.linewidth": 0.8,
    "figure.facecolor": "white", "savefig.facecolor": "white"})


def frame(ax, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    if grid:
        ax.grid(axis=grid, color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def save(fig, name):
    fig.get_layout_engine().set(w_pad=0.2, h_pad=0.2)
    fig.savefig(OUT / name, dpi=DPI * W / fig.get_figwidth())  # always 1600 px wide
    plt.close(fig)


def fig_reach():
    rows = [("People using the app", APPS, BLUE), ("Developers on the API", APIS, ORANGE)]
    fig, ax = plt.subplots(figsize=(W, 4.3), layout="constrained")
    y, ticks, labels = 0, [], []
    for group, items, c in rows:
        ax.text(1.2e6, y - 0.1, group, fontsize=11, fontweight="bold", color=INK, va="bottom")
        y -= 0.75
        for name, v, lab in items:
            ax.plot([1e6, v], [y, y], color=c, linewidth=2, alpha=0.35, solid_capstyle="butt")
            ax.scatter([v], [y], s=90, color=c, edgecolor="white", linewidth=2, zorder=3)
            ax.text(v * 1.35, y, lab, va="center", fontsize=10.5, color=INK)
            ticks.append(y); labels.append(name)
            y -= 0.75
        y -= 0.35
    ax.axvline(WORLD_AI_USERS, color=AXIS, linewidth=1, linestyle=(0, (3, 3)))
    ax.text(WORLD_AI_USERS * 1.12, y + 0.45, "~2B AI users\nworldwide (survey)", ha="left", va="bottom", fontsize=9.5, color=MUTED)
    ax.set_xscale("log")
    ax.set_xlim(1e6, 3e10)
    ax.set_xticks([1e6, 1e7, 1e8, 1e9, 1e10])
    ax.set_xticklabels(["1M", "10M", "100M", "1B", ""])
    ax.set_yticks(ticks, labels)
    ax.set_ylim(y + 0.2, 0.3)
    ax.set_title("Who reaches the models")
    ax.set_xlabel("log scale")
    fig.text(0.01, 0.005, "Denominators differ: apps count weekly or monthly users, APIs count developers. "
             "Anthropic publishes no user figure for Claude.", fontsize=9.5, color=MUTED, ha="left", va="bottom")
    frame(ax, "x")
    ax.spines["left"].set_visible(False)
    fig.get_layout_engine().set(rect=(0, 0.05, 1, 0.95))
    save(fig, "reach.png")


def fig_accuracy_vs_false():
    fig, ax = plt.subplots(figsize=(W, 5.0), layout="constrained")
    ax.add_patch(plt.Rectangle((85, -0.5), 15, 2.3, color="#f0efec", linewidth=0, zorder=0))
    ax.text(99.4, -0.25, "complete and rarely wrong:\nno chatbot is here", ha="right", va="bottom", fontsize=9.5, color=MUTED)
    off = {"Grok": (0, 14, "center"), "Gemini": (0, -16, "center"), "ChatGPT": (-12, 0, "right"),
           "Claude": (10, 4, "left"), "DeepSeek": (10, 4, "left")}
    for m in MODELS:
        x, yv = M[m]["accuracy"], M[m]["answers_with_false_claim"]
        if m == "Gemini":
            ax.scatter([x], [yv], s=130, facecolor="white", edgecolor=BLUE, linewidth=2, linestyle="--", zorder=3)
            lab = f"Gemini*  {x:.0f}%, {yv} false"
        else:
            ax.scatter([x], [yv], s=130, color=BLUE, edgecolor="white", linewidth=2, zorder=3)
            lab = f"{m}  {x:.0f}%, {yv} false"
        dx, dy, ha = off[m]
        ax.annotate(lab, (x, yv), xytext=(dx, dy), textcoords="offset points", ha=ha, va="center",
                    fontsize=10.5, color=INK)
    ax.set_xlim(45, 100); ax.set_ylim(-0.5, 10)
    ax.set_xlabel("share of checklist facts covered (%)")
    ax.set_ylabel("answers with at least one false claim (of 70)")
    ax.set_title("Completeness is not truthfulness", pad=26)
    ax.text(0.0, 1.025, "Grok covers the most; ChatGPT says the fewest false things; Claude says the most.",
            transform=ax.transAxes, fontsize=10, color=INK2, va="bottom")
    fig.text(0.01, 0.005, "* Gemini (hollow): a capture bug kept it in one running conversation, so its answers "
             "were not independent.", fontsize=9.5, color=MUTED, ha="left", va="bottom")
    frame(ax, "both")
    fig.get_layout_engine().set(rect=(0, 0.04, 1, 0.96))
    save(fig, "accuracy_vs_false.png")


def fig_heatmap():
    qs = [q["id"] for q in D["questions"]]
    fig, ax = plt.subplots(figsize=(W, 6.6), layout="constrained")
    cols = [f"{m}*" if m == "Gemini" else m for m in MODELS]
    for i, q in enumerate(qs):
        r = i + (0.8 if q.startswith("C") else 0)
        for j, m in enumerate(MODELS):
            v = D["accuracy_matrix"][q][m]
            k = min(len(SEQ) - 1, int(v / 100 * (len(SEQ) - 1) + 0.5))
            ax.add_patch(plt.Rectangle((j + 0.03, r + 0.04), 0.94, 0.92, color=SEQ[k], linewidth=0))
            ax.text(j + 0.5, r + 0.5, f"{v:.0f}", ha="center", va="center", fontsize=10.5,
                    color="white" if k >= 7 else INK)
    ax.set_xlim(0, 5); ax.set_ylim(14.8, -0.9)
    ax.set_xticks([j + 0.5 for j in range(5)], cols)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 + (0.8 if q.startswith("C") else 0) for i, q in enumerate(qs)],
                  [f"{q}  {SHORT[q]}" for q in qs])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.text(-0.02, -0.12, "Logistics", transform=ax.get_yaxis_transform(), ha="right", fontsize=11,
            fontweight="bold", color=INK)
    ax.text(-0.02, 7.62, "Candidates", transform=ax.get_yaxis_transform(), ha="right", fontsize=11,
            fontweight="bold", color=INK)
    ax.set_title("Mean accuracy by question and chatbot (%)", pad=26)
    fig.text(0.01, 0.005, "Each cell: mean over 5 answers of the share of checklist facts covered. "
             "* Gemini answers were not independent (capture bug).", fontsize=9.5, color=MUTED, ha="left", va="bottom")
    fig.get_layout_engine().set(rect=(0, 0.03, 1, 0.97))
    save(fig, "heatmap.png")


def fig_five_states():
    cats = [("Michigan (correct)", BLUE), ("asked which state", NEUTRAL), ("several states", MAGENTA),
            ("Florida", ORANGE), ("Kansas", AQUA), ("Virginia / Missouri", YELLOW)]

    def cat(a):
        a = a.lower()
        if a.startswith("asked"): return "asked which state"
        if a.startswith("several"): return "several states"
        if a.startswith("michigan"): return "Michigan (correct)"
        if a.startswith("florida"): return "Florida"
        if a.startswith("kansas"): return "Kansas"
        if a.startswith("virginia") or a.startswith("missouri"): return "Virginia / Missouri"
        raise ValueError(a)

    ans = D["voter_id_question"]["answers"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8), layout="constrained")
    for i, m in enumerate(MODELS):
        counts = {c: 0 for c, _ in cats}
        for a in ans[m]:
            counts[cat(a)] += 1
        left = 0
        for c, col in cats:
            n = counts[c]
            if not n: continue
            ax.barh(i, n - 0.06, left=left + 0.03, height=0.62, color=col,
                    alpha=0.45 if m == "Gemini" else 1.0, linewidth=0)
            ax.text(left + n / 2, i, str(n), ha="center", va="center", fontsize=10.5,
                    color="white" if col in (BLUE,) and m != "Gemini" else INK)
            left += n
        ax.text(left + 0.1, i, f"{len(ans[m])} answers" + (", contaminated" if m == "Gemini" else ""), va="center", fontsize=9.5, color=MUTED)
    ax.set_yticks(range(len(MODELS)), [f"{m}*" if m == "Gemini" else m for m in MODELS])
    ax.set_ylim(len(MODELS) - 0.4, -0.6)
    ax.set_xlim(0, 6.2); ax.set_xticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.legend(handles=[Patch(color=c, label=l) for l, c in cats], ncol=3, loc="lower left",
              bbox_to_anchor=(0, 1.0), fontsize=9.5, handlelength=1, columnspacing=1.1, borderaxespad=0.3)
    ax.set_title("Which state each chatbot answered for", pad=48)
    fig.text(0.01, 0.005, "Voter-ID question, no state named.\n* Gemini (faded) had seen earlier Michigan "
             "questions in the same conversation.", fontsize=9.5, color=MUTED, ha="left", va="bottom")
    fig.get_layout_engine().set(rect=(0, 0.09, 1, 0.91))
    save(fig, "five_states.png")


def fig_funnel():
    fig, ax = plt.subplots(figsize=(W, 3.6), layout="constrained")
    for i, (lab, n) in enumerate(FUNNEL):
        last = i == len(FUNNEL) - 1
        ax.barh(i, n, height=0.62, color=BLUE if last else SEQ[3], linewidth=0)
        ax.text(n + 25, i, f"{n:,}", va="center", fontsize=10.5, color=INK, fontweight="bold" if last else "normal")
    ax.set_yticks(range(len(FUNNEL)), [l for l, _ in FUNNEL])
    ax.set_ylim(len(FUNNEL) - 0.4, -0.6)
    ax.set_xlim(0, 2300); ax.set_xticks([0, 500, 1000, 1500, 2000], ["0", "500", "1,000", "1,500", "2,000"])
    ax.set_title("From requests to checkable questions")
    fig.text(0.01, 0.005, "One run, 24 to 25 Sep 2026: 14.5 hours of feed, filter v1.2.", fontsize=9.5,
             color=MUTED, ha="left", va="bottom")
    frame(ax, "x")
    ax.spines["left"].set_visible(False)
    fig.get_layout_engine().set(rect=(0, 0.06, 1, 0.94))
    save(fig, "funnel.png")


fig_reach(); fig_accuracy_vs_false(); fig_heatmap(); fig_five_states(); fig_funnel()
