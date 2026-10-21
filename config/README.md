# Configuration

Validated YAML configuration files live here. P01 adds the asset registry and deterministic risk
limits; P09 adds AI spend/cache policy. Load configuration through `tb.core.config.load_config`;
do not parse YAML directly in trading components. Paid AI entries remain disabled until a human
sets current nonzero token prices and explicit caps.

Secrets never belong in this directory. Put optional credentials only in the ignored repository-root `.env` file.
