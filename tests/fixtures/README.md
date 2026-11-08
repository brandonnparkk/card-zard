# Test fixtures

## `oracle-cards-sample.jsonl`

75 real Cards copied verbatim from Scryfall's `oracle_cards` bulk file, one JSON object per line, unmodified and in source-file order. Tests load this instead of the full bulk file.

### How it was generated

- Source: `data/raw/oracle-cards.jsonl`, downloaded by `backend/scripts/download_scryfall.py` from `https://data.scryfall.io/oracle-cards/oracle-cards-20261101220203.jsonl.gz` (Scryfall bulk-data `updated_at` 2026-11-01T22:02:03.472+00:00).
- Cards were picked by exact Card Name or Front-Face Name, or by filtering on fields (`layout`, `keywords`, `type_line`, `oracle_text`, `legalities.commander`, `set_type`). Each pick was checked for the property it is here for. The one-off selection script is not part of the repo.
- To regenerate, re-select the same names from a newer bulk file. Card text, legality and printings may have changed.

### Data notes

- Every line, including tokens, art series and other non-game objects, has a top-level `oracle_id`. No `card_faces` entry carries its own `oracle_id`. This bulk file has no `reversible_card` layout.
- Art series entries are named `X // X` (for example `Sol Ring // Sol Ring`), so their front-face name collides with the real Card while having a different `oracle_id`.
- Friends forever and other `Partner—...` variants have the plain keyword `Partner` in `keywords`; only `oracle_text` tells them apart.
- `legalities.commander` is `banned` for ante and Conspiracy cards as well as for the Commander banned list.

### Cards

