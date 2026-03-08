# Phase 2: Minimal Change Detection Engine (Local / CLI)

Now that we have successfully validated the SDK, tracking logic, and caching math (Phase 1), we are moving on to Phase 2 as defined in the README. The goal is to provide a useful answer locally to the question: **"Which change increased costs?"**

## Design Decisions Addressed

1. **Commit Hashes:** We will use `argparse` with explicit `dest` parameters (e.g. `parser.add_argument('--from', dest='commit_a')`) because `from` is a reserved Python keyword. This keeps the CLI surface clean while giving us usable internal keyword arguments.
2. **Time Format Contract:** We will use simple ISO date strings. We will explicitly document and enforce that all SQLite timestamps must follow strict ISO8601 formatting (`YYYY-MM-DDTHH:MM:SSZ`) without spaces to guarantee perfect lexicographical sorting for SQLite queries.
3. **Table Rendering API:** We will stick with `argparse`, keeping dependencies to 0. We will create a small private helper `_render_table()` in `cli.py` to format rows using `str.ljust` rather than scattering `f-strings`.
4. **Read/Write Query Helper Technical Debt:** Since `sinks.py` is primarily a write abstraction layer via `BaseSink`, placing arbitrary `SQL SELECT` queries inside it blurs the architecture. Since this is an MVP we will place a `# TODO: Extract into dedicate Read/Storage Model` comment to note the technical debt.
5. **Configurable Thresholds:** We will define clear, explicit constants at the top of `engine.py` (e.g. `REGRESSION_ABSOLUTE_THRESHOLD_USD = 0.01` and `REGRESSION_PERCENT_THRESHOLD = 0.10`) rather than burying them inside calculation logic, opening the door for easy user-configurable flags in the future.

## User Review Required

> [!NOTE]
> Do you have a preference for the CLI framework? Python's built-in `argparse` is great for 0-dependency requirements, but `click` or `typer` offer a better developer experience for complex CLIs. Given the project goal of limiting dependencies, I recommend `argparse`. Let me know if you agree.

## Proposed Changes

### Core Package updates

#### [NEW] `veritas/cli.py`
- Setup an `argparse` interface for the `veritas` command line tool.
- Subcommand: `diff --feature <name> --from <commit_A> --to <commit_B>`
- Subcommand: `stats --feature <name> --since <time>` (Time format is standard ISO string)
- Output clear terminal tables displaying averages, deltas, and whether it hits the regression threshold utilizing a custom `_render_table()` helper.

#### [NEW] `veritas/engine.py`
- Implement the comparison and heuristics engine.
- Fetch rows from `events` where `feature=?` and `commit=?`.
- If zero rows are returned for *either* commit hash, throw an explicit, clear error string (e.g. `No data found for commit abc123`) instead of returning `0` or encountering a divide-by-zero error.
- Calculate `avg_cost_per_request`, `avg_tokens_in`, `avg_tokens_out`.
- Calculate percentage deltas between Commit A and Commit B.
- Implement the "Regression Heuristics" (e.g., > 10% increase AND > $X absolute delta).

#### [MODIFY] `veritas/sinks.py`
- Add simple query helper methods to read from the local SQLite database.

### Build System

#### [MODIFY] `pyproject.toml`
- Expose the console script so users can type `veritas diff` from anywhere.
```toml
[project.scripts]
veritas = "veritas.cli:main"
```

## Verification Plan

### Automated Tests
- Scaffold `test_cli.py` to ensure commands execute correctly and print expected text without throwing. Validate explicit printing of Empty Result states (e.g. when an invalid commit hash is passed).
- Scaffold `test_engine.py` with mocked SQLite rows to ensure math percentages and threshold alarms trigger exactly when costs regress. Ensure the average calculations properly handle dividing large integers and scaling gracefully.

### Manual Verification
- We will construct an offline Python script that generates 10 unique tracking events for Commit A (Base) using small parameters, and 10 isolated tracking events for Commit B (Regressed) using larger fake prompts.
- We will execute `veritas diff` to prove that the table renders correctly, averages correctly across the 10 data points per hash, and accurately flags the Regression threshold.
