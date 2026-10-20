# Configuration

Validated YAML configuration files live here. P01 adds the asset registry and deterministic risk limits. Load configuration through `tb.core.config.load_config`; do not parse YAML directly in trading components.

Secrets never belong in this directory. Put optional credentials only in the ignored repository-root `.env` file.
