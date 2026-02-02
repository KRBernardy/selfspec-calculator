# selfspec-calculator

Parametric hardware performance estimator (“calculator”) for the Self-Speculating Analog Architecture described in `Roadmap.md`.

## Quickstart

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
ppa-calculator \
  --model examples/model.yaml \
  --hardware examples/hardware.yaml \
  --stats examples/stats.json \
  --prompt-lengths 64 128 256 \
  --output out/report.json
```

The tool writes a machine-readable JSON report including per-prompt-length metrics, baseline comparison, and a Draft/Verify breakdown.
