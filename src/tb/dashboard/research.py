"""Read-only local research projection; live current rights precede result/price reads."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from tb.research.cli import status
from tb.research.importer import bars
from tb.research.registry import load, read_metadata
from tb.research.runner import read_result


def research_view(root: Path) -> None:
    st.subheader("Local Market Research")
    st.caption(
        "Frozen EMA/channel hypotheses · Offline local data · No execution or account returns"
    )
    now = datetime.now(UTC)
    try:
        catalog = status(root, now)
        st.dataframe(catalog["datasets"], hide_index=True, width="stretch")
        st.info(catalog["genuine_historical_evaluation"])
        pointer = read_metadata(root, "work/research/current.json", base="work/research")
        value = read_result(root, pointer["run_id"], now=now)
    except (ValueError, OSError, KeyError):
        st.info(
            "No currently authorized research result. Run the owned offline research demo; missing, expired or revoked data remains blocked."
        )
        return
    if value["source_class"] == "owned_synthetic":
        st.warning("SOFTWARE TEST ONLY — generated fixtures do not establish market profitability")
    st.info(value["evidence_status"])
    st.write(
        "Dataset:",
        value["dataset_id"],
        "· Provider:",
        value["provider"],
        "· Price type:",
        value["price_type"],
    )
    st.write("Coverage and data quality", value["quality"])
    st.write("Frozen strategy and evaluation protocol", value["protocol"])
    st.dataframe(value["results"], hide_index=True, width="stretch")
    st.caption(
        "Baselines use matched non-overlapping future windows. Missing outcomes are not filled. Non-overlap alone does not establish independence."
    )
    st.write("Rights/retention deadline", value["retention"])
    st.write(
        "Reproducibility",
        {k: value[k] for k in ("run_id", "source_sha256", "decision_sha256", "labels_sha256")},
    )
    st.info(value["execution_PnL"])
    if st.checkbox("Show authorized source-price sample", value=False):
        try:
            load(root, value["dataset_id"], datetime.now(UTC), display=True)
            sample = []
            for b in bars(root, value["dataset_id"], clock=lambda: datetime.now(UTC)):
                sample.append(
                    {
                        "symbol": b.symbol,
                        "source_UTC": b.source_at,
                        "price_type": value["price_type"],
                        "close": str(b.close),
                    }
                )
                if len(sample) >= 100:
                    break
            st.dataframe(sample, hide_index=True, width="stretch")
        except (ValueError, OSError, KeyError):
            st.info("Source prices withheld: display permission or source lifetime is not current.")
