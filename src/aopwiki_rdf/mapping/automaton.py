"""Aho-Corasick automaton for gene-name matching.

Replaces a nested loop that tested all ~45,000 genes against every text, using a
``genedict2`` of every token pre-expanded with all 49 combinations of leading and
trailing delimiter -- 7.4 million materialised strings, and a scan cost
proportional to (genes x tokens x texts).

The automaton scans each text ONCE, in time proportional to the text length
regardless of dictionary size, and stores each token once.

Implemented in pure Python deliberately: ``pyahocorasick`` is faster, but this
runs in the weekly production pipeline and a C extension is a build-time failure
mode the pipeline does not currently have. The dictionary is built once per run
and the corpus is small enough that the constant factor does not dominate.

Boundary semantics
------------------
A match counts only when the characters immediately before and after it are
delimiters. The delimiter set is exactly the one ``genedict2`` enumerated --
space, parens, brackets, comma, period -- so results are unchanged, EXCEPT that
the start and end of the text now count as boundaries.

That difference is the point: every ``genedict2`` variant was
delimiter+token+delimiter, so a token opening a text had no leading delimiter to
match against and was missed entirely, no matter how unambiguous it was. It was
pinned as a strict xfail in tests/unit/test_gene_precision.py.
"""

import logging

logger = logging.getLogger(__name__)

# Exactly the delimiters genedict2 enumerated. Kept identical rather than
# widened to \W so this change is a pure structural swap: broadening what counts
# as a boundary (to catch "TP53-mediated", say) would alter recall and belongs in
# its own measured change.
DELIMITERS = frozenset(' ()[],.')


def _is_boundary(text: str, index: int) -> bool:
    """True when ``index`` is outside the text or holds a delimiter."""
    if index < 0 or index >= len(text):
        return True  # start/end of text -- the gap the old expansion could not express
    return text[index] in DELIMITERS


class GeneAutomaton:
    """Aho-Corasick automaton mapping token occurrences to gene IDs.

    Built from ``{token: gene_key}``. Tokens resolved to ``None`` by contested-
    token resolution are simply not added, so retired tokens cost nothing at
    scan time.
    """

    __slots__ = ('_goto', '_fail', '_output', '_token_len', '_size')

    def __init__(self, token_owners: dict):
        # Node 0 is the root. Parallel arrays keep this compact: a dict per node
        # for transitions, plus flat lists for fail links and outputs.
        self._goto = [{}]
        self._fail = [0]
        self._output = [None]   # node -> (token_length, gene_key) or None
        self._token_len = 0
        self._size = 0

        for token, gene_key in token_owners.items():
            if gene_key is None or not token:
                continue
            self._add(token, gene_key)

        self._build_failure_links()
        logger.info(
            "Gene automaton: %d tokens over %d states",
            self._size, len(self._goto),
        )

    def _add(self, token: str, gene_key: str) -> None:
        node = 0
        for char in token:
            nxt = self._goto[node].get(char)
            if nxt is None:
                nxt = len(self._goto)
                self._goto.append({})
                self._fail.append(0)
                self._output.append(None)
                self._goto[node][char] = nxt
            node = nxt
        # A token claimed twice would be a bug in ownership resolution; keep the
        # first so behaviour is deterministic rather than dict-order dependent.
        if self._output[node] is None:
            self._output[node] = (len(token), gene_key)
            self._size += 1

    def _build_failure_links(self) -> None:
        """Standard BFS construction of failure links."""
        queue = []
        for node in self._goto[0].values():
            self._fail[node] = 0
            queue.append(node)

        head = 0
        while head < len(queue):
            current = queue[head]
            head += 1
            for char, target in self._goto[current].items():
                queue.append(target)
                state = self._fail[current]
                while state and char not in self._goto[state]:
                    state = self._fail[state]
                self._fail[target] = (
                    self._goto[state][char] if char in self._goto[state] else 0
                )

    def find(self, text: str):
        """Yield ``(start, end, gene_key)`` for every delimiter-bounded match.

        Overlapping matches are all reported -- the caller decides which to keep.
        This is what removes the need for a separate contested-token pass: an
        automaton naturally surfaces every token spanning a position, where the
        old screen-then-confirm loop could only see one gene at a time.
        """
        node = 0
        for index, char in enumerate(text):
            while node and char not in self._goto[node]:
                node = self._fail[node]
            node = self._goto[node].get(char, 0)

            # Walk the failure chain so shorter tokens ending here are not lost.
            state = node
            while state:
                entry = self._output[state]
                if entry is not None:
                    length, gene_key = entry
                    start = index - length + 1
                    if _is_boundary(text, start - 1) and _is_boundary(text, index + 1):
                        yield start, index + 1, gene_key
                state = self._fail[state]

    def __len__(self) -> int:
        return self._size
