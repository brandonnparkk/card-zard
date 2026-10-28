# Share Links store the Deck List and re-run the Analysis

A Share Link stores the submitted Deck List (and the Snapshot it was first analyzed against), not a frozen copy of the Analysis. Opening the link re-runs the Analysis against the current Snapshot and Rules. We chose this because analysis is cheap to compute, stored results would need migrating every time the Analysis shape changes, and users benefit from improved Rules and fresh card data. A shared link can therefore show different Verdicts over time; storing the original Snapshot means we can explain why.
