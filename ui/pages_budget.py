"""The Budget Analysis screen: the deterministic estimate, presented.

Nothing on this screen calculates anything. Every figure comes from
``core.budget_engine`` through :func:`ui.budget.compute_estimate`; this module
only decides the order they are read in, how they are formatted, and what has to
be said about their limits:

* **the total is indicative**, not a quotation — the catalog's own disclaimer is
  shown rather than a paraphrase;
* **materials are not in the total and are not zero** — there is no material
  price list, so their cost is unknown, and an empty row would read as "free";
* **an unpriced item is not a free item** — the engine reports it, the total
  excludes it, and the screen says the estimate is incomplete instead of
  presenting an understated figure as final.

The estimate is computed deterministically after the layout is calculated, so it
is already available when the design is evaluated. This screen is where it is
read, checked and recalculated.
"""

from __future__ import annotations

from typing import Final, Sequence

from core.budget_engine import BudgetResult, LineItem
from workflow.state import WorkflowStep

from ui import budget as budget_view, commits, references, session, theme
from ui.shell import render_flash, render_shell_header, stage_eyebrow

_RECALCULATE_NOTE = (
    "Recalculating repeats the same deterministic arithmetic on the current "
    "basket. It sends nothing to the AI model and does not touch the layout."
)

_COVERAGE_NOTE = (
    "The estimate covers the catalog furniture in the current basket, priced "
    "from the local catalog's illustrative unit costs and multiplied by the "
    "requested quantity. Materials, labour, delivery, installation and VAT are "
    "outside it."
)

#: Below this many priced lines a bar chart says less than the table above it.
_MIN_LINES_FOR_CHART: Final[int] = 2


# --------------------------------------------------------------------------- #
# The three headline figures
# --------------------------------------------------------------------------- #


def _render_totals(state, result: BudgetResult) -> None:
    """Total, limit, then remaining or overrun — in that order."""

    import streamlit as st

    analysis = result.analysis
    currency = analysis.currency
    over = analysis.is_over_budget

    columns = st.columns(3, gap="medium")
    with columns[0]:
        theme.html_block(
            theme.score_line(
                "Indicative total",
                commits.format_money(analysis.total_estimated, currency),
                "Furniture only. Materials are not included.",
            )
        )
    with columns[1]:
        theme.html_block(
            theme.score_line(
                "Your budget",
                commits.format_money(state.budget.total_budget, currency),
                "As saved in your design preferences.",
            )
        )
    with columns[2]:
        theme.html_block(
            theme.score_line(
                "Over budget by" if over else "Remaining budget",
                commits.format_money(
                    abs(analysis.remaining_budget)
                    if over
                    else analysis.remaining_budget,
                    currency,
                ),
                "How far the design exceeds your limit."
                if over
                else "What is left of the limit you set.",
            )
        )

    # Usage is a proportion of the limit, so it belongs under all three figures
    # rather than as the caption of the one card that does not hold it. The
    # previous placement read as "96.3% of the budget limit" attached to the
    # remaining amount.
    if result.budget_usage_percent is None:
        theme.html_block(
            f'<p class="hm-meter-caption">{theme.escape(budget_view.usage_text(result))}'
            "</p>"
        )
    else:
        theme.html_block(
            theme.usage_meter(
                float(result.budget_usage_percent), over=over
            )
        )

    badge = (
        theme.error_badge("Over budget")
        if over
        else theme.success_badge("Within budget")
    )
    sentence = (
        f"The indicative furniture total is "
        f"{commits.format_money(abs(analysis.remaining_budget), currency)} "
        "above the budget you set. The design is not affordable as priced."
        if over
        else "The indicative furniture total fits inside the budget you set."
    )
    theme.html_block(theme.status_row(badge, sentence))

    if not result.is_trustworthy:
        theme.html_block(
            theme.error_badge("Estimate incomplete")
            + theme.paragraph(budget_view.INCOMPLETE_NOTE)
        )

    for warning in result.warnings:
        st.warning(warning)


# --------------------------------------------------------------------------- #
# Per-item detail
# --------------------------------------------------------------------------- #


def _render_lines(result: BudgetResult) -> None:
    """One row per priced recommendation, with quantity and line total."""

    currency = result.analysis.currency
    theme.html_block(theme.group_heading("Item costs"))
    if not result.line_items:
        theme.html_block(
            '<p class="hm-card-copy">No item in the basket could be priced, so '
            "there is no item table.</p>"
        )
        return

    rows = "".join(
        "<tr>"
        f"<td>{theme.escape(line.name)}</td>"
        f'<td class="hm-num">{line.quantity}</td>'
        f'<td class="hm-num">{commits.format_money(line.unit_cost, currency)}</td>'
        f'<td class="hm-num">{commits.format_money(line.line_total, currency)}</td>'
        "</tr>"
        for line in result.line_items
    )
    theme.html_block(
        '<table class="hm-table">'
        "<thead><tr><th>Item</th><th>Qty</th><th>Unit cost</th>"
        "<th>Line total</th></tr></thead>"
        f'<tbody>{rows}</tbody>'
        "</table>"
        + theme.field_note(
            "The line total is the catalog unit cost multiplied by the quantity, "
            "then added to the subtotal. Every figure is calculated in Python."
        )
    )


