# Variant: Moo-d Board

## Design stance
Don't make users search by tag — let them search by *vibe*. The cow is the interface: mood faces, a Sacred Cow of the day, a heatmap of when the herd peaks, and streaks to keep them coming back.

## Key choices
- Layout: streak banner → Sacred Cow hero → mood row → heatmap → venue list
- Typography: system stack, playful but legible
- Color: existing tokens; gold Sacred Cow gradient with MOO-T APPROVED seal; heatmap cells in leather-brown intensity scale with a pulsing golden-hour cell
- Interaction: 5 mood buttons filter the list (Cheap Thrills→dive/pub, Date Night→classy/downtown, Rowdy→sports/western/dive, Chill→craft-beer/whiskey, Day Drinking→currently live); heatmap cells filter by half-hour; crowd moo-ter gauges (1–5 cows) on each card; streak banner

## Trade-offs
- Strong at: personality and fun; the heatmap is real math over the hours parser, so it's buildable today; habit-forming (streak, sacred cow)
- Weak at: less obvious "where do I go at 4:45pm" framing; mood→tag mapping needs curation and may feel arbitrary for some venues

## Best for
- The "I don't know what I want, just make it feel right" user; great second iteration layered on Deal-First
