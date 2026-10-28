# demo-codex-usage-audit

Codex users report that their 5-hour and weekly limits drain faster than before, and OpenAI
has not explained it. This tool reads the rate-limit readings that the Codex CLI already writes
to your local session logs and flags any sudden jump, so you can check the claim with your own
data before you argue about it.

The tool is read-only. It sends nothing over the network and changes no logs.

## Run it

```bash
uv run codex-usage-audit --demo          # bundled sample logs, shows one flagged cliff
uv run codex-usage-audit                 # your logs in ~/.codex/sessions
uv run codex-usage-audit --threshold 3   # flag smaller jumps
uv run codex-usage-audit --max-gap 120   # count jumps up to 2 hours apart as sudden
uv run pytest -q                         # tests
```

The sample run prints:

```
Read 6 rate-limit readings.
Sudden jumps (more than 5 points within 60 minutes):
  2026-10-16T18:10:00Z  168h window  21.0% -> 33.0%  (+12.0)  40m after the previous reading
```

## What you need

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Codex CLI session logs in `~/.codex/sessions/` (or pass `--sessions DIR`)
- No API key

## Caveats

- OpenAI does not document the session-log format. The field names (`rate_limits`,
  `used_percent`, `window_minutes`, `resets_at`, `plan_type`) come from community reports in
  [openai/codex#54677](https://github.com/openai/codex/issues/54677). The parser looks for them
  wherever they sit in each line. If the format changes, you get "no events found", not wrong numbers.
- A jump shows the meter moved. It does not show why. A real cause could be a metering defect,
  a silent allowance change, or the cost of a model switch. This tool cannot tell those apart.
- Codex only logs readings while a CLI session runs. Usage elsewhere, such as the desktop app,
  cloud tasks or another machine, shows up as one big rise at your next reading. So a rise
  counts as sudden only when the previous reading is within `--max-gap` minutes and on the same
  plan. Readings that report no plan are left out, since they appear to be placeholders.
- The bundled fixture is synthetic. It is there to show the output, not as evidence about OpenAI.

## Sources

- Thread that prompted this: https://x.com/thsottiaux/status/2111990254408434095
- Reports and logs: https://github.com/openai/codex/issues/54677
- Upstream CLI: https://github.com/openai/codex (Codex CLI writes the session logs read here)

## License

MIT. See [LICENSE](LICENSE).