def _render_errors(result: BudgetResult) -> None:
    """Basket problems, kept apart from the over-budget warning."""

    if not result.errors:
        return
    theme.html_block(
        theme.group_heading("Problems in the basket")
        + theme.paragraph(
            "These entries could not be priced. They are excluded from the "
            "total, not costed at zero."
        )
        + "".join(
            '<div class="hm-issue hm-issue--error">'
            '<span class="hm-issue-kind">Error</span>'
            f"{theme.escape(error.message)}</div>"
            for error in result.errors
        )
    )


def _render_subtotals(result: BudgetResult) -> None:
    """The composition of the total, including what is not in it."""

    analysis = result.analysis
    currency = analysis.currency
    theme.html_block(
        theme.group_heading("How the total is built")
        + theme.summary(
            [
                (
                    "Furniture subtotal",
                    commits.format_money(analysis.furniture_subtotal, currency),
                ),
                (
                    "Materials and finishes",
                    "Not priced — excluded from the total",
                ),
                ("Other expenses", "None recorded"),
                (
                    "Total estimated",
                    commits.format_money(analysis.total_estimated, currency),
                ),
                ("Priced lines", str(result.line_count)),
            ]
        )
        + theme.field_note(budget_view.MATERIALS_NOTE)
    )


def _render_materials(state) -> None:
    """The materials the design specifies, listed as unpriced."""

    theme.html_block(theme.group_heading("Materials outside the estimate"))
    if not state.materials:
        theme.html_block(
            '<p class="hm-card-copy">No materials were recommended for this '
            "concept.</p>"
        )
        return
    rows = "".join(
        "<tr>"
        f"<td>{theme.escape(material.name)}</td>"
        f"<td>{theme.escape(material.category)}</td>"
        '<td class="hm-num">Not priced</td>'
        "</tr>"
        for material in state.materials
    )
    theme.html_block(
        '<table class="hm-table">'
        "<thead><tr><th>Material</th><th>Category</th><th>Cost</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>"
        + theme.field_note(
            "The application has no material price list. These entries are part "
            "of the design but not of the furniture total."
        )
    )


# --------------------------------------------------------------------------- #
# Distribution
# --------------------------------------------------------------------------- #


def distribution_alt_text(line_items: Sequence[LineItem], currency: str) -> str:
    """The chart's alternative text: what it draws, and every figure in it.

    A Matplotlib figure reaches the browser as a bare ``<img>``, so without this
    a screen reader announces an unlabelled graphic and the numbers inside it
    exist only for people who can see them. axe-core reported exactly that as a
    serious ``image-alt`` violation.

    The sentence names the chart type, its unit and every bar's value, then
    points at the table that already holds the same figures — a real alternative
    rather than a restatement of the heading.
    """

    bars = "; ".join(
        f"{item.name}: {item.line_total:,.0f} {currency}"
        for item in sorted(line_items, key=lambda item: item.line_total, reverse=True)
    )
    return (
        "Horizontal bar chart of the indicative line total per item, in "
        f"{currency}. {bars}. The same figures appear in the item costs table "
        "above."
    )


def _render_distribution(result: BudgetResult) -> None:
    """A bar per priced line, drawn with the already-installed Matplotlib.

    The chart repeats the table's line totals; it adds no new figure. It is
    omitted when there are too few lines for a bar to say anything, so the
    screen never implies a distribution it cannot show.
    """

    import streamlit as st

    if len(result.line_items) < _MIN_LINES_FOR_CHART:
        return

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    currency = result.analysis.currency
    ordered = sorted(result.line_items, key=lambda line: line.line_total)
    labels = [line.name for line in ordered]
    values = [float(line.line_total) for line in ordered]

    figure, axes = plt.subplots(figsize=(7, max(2.2, 0.42 * len(labels) + 1.0)))
    axes.barh(labels, values, color=theme.COLORS["primary"])
    axes.set_xlabel(f"Indicative line total ({currency})")
    axes.set_title("Cost by item", loc="left", fontsize=11)
    axes.tick_params(axis="both", labelsize=9)
    axes.spines["top"].set_visible(False)
    axes.spines["right"].set_visible(False)
    figure.tight_layout()

    theme.html_block(theme.group_heading("Cost distribution"))
    # The chart is an image, so it needs an accessible name of its own: a screen
    # reader otherwise announces an unlabelled graphic and the figures inside it
    # are unreachable.
    st.pyplot(
        figure, width="stretch", alt=distribution_alt_text(ordered, currency)
    )
    plt.close(figure)
    theme.html_block(
        theme.field_note(
            "Same figures as the item table: each bar is one line total. "
            "Materials are absent because they are not priced."
        )
    )


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


