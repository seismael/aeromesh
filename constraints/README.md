# Tested dependency snapshot

`ci-python.txt` records exact installed dependency versions used to validate
AeroMesh 1.0.0 on Linux and CPython 3.12. CI also exercises this snapshot on Python
3.11 and 3.13. Package metadata restricts runtime API families; the constraint
file removes resolver drift within those families for development and CI:

```bash
python -m pip install -c constraints/ci-python.txt -e 'packages/aero[dev]' -e packages/sdk-python
python -m pip check
```

This is a version snapshot, not a hash-locked deployment environment, vulnerability
assessment, or guarantee for every operating system. Distributions resolved by
pip still depend on platform and Python ABI. Container-based deployments should
also record the image digest and retain the actual approved artifacts.

Update intentionally: resolve in a clean environment, review dependency changes,
regenerate exact pins, run offline regression and real MCP tests, build wheels
from source distributions, and run `scripts/check_distribution.py` using only
installed wheels. Require the Docker isolation job for a release. Live-model
results must be reported separately; skips do not establish provider compatibility.

CI never makes paid provider calls on pull requests or normal pushes. A maintainer
can dispatch the live job from `main` after configuring the `live-model-tests`
GitHub environment with required reviewers and a `DEEPSEEK_API_KEY` environment
secret. Without a configured key that job fails explicitly.
