"""Supported relationship types between concepts (spec §10)."""

PREREQUISITE_OF = "PREREQUISITE_OF"
RELATED_TO = "RELATED_TO"
PART_OF = "PART_OF"
EXAMPLE_OF = "EXAMPLE_OF"
DERIVED_FROM = "DERIVED_FROM"
CONTRADICTS = "CONTRADICTS"

RELATION_TYPES = frozenset(
    {PREREQUISITE_OF, RELATED_TO, PART_OF, EXAMPLE_OF, DERIVED_FROM, CONTRADICTS}
)

# Direction convention: source --PREREQUISITE_OF--> target means the source
# concept is a prerequisite of the target concept.
