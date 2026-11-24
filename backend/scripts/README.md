# Sensitivity analysis (`backend/scripts/`)

The sensitivity script checks whether changing the weekly heatmap's event
point weights changes the risk-level colours assigned to sample weeks. It
uses the sample deadlines in `samples/deadlines.json` at the repository root.

## Run it

From the `backend/` directory:

```powershell
python -m scripts.sensitivity
```

The script prints the number of sample deadlines and weeks, then compares each
week's baseline level with levels calculated after:

- Scaling all event-type point weights by `0.8` and `1.2`.
- Scaling exam, project, quiz, or assignment points individually by `0.8` and
  `1.2`.

It reports how many weeks change level for each adjustment. It compares
colours only; it does not report score differences or recalculate collision
rules. The script restores the original heatmap weights after each
calculation.

## Current sample results

With the current 20 deadlines across 10 weeks, the output reports:

| Adjustment | Weeks with a changed level |
|---|---:|
| All points × 0.8 | 1 of 10 |
| All points × 1.2 | 1 of 10 |
| Exam × 0.8 | 0 of 10 |
| Exam × 1.2 | 1 of 10 |
| Project × 0.8 or × 1.2 | 0 of 10 |
| Quiz × 0.8 or × 1.2 | 0 of 10 |
| Assignment × 0.8 or × 1.2 | 0 of 10 |

These are results for the current sample file; rerun the script after changing
the sample deadlines or heatmap weights to get updated results.

The analytics API and scoring thresholds are documented in
[`backend/analytics/README.md`](../analytics/README.md).
