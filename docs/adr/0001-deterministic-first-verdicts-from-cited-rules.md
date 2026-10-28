# Counts and Verdicts come from code; the LLM only explains

Anything with a calculable answer (land counts, Color Sources, mana curve, legality) is computed by deterministic code from card data. Judgments like "too few lands" come from named, cited Rules in code, and every Verdict names its Rule. When an LLM is added (phase 2) it chooses which analyses to run and explains their output, but it never produces a Count or a Verdict itself. We chose this because LLMs guess plausibly but wrongly at arithmetic and card facts, while a Rule can be tested, cited and tuned.

## Consequences

- "Is X enough?" questions need a Rule before they can be answered. A missing Rule means the app says it has no Verdict; it does not let the LLM improvise one.
- Rule thresholds live in code with a citation (for example, Frank Karsten's Commander mana analysis), so changing one is a reviewed code change.
