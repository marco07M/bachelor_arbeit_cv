"""Extend the existing overview with exported scientific figures and transparent denominators."""

import numpy as np

START = "<!-- scientific-analysis:start -->"
END = "<!-- scientific-analysis:end -->"


def render_figures(folder, payload):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    primary = [r for r in payload["overview"] if r.get("mode") == "original_roles"]
    methods = [r["candidate"] for r in primary]
    course_info = payload["course_metadata"]
    courses = list(course_info)[:200]

    def save(fig, name):
        fig.savefig(folder / (name + ".svg"), bbox_inches="tight")
        fig.savefig(folder / (name + ".png"), dpi=150, bbox_inches="tight")
        plt.close(fig)

    if methods and courses:
        from .detail_report import read_csv

        rows = [r for r in read_csv(folder / "courses.csv") if r["mode"] == "original_roles"]
        lookup = {
            (r["candidate"], r["class_id"]): float(r["exact_recall"]) if r["exact_recall"] else np.nan
            for r in rows
        }
        values = np.array([[lookup.get((m, c), np.nan) * 100 for c in courses] for m in methods])
        fig, ax = plt.subplots(figsize=(max(7, min(25, len(courses) * 0.7)), max(3, len(methods) * 0.55)))
        display = ax.imshow(np.ma.masked_invalid(values), vmin=0, vmax=100, cmap="Blues", aspect="auto")
        ax.set_xticks(
            range(len(courses)),
            [f"{c}\n{course_info[c]['stratum']}" for c in courses],
            rotation=45,
            ha="right",
        )
        ax.set_yticks(range(len(methods)), methods)
        ax.set_title("Exakter Feld-Recall je Schulung – originale Namensrollen")
        ax.set_xlabel("Schulung / manuell dokumentierter Schrifttyp (unbekannt bleibt unknown)")
        if len(courses) <= 30:
            for i in range(len(methods)):
                for j in range(len(courses)):
                    ax.text(
                        j,
                        i,
                        "—" if np.isnan(values[i, j]) else f"{values[i, j]:.1f}",
                        ha="center",
                        va="center",
                        color="white" if values[i, j] > 65 else "black",
                    )
        fig.colorbar(display, ax=ax, label="Exakter Feld-Recall (%)")
        fig.tight_layout()
        save(fig, "heatmap")
        samples = [
            [float(r["exact_f1"]) * 100 for r in rows if r["candidate"] == m and r["exact_f1"]]
            for m in methods
        ]
        kept = [(m, v) for m, v in zip(methods, samples, strict=True) if v]
        if kept:
            fig, ax = plt.subplots(figsize=(9, max(3, len(kept) * 0.6)))
            ax.boxplot(
                [v for _, v in kept],
                orientation="horizontal",
                tick_labels=[f"{m} (n={len(v)})" for m, v in kept],
                showmeans=False,
            )
            ax.set_xlim(-2, 102)
            ax.set_xlabel("Exakter Feld-F1 je Schulung (%); deskriptiv, nicht der gepoolte Gesamtscore")
            ax.set_title("Ergebnisverteilung über Schulungen")
            fig.tight_layout()
            save(fig, "distribution")
    fig, ax = plt.subplots(figsize=(10, 6))
    plotted = []
    colors = {"cached_components": "#b35a12", "no_reported_cache": "#167a91", "unknown": "#777777"}
    for row in payload["pareto"]:
        if row["seconds"] is None or row["quality"] is None or not row["comparable"]:
            continue
        plotted.append(row)
        ax.scatter(
            row["seconds"],
            100 * row["quality"],
            s=80,
            c=colors[row["cache_regime"]],
            marker="o" if row["complete"] else "x",
        )
        ax.annotate(
            row["candidate"],
            (row["seconds"], 100 * row["quality"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )
    if plotted and all(r["seconds"] > 0 for r in plotted):
        ax.set_xscale("log")
    if not plotted:
        ax.text(
            0.5,
            0.5,
            "Keine vergleichbare vollständige Laufzeitmessung vorhanden",
            ha="center",
            transform=ax.transAxes,
        )
    ax.set_ylim(-3, 104)
    ax.set_xlabel("Beobachtete volle Methodenzeit (s; ggf. logarithmisch)")
    ax.set_ylabel("Exakter Feld-F1 der Originalrollen (%)")
    ax.set_title("Qualität und Laufzeit – beobachteter Betrieb, kein kontrollierter Benchmark")
    from matplotlib.lines import Line2D

    ax.legend(
        handles=[
            Line2D([0], [0], marker="o", color="none", markerfacecolor=c, label=k) for k, c in colors.items()
        ],
        loc="best",
    )
    ax.grid(alpha=0.2)
    fig.tight_layout()
    save(fig, "quality_runtime")


def render(output, payload, *, figures=True):
    from .dashboard_report import render as render_dashboard

    if figures:
        render_figures(output / "scientific", payload)
    return render_dashboard(output, payload)