| Card Name | Category | Why it is here | layout | commander legality |
|---|---|---|---|---|
| Agadeem's Awakening // Agadeem, the Undercrypt | MDFC land | Spell front, land back | `modal_dfc` | `legal` |
| Emeria's Call // Emeria, Shattered Skyclave | MDFC land | Spell front, land back | `modal_dfc` | `legal` |
| Valakut Awakening // Valakut Stoneforge | MDFC land | Spell front, land back | `modal_dfc` | `legal` |
| Brightclimb Pathway // Grimclimb Pathway | Pathway land | modal_dfc with a land on both faces | `modal_dfc` | `legal` |
| Hengegate Pathway // Mistgate Pathway | Pathway land | modal_dfc with a land on both faces | `modal_dfc` | `legal` |
| Fire // Ice | Split card | Classic split card | `split` | `legal` |
| Cut // Ribbons | Split card (aftermath) | Aftermath split card | `split` | `legal` |
| Wear // Tear | Split card (fuse) | Fuse split card | `split` | `legal` |
| Polluted Delta | Fetchland | Fetchland; produces no mana itself | `normal` | `legal` |
| Prismatic Vista | Fetchland | Fetchland for basics | `normal` | `legal` |
| Fabled Passage | Fetchland | Fetchland for basics | `normal` | `legal` |
| Plains | Basic land | Basic land | `normal` | `legal` |
| Wastes | Basic land | Colorless basic; empty color identity | `normal` | `legal` |
| Snow-Covered Island | Snow basic | Snow basic land | `normal` | `legal` |
| Thrasios, Triton Hero | Partner | Plain Partner | `normal` | `legal` |
| Tymna the Weaver | Partner | Plain Partner | `normal` | `legal` |
| Pir, Imaginative Rascal | Partner with | Partner with Toothy | `normal` | `legal` |
| Toothy, Imaginary Friend | Partner with | Partner with Pir | `normal` | `legal` |
| Wilson, Refined Grizzly | Choose a Background | Commander that takes a Background | `normal` | `legal` |
| Raised by Giants | Background | Background enchantment | `normal` | `legal` |
| Faceless One | Choose a Background + Background | Both a Background and a Choose-a-Background creature | `normal` | `legal` |
| Cecily, Haunted Mage | Friends forever | Friends forever; Scryfall keyword is just 'Partner' | `normal` | `legal` |
| Bjorna, Nightfall Alchemist | Friends forever | Friends forever; pairs with Cecily | `normal` | `legal` |
| Kratos, Stoic Father | Partner variant | Partner—Father & son; keyword is just 'Partner' | `normal` | `legal` |
| Atreus, Impulsive Son | Partner variant | Partner—Father & son; pairs only with Kratos | `normal` | `legal` |
| Rose Tyler | Doctor's companion | Doctor's companion | `normal` | `legal` |
| The Tenth Doctor | Doctor | Doctor for a companion pair | `normal` | `legal` |
| The Fourteenth Doctor | Doctor | Doctor for a companion pair | `normal` | `legal` |
| Relentless Rats | Any number | Any number of copies allowed | `normal` | `legal` |
| Shadowborn Apostle | Any number | Any number of copies allowed | `normal` | `legal` |
| Persistent Petitioners | Any number | Any number of copies allowed | `normal` | `legal` |
| Seven Dwarves | Up to N | Up to seven copies | `normal` | `legal` |
| Nazgûl | Up to N + accented name | Up to nine copies; accented name | `normal` | `legal` |
| Black Lotus | Banned in Commander | Banned | `normal` | `banned` |
| Mana Crypt | Banned in Commander | Banned | `normal` | `banned` |
| Dockside Extortionist | Banned in Commander | Banned | `normal` | `banned` |
| Nadu, Winged Wisdom | Banned in Commander | Banned | `normal` | `banned` |
| Timmerian Fiends | Banned in Commander (ante) | Ante card; Scryfall marks it banned | `normal` | `banned` |
| Power Play | Banned in Commander (conspiracy) | Conspiracy; Scryfall marks it banned | `normal` | `banned` |
| Lim-Dûl's Vault | Accented name | u-circumflex in name | `normal` | `legal` |
| Jötun Grunt | Accented name | o-umlaut in name | `normal` | `legal` |
| Dandân | Accented name | a-circumflex in name | `normal` | `legal` |
| Ifh-Bíff Efreet | Accented name | i-acute in name | `normal` | `legal` |
| Delver of Secrets // Insectile Aberration | Transform | Transform DFC | `transform` | `legal` |
| Search for Azcanta // Azcanta, the Sunken Ruin | Transform (land back) | Transforms into a land; front face is not a land | `transform` | `legal` |
| Bonecrusher Giant // Stomp | Adventure | Adventure | `adventure` | `legal` |
| Lovestruck Beast // Heart's Desire | Adventure | Adventure | `adventure` | `legal` |
| Akki Lavarunner // Tok-Tok, Volcano Born | Flip | Flip card | `flip` | `legal` |
| Gisela, the Broken Blade | Meld | Meld half | `meld` | `legal` |
| Bruna, the Fading Light | Meld | Meld half | `meld` | `legal` |
| Brisela, Voice of Nightmares | Meld result | Meld result; not deckable on its own | `meld` | `legal` |
| History of Benalia | Saga | Saga | `saga` | `legal` |
| Druid Class | Class | Class | `class` | `legal` |
| Case of the Locked Hothouse | Case | Case | `case` | `legal` |
| Adventurous Eater // Have a Bite | Prepare | Newer two-face 'prepare' layout | `prepare` | `legal` |
| Gemrazer | Mutate | Mutate | `mutate` | `legal` |
| Student of Warfare | Leveler | Leveler | `leveler` | `legal` |
| Phyrexian Fleshgorger | Prototype | Prototype | `prototype` | `legal` |
| Sol Ring | Staple | Ordinary staple | `normal` | `legal` |
| Command Tower | Staple | Ordinary staple land | `normal` | `legal` |
| Arcane Signet | Staple | Ordinary staple | `normal` | `legal` |
| Cultivate | Staple | Ordinary staple | `normal` | `legal` |
| Atraxa, Praetors' Voice | Staple commander | Ordinary single commander | `normal` | `legal` |
| Sol Ring // Sol Ring | Non-game: art_series | art_series whose front name collides with Sol Ring; own oracle_id | `art_series` | `not_legal` |
| Tyranid | Non-game: token | layout token; loader should skip | `token` | `not_legal` |
| Demon | Non-game: token | layout token; loader should skip | `token` | `not_legal` |
| Foraging Squirrels // Foraging Squirrels (cont'd) | Non-game: double_faced_token | layout double_faced_token; loader should skip | `double_faced_token` | `not_legal` |
| Koth of the Hammer Emblem | Non-game: emblem | layout emblem; loader should skip | `emblem` | `not_legal` |
| Brightglass Gearhulk // Brightglass Gearhulk | Non-game: art_series | layout art_series; loader should skip | `art_series` | `not_legal` |
| Surprise! | Non-game: front_card | layout front_card (memorabilia); loader should skip | `front_card` | `not_legal` |
| The Great Aerie | Non-game: planar | Planechase plane; not a deck card | `planar` | `not_legal` |
| What's Yours Is Now Mine | Non-game: scheme | Archenemy scheme; not a deck card | `scheme` | `not_legal` |
| Titania | Non-game: vanguard | Vanguard; not a deck card | `vanguard` | `not_legal` |
| Phyrexian Broodstar | Not legal: Un-card | Un-set card, layout normal, commander not_legal | `normal` | `not_legal` |
| Mine Security | Not legal: Alchemy | Digital-only card, layout normal, commander not_legal | `normal` | `not_legal` |
