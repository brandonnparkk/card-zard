# Cards are identified by Oracle ID; Printings are ignored

A Deck Line like `1 Sol Ring (C21) 263` resolves to the Card _Sol Ring_ by Oracle ID, and the set code and collector number are dropped. Every planned analysis is about what a card does, not which Printing it is. Printing-level features (prices, specific art) would need Scryfall's larger `default_cards` file and a schema change, so that is deferred on purpose.
