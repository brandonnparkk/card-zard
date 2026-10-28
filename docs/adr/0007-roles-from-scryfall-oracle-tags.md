# Roles come from Scryfall Oracle Tags plus manual overrides

Each card's Roles are assigned by mapping Scryfall's community Oracle Tags (the `oracle_tags` bulk file) onto our closed Role list, with a checked-in file of manual overrides for mistakes and missing tags. We rejected writing our own pattern matching on rules text, which is brittle across Magic's wording variations, and asking an LLM to classify every card, which costs money, isn't repeatable and conflicts with ADR-0001. Pattern matching is used only where card data is reliably structured, such as Scryfall's `produced_mana` field for Color Sources.

## Consequences

- Newly released cards may have no Oracle Tags for a while, so they get no Roles until they're tagged or overridden.
- The Role list starts as ramp, card draw, targeted removal, board wipe, tutor, counterspell, protection and recursion. Adding a Role means extending the tag mapping.
