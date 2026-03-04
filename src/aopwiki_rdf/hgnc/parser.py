"""HGNC TSV parser producing genedict1 (screening) and genedict2 (precision variants).

Extracted from monolith AOP-Wiki_XML_to_RDF_conversion.py lines 1811-1832.
"""

import logging

logger = logging.getLogger(__name__)

# Punctuation symbols used to create delimited variants for precision matching.
# Matches the monolith's symbols list exactly.
DELIMITER_SYMBOLS = [" ", "(", ")", "[", "]", ",", "."]


def parse_hgnc_genes(content: str) -> tuple[dict, dict]:
    """Parse HGNC TSV content into genedict1 (screening) and genedict2 (precision variants).

    Produces identical output to the monolith parsing logic. The first line
    (header) is skipped unconditionally to handle both old ("Synonyms") and
    new ("Alias symbols") header formats.

    Args:
        content: Raw TSV text from HGNC download or static file.

    Returns:
        Tuple of (genedict1, genedict2) where:
        - genedict1: symbol -> [symbol, approved_name, previous_symbols..., aliases..., accessions..., ensembl_id]
        - genedict2: symbol -> [s1+item+s2 for each item in genedict1 for each pair of delimiter symbols]
    """
    genedict1: dict[str, list[str]] = {}
    genedict2: dict[str, list[str]] = {}

    lines = content.split("\n")

    # Skip header line (first line) unconditionally
    for line in lines[1:]:
        line = line.rstrip("\n").rstrip("\r")
        if not line:
            continue

        a = line.split("\t")
        if len(a) < 2:
            continue

        symbol = a[1]

        # Filter out gene clusters (symbols containing '@')
        if "@" in symbol:
            continue

        genedict1[symbol] = []
        genedict2[symbol] = []

        # Column 1: approved symbol (always present)
        genedict1[symbol].append(a[1])

        # Column 2: approved name
        if len(a) > 2 and a[2] != "":
            genedict1[symbol].append(a[2])

        # Columns 3+: previous symbols, aliases, accession numbers, ensembl ID
        for item in a[3:]:
            if item != "":
                for name in item.split(", "):
                    genedict1[symbol].append(name)

        # Build punctuation-delimited variants
        for item in genedict1[symbol]:
            for s1 in DELIMITER_SYMBOLS:
                for s2 in DELIMITER_SYMBOLS:
                    genedict2[symbol].append(s1 + item + s2)

    logger.info(
        "HGNC parser: %d gene symbols parsed, %d total variants",
        len(genedict1),
        sum(len(v) for v in genedict2.values()),
    )

    return genedict1, genedict2
