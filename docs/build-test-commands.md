# Build And Test Commands

Canonical validation commands for this project.

## Package validation

```bash
python3 -m compileall -q orchestrator tests
```

## Test suite

```bash
python3 -m unittest discover -s tests
```

## Orchestrator config check

```bash
orchestrator check-config
```
