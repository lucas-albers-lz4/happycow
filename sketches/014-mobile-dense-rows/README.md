# Variant: Dense venue rows (iteration on 013)

## Design stance
Same mobile deal-first shell as [013](../013-mobile-deal-first/) / issue #85 — iterate the **venue information format**: condense, organize, left-align to reclaim width.

## Row format (left-stacked)

```
Name                              18m     ← status as compact right time
Deal / special                            ← spot color, one line ellipsis
4:30–5:30pm · Downtown                    ← hours · place
```

- Dropped the `›` chevron column (pure left scan)
- Status is a short time (`18m` / `40m` / `—`), not a wordy label inline with the name
- Left border accent: green live / gold soon / grey closed
- Deal sits on its own line so name + special don't fight for the same run of text
- Pin card also left-stacked (name + time on one row; no floating badge/emoji)

## vs 013

| | 013 | 014 |
|---|---|---|
| Primary line | `Name — special` + chevron | `Name` + compact time |
| Deal | Inline with name | Own line (clearer hierarchy) |
| Meta | `hours · area · live` | `hours · area` (status already on L1) |
| Width | Chevron steals ~24px | Full width for copy |

## Verification
Compare side-by-side with 013 in the gallery (Wave D). Scan the list: more venues visible, deals readable, no right-column waste.
