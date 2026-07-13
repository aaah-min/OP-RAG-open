from __future__ import annotations

import logging

log = logging.getLogger("op_rag")


def trace_herb_lookup(herb_name: str, herb_record: dict | None, *, formula_id: str = "") -> None:
    """Log missing herb annotations without creating persistent runtime artifacts."""
    if herb_record is None:
        log.debug("No mechanism annotation for herb %s in %s", herb_name, formula_id)
