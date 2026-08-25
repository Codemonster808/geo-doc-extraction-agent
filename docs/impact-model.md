# Impact model — assumptions

| # | Assumption | Value used | Source (fill in before publishing) |
|---|---|---|---|
| 1 | Geologist hours spent manually transcribing one report | TODO | TODO |
| 2 | Reports processed per month by a mid-size exploration team | TODO | TODO |
| 3 | Fully loaded geologist hourly cost | TODO | TODO |
| 4 | % of manual transcription time replaced by the agent (accounting for review of low-confidence extractions) | TODO | TODO |

## Calculation

```
hours_saved_per_month = reports_per_month * manual_hours_per_report * replacement_pct
value_per_month          = hours_saved_per_month * hourly_cost
value_per_year            = value_per_month * 12
```

## Rule for this file

Never change the README's "Modeled business impact" number without updating this file in the same commit.