def _recalculate(state) -> None:
    """Recompute deterministically and record the result. No AI, no network."""

    import streamlit as st

    assert state.room is not None
    result = budget_view.compute_estimate(
        state.budget, state.furniture, references.load_catalog()
    )
    dropped = state.record_budget_analysis(result.analysis)
    if dropped:
        # Storing a refreshed analysis does not drop anything else, but say so
        # from the workflow's own answer rather than assuming it.
        message = session.invalidation_message(
            dropped, previously_present=session.present_keys(state)
        )
        if message:
            session.set_flash(message, tone="info")
            st.rerun()
            return
    session.set_flash(
        "The estimate has been recalculated from the current basket.", tone="success"
    )
    st.rerun()


# --------------------------------------------------------------------------- #
# Navigation
# --------------------------------------------------------------------------- #


def _render_navigation(state, *, current: bool = True) -> None:
    import streamlit as st

    forward, back, restart = st.columns([2, 1, 1], gap="small")
    with forward:
        # ``current`` is False on the stale-estimate branch, where the screen's
        # own primary action is "Recalculate the estimate". Leaving the forward
        # button primary there would put two primaries side by side, which is
        # the ambiguity the single-primary rule exists to remove.
        if st.button(
            "Continue to the final report",
            type="primary" if current else "secondary",
            width="stretch",
        ):
            session.go_to(session.SCREEN_REPORT)
    with back:
        if st.button("Back to the evaluation", width="stretch"):
            session.go_to(session.SCREEN_EVALUATION)
    with restart:
        if st.button("Start a new project", width="stretch"):
            session.reset_workflow()
            session.set_flash(
                "Project cleared. Describe a new room to begin.", tone="info"
            )
            session.go_to(session.SCREEN_ROOM)


# --------------------------------------------------------------------------- #
# The screen
# --------------------------------------------------------------------------- #


def render() -> None:
    """Draw the budget screen."""

    import streamlit as st

    state = session.get_workflow()
    if state.room is None or state.preferences is None:
        session.set_flash(
            "Save the room and the design preferences first.", tone="warning"
        )
        session.go_to(session.SCREEN_ROOM)
        return

    if not state.is_complete(WorkflowStep.RECOMMENDATIONS):
        session.set_flash(
            "Recommend furniture before analysing the budget.", tone="warning"
        )
        session.go_to(session.SCREEN_PLAN)
        return

    if state.budget_analysis is None:
        session.set_flash(
            "The estimate is calculated from the basket; calculate the layout on "
            "the plan screen first.",
            tone="warning",
        )
        session.go_to(session.SCREEN_PLAN)
        return

    render_shell_header(state, "Design Plan")
    render_flash()

    theme.html_block(
        theme.page_intro(
            stage_eyebrow("Design Plan") + " · Budget",
            "Indicative budget analysis",
            "Every figure below is calculated by the application from the local "
            "catalog's illustrative costs and the quantities in your basket. The "
            "AI model is not involved: it never adds a price, totals a basket or "
            "decides whether the design is affordable.",
        )
    )

    result = budget_view.compute_estimate(
        state.budget, state.furniture, references.load_catalog()
    )
    stale = not budget_view.matches(state.budget_analysis, result)

    if stale:
        theme.html_block(
            theme.warning_badge("Recalculation needed")
            + theme.paragraph(
                "The stored estimate no longer matches the current basket, so it "
                "is not shown as current. Recalculate it below."
            )
        )
        if st.button("Recalculate the estimate", type="primary", width="stretch"):
            _recalculate(state)
        _render_navigation(state, current=False)
        return

    _render_totals(state, result)
    _render_lines(result)
    _render_subtotals(result)
    _render_errors(result)
    _render_materials(state)
    _render_distribution(result)

    theme.html_block(theme.call_note(_RECALCULATE_NOTE))
    if st.button("Recalculate the estimate", width="stretch"):
        _recalculate(state)

    theme.html_block(theme.footnote(_COVERAGE_NOTE))
    theme.html_block(theme.footnote(budget_view.INDICATIVE_NOTE))
    theme.html_block(theme.footnote(references.catalog_image_free_note()))
    _render_navigation(state)


__all__ = ["render"]
