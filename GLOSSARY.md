# Card Zard

A Magic: The Gathering deck analysis assistant for the Commander format. It answers questions about a deck using real card data, computing anything calculable and explaining the results.

## Cards

**Card**:
A distinct Magic card as defined by its rules text, regardless of which set it was printed in. Identified by its Oracle ID.
_Avoid_: Printing, card object

**Oracle ID**:
Scryfall's stable identifier for a Card, shared by every printing of it.
_Avoid_: Card ID, Scryfall ID

**Printing**:
One physical release of a Card in a particular set, with its own set code, collector number and art. Card Zard ignores Printings.
_Avoid_: Edition, version

**Card Name**:
The full name of a Card. For multi-faced cards this is both faces joined by ` // `, for example _Fable of the Mirror-Breaker // Reflection of Kiki-Jiko_.

**Front-Face Name**:
The name of only the first face of a multi-faced Card, for example _Fable of the Mirror-Breaker_.

**Snapshot**:
A complete, versioned copy of Scryfall's card data at a point in time. Every Analysis is produced against exactly one Snapshot.
_Avoid_: Dump, cache, database

**Oracle Tag**:
A community-maintained label from Scryfall Tagger describing what a Card does, such as "ramp" or "card advantage". Oracle Tags are an input for assigning Roles; they are not Roles.
_Avoid_: Tag (on its own)

## Decks

**Deck List**:
The text a user submits to describe a deck, either pasted or fetched from a deck site. It may be messy, misspelled or include extra sections.
_Avoid_: Decklist file, import

**Deck Line**:
One line of a Deck List naming a quantity and a card, such as `1 Sol Ring (C21) 263`.

**Resolved Deck**:
The result of matching every Deck Line to a Card in a Snapshot: the Commanders, the Main Deck, and any Unresolved Lines.
_Avoid_: Parsed deck, deck object

**Unresolved Line**:
A Deck Line that could not be matched to exactly one Card. It is reported to the user, sometimes with suggestions, and is never silently corrected.
_Avoid_: Error, missing card

**Commander**:
The legendary card (or one of two paired cards) that leads a Commander deck and defines its Color Identity.
_Avoid_: General, leader

**Commander Pair**:
Two Commanders leading one deck through Partner, Partner with, Background, Friends forever or Doctor's companion. Their Color Identities combine.
_Avoid_: Partners (when meaning a Background or Doctor's companion pair)

**Color Identity**:
The set of colors a deck may use, determined by the mana symbols on its Commander or Commander Pair.
_Avoid_: Deck colors, color

**Main Deck**:
Every card in a deck other than the Commander or Commander Pair.
_Avoid_: The 99, library

**Ignored Section**:
A part of a Deck List that is not part of the deck, such as Sideboard, Maybeboard or Considering. It is left out of the Analysis and listed back to the user.
_Avoid_: Sideboard (as a general term)

## Analysis

**Analysis**:
The full set of Counts and Verdicts computed for a Resolved Deck against one Snapshot.
_Avoid_: Report, result, answer

**Count**:
A fact computed directly from card data, such as the number of lands or the mana curve. A Count is never an opinion.
_Avoid_: Stat, metric

**Land**:
A card whose front face has the land type. MDFC Lands are counted separately.

**MDFC Land**:
A modal double-faced card that is a spell on one face and can be played as a land on the other. It counts as a fraction of a Land in Rules, never as a full Land.
_Avoid_: Modal land, spell land

**Color Source**:
A card that can produce mana of a given color for this deck. Land Sources and Nonland Sources are always counted separately.
_Avoid_: Mana source (unqualified)

**Land Source**:
A Land, or MDFC Land, that is a Color Source.

**Nonland Source**:
A non-land card that is a Color Source, such as a mana rock or a creature that makes mana.
_Avoid_: Mana rock (as a general term)

**Role**:
One of a small, fixed set of jobs a card does in a deck: ramp, card draw, targeted removal, board wipe, tutor, counterspell, protection or recursion. A card can have more than one Role.
_Avoid_: Category, tag, function

**Rule**:
A named, cited guideline that turns Counts into a Verdict, such as a land-count guideline based on published Commander mana analysis.
_Avoid_: Heuristic, check

**Verdict**:
A judgment about a deck produced by a Rule, such as "too few Land Sources of blue". Every Verdict names the Rule that produced it.
_Avoid_: Recommendation, warning, opinion

**Share Link**:
A URL that reopens an Analysis by re-running it on the stored Deck List.
_Avoid_: Permalink, saved analysis
