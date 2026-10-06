"""End-to-end live demo: `make demo` / `python -m sentinel`.

Walks the full five-layer loop on the sample data and narrates each step, so you
can run it live in under a minute. The punchline: every deterministic check
passes on v2, yet the semantic sentinel catches the silent meaning drift and
trips the circuit breaker.
"""

from __future__ import annotations

import asyncio

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .adapter import process_batch
from .circuit_breaker import evaluate_gate
from .config import settings
from .metrics import compute_loop_metrics
from .schemas import DEMO_QUESTIONS, CircuitState, RowEvaluation
from .warehouse import Warehouse

console = Console()


def _rule(title: str) -> None:
    console.rule(f"[bold]{title}")


def _deterministic_panel(wh: Warehouse) -> None:
    _rule("1 · BigQuery  ·  deterministic SQL checks")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("deployment")
    table.add_column("rows", justify="right")
    for check in ["completeness_null_summary", "schema_invalid_category",
                  "uniqueness_duplicate_id", "freshness_stale_rows"]:
        table.add_column(check.split("_")[0], justify="center")
    for version in ("v1", "v2"):
        rep = wh.deterministic_checks(version)
        cells = [
            "[green]PASS[/]" if rep.failures[c] == 0 else f"[red]{rep.failures[c]} FAIL[/]"
            for c in ["completeness_null_summary", "schema_invalid_category",
                      "uniqueness_duplicate_id", "freshness_stale_rows"]
        ]
        table.add_row(version, str(rep.total_rows), *cells)
    console.print(table)
    console.print(
        "[dim]Every deterministic check is green on both versions. "
        "If meaning drifted, SQL cannot see it.[/]\n"
    )


async def _evaluate_version(wh: Warehouse, version: str) -> list[RowEvaluation]:
    rows = wh.rows_to_evaluate(version)
    console.print(
        f"  → routing [bold]{len(rows)}[/] {version} rows to the async adapter "
        f"(backend=[magenta]{settings.backend}[/], "
        f"concurrency={settings.max_concurrency})"
    )
    evals = await process_batch(rows, DEMO_QUESTIONS)
    wh.write_metrics(evals)  # layer 5: closed loop
    return evals


def _eval_table(version: str, evals: list[RowEvaluation]) -> None:
    table = Table(title=f"{version} semantic evaluation (typed Jev-style answers)",
                  show_header=True, header_style="bold cyan", title_justify="left")
    table.add_column("row")
    table.add_column("addresses_ticket", justify="right")
    table.add_column("category_ok", justify="right")
    table.add_column("resolution(1-5)", justify="right")
    table.add_column("quality", justify="right")
    for e in evals:
        a = e.answers
        q = e.quality
        qcol = "green" if q >= 0.7 else ("yellow" if q >= 0.5 else "red")
        table.add_row(
            e.row_id,
            f"{a['summary_addresses_ticket'].noul:.2f}",
            f"{a['category_correct'].noul:.2f}",
            f"{a['resolution_quality'].score:.1f}",
            f"[{qcol}]{q:.2f}[/]",
        )
    console.print(table)


def _breaker_panel(decision, review: list[RowEvaluation]) -> None:
    tripped = decision.state == CircuitState.OPEN
    head = "🚨 CIRCUIT BREAKER TRIPPED (OPEN)" if tripped else "✅ CIRCUIT CLOSED"
    body = Text()
    body.append(f"deployment      {decision.deployment_version}\n")
    body.append(f"mean quality    {decision.mean_quality:.3f}\n")
    body.append(f"drift vs base   {decision.drift_vs_baseline:+.3f}\n")
    body.append(f"reason          {decision.reason}\n")
    if tripped:
        body.append("\nactions:\n", style="bold")
        body.append("  • fired downstream pipeline alert (Slack)\n")
        body.append(f"  • routed {len(review)} worst rows to human review queue\n")
    console.print(Panel(body, title=head,
                        border_style="red" if tripped else "green"))
    if review:
        rt = Table(title="human review queue (lowest quality rows)",
                   header_style="bold yellow", title_justify="left")
        rt.add_column("row")
        rt.add_column("quality", justify="right")
        rt.add_column("why flagged")
        for e in review:
            rt.add_row(e.row_id, f"{e.quality:.2f}",
                       "resolution_summary does not address the ticket")
        console.print(rt)


def _metrics_panel(all_evals: list[RowEvaluation]) -> None:
    _rule("operational metrics  ·  the numbers worth monitoring")
    # Ground truth: v1 rows are good, v2 rows are the silently-drifted ones.
    human = {f"{e.row_id}@{e.deployment_version}": (e.deployment_version == "v1")
             for e in all_evals}
    m = compute_loop_metrics(all_evals, human_labels=human)
    table = Table(show_header=False)
    table.add_column("metric", style="bold")
    table.add_column("value")
    for v, q in sorted(m.mean_quality_by_version.items()):
        table.add_row(f"mean semantic quality · {v}", f"{q:.3f}")
    table.add_row("semantic drift (v1→v2)", f"{m.semantic_drift:+.3f}")
    dr = "n/a" if m.disagreement_rate is None else f"{m.disagreement_rate:.0%}"
    table.add_row("human vs evaluator disagreement", dr)
    table.add_row("latency p50 / p95", f"{m.p50_latency_ms:.0f} / {m.p95_latency_ms:.0f} ms")
    table.add_row("total cost per loop", f"${m.total_cost_usd:.6f}")
    table.add_row("cost per row", f"${m.cost_per_row_usd:.6f}")
    table.add_row("backend", m.backend)
    console.print(table)


async def run() -> int:
    console.print(Panel.fit(
        "[bold]semantic-drift-sentinel[/]\n"
        "semantic quality as a continuous infrastructure metric\n"
        "[dim]BigQuery → Cloud Run (async) → Jev typed eval → circuit breaker → closed loop[/]",
        border_style="magenta"))

    wh = Warehouse()
    wh.seed()

    _deterministic_panel(wh)

    _rule("2-3 · Cloud Run async adapter  →  Jev typed semantic evaluation")
    v1 = await _evaluate_version(wh, "v1")
    _eval_table("v1", v1)
    v2 = await _evaluate_version(wh, "v2")
    _eval_table("v2", v2)

    baseline = sum(e.quality for e in v1) / len(v1)
    _rule("4 · data circuit breaker")
    decision, review = evaluate_gate(v2, "v2", baseline_quality=baseline)
    _breaker_panel(decision, review)

    _metrics_panel(v1 + v2)

    _rule("5 · closed loop")
    console.print(
        "Versioned quality metrics written back to the warehouse "
        f"([dim]{settings.warehouse_path}[/]). Query drift over time:")
    for row in wh.drift_by_version():
        console.print(
            f"  {row['deployment_version']}: n={row['n']} "
            f"mean_quality={row['mean_quality']:.3f} "
            f"cost=${row['total_cost']:.6f}")
    wh.close()

    console.print()
    console.print(Panel.fit(
        "Did this deployment preserve the meaning of our data?\n"
        "[bold red]No.[/] v2 passed every deterministic check and still "
        "regressed. The sentinel caught it and tripped the gate.",
        border_style="magenta"))
    return 0 if decision.state == CircuitState.OPEN else 1


def main() -> int:
    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
