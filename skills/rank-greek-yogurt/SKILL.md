---
name: rank-greek-yogurt
description: Rank Greek yogurt by $/g protein, calorie:protein ratio, and leucine-adjusted cost. Uses live Amazon prices via the amazon-product-data skill. Covers plain nonfat, lowfat, whole-milk, and flavored variants from major brands (Chobani, FAGE, 365 Whole Foods, Greek Gods). Compares Amazon Fresh and regular Amazon channels in one table.
---

# Greek yogurt ranker

Ranks Greek yogurt by the same three criteria as the other `rank-*` skills: unit cost ($/g protein), calorie:protein ratio, and leucine-adjusted cost.

Math, CLI, and output formatting live in `.claude-plugin/lib/ranking.py`. This skill is curated nutrition data + a thin wrapper.

The output table includes a **Channel** column (regular vs fresh) so a user can directly compare an Amazon Fresh listing against the regular-Amazon listing of the same brand. With `--zip <code>`, the pipeline searches both Amazon and the Fresh storefront and merges results.

## When to use

- Choose a Greek yogurt by cost, calorie efficiency, or muscle-building value.
- Compare plain vs flavored variants; nonfat vs whole milk; or one brand vs another.
- Decide whether an Amazon Fresh listing is a better deal than the regular-Amazon listing.

## When NOT to use

- The user wants taste, texture, or subjective reviews.
- The user wants drinkable yogurts, kefir, or non-Greek styles.
- The user wants powders, bars, or edamame — use the corresponding rank-* skill.

## How to use

### With Amazon Fresh comparison (recommended)

**Proactively ask the user:**

> Would you like to include Amazon Fresh availability and prices in the comparison? This requires a 5-digit US ZIP code so the scraper can set the delivery location.

- If yes → ask for the ZIP, then:
  ```bash
  uv run scripts/rank.py --search "greek yogurt" --zip 02139 \
    --nutrition references/nutrition_data.json
  ```
- If no:
  ```bash
  uv run scripts/rank.py --search "greek yogurt" \
    --nutrition references/nutrition_data.json
  ```

Either way, the table includes a `Channel` column — products are tagged `fresh` if they came from the Fresh storefront search and `regular` otherwise.

### Known-ASIN mode

```bash
uv run ../amazon-product-data/scripts/scrape.py B008U5OSTQ B006WBVSV6
uv run scripts/rank.py --prices /tmp/amzn/results.json \
  --nutrition references/nutrition_data.json
```

Re-sort with `--sort cal_protein` or `--sort leucine_adjusted`.

## Domain-specific schema notes

Shared schema documented in [CONTRIBUTING.md](../../CONTRIBUTING.md#add-a-product-to-a-rank--skill). A Greek-yogurt container is multi-serving — `servings_per_container` is the manufacturer's label count. This is typically 4 or 5 for a 32 oz tub depending on the brand: Chobani labels 4, FAGE labels 5 (smaller per-serving size).

Valid `type` values for this skill:

- `plain_nonfat` — 0% milkfat, no added sugar. Highest protein:calorie ratio.
- `plain_lowfat` — 2% milkfat
- `plain_whole_milk` — 5% milkfat
- `flavored_nonfat` — fruit / vanilla blends, often with added sugar
- `flavored_whole_milk` — sweetened, higher-calorie

All Greek yogurt is milk-protein-based — leucine fraction is ~9–9.5% of total protein. Use 1.4–1.7 g leucine per 14–18 g of protein per serving.

### Channel field

Each nutrition entry may carry a `"channel": "regular" | "fresh"` field. This defaults the row's Channel column when the ranker can't otherwise determine source (e.g. `--prices` mode without `--search`). At runtime, search-mode populates the channel from the search.py `source` tag, which overrides the database default.

### Fresh-specific ASINs

Amazon Fresh sometimes lists the same brand under a different ASIN than regular Amazon. To compare both side-by-side, add BOTH ASINs to `nutrition_data.json`:
- The regular-channel ASIN with `"channel": "regular"`
- The Fresh-channel ASIN with `"channel": "fresh"`

The ranker treats them as distinct products — both will appear in the table at their respective prices, letting the user pick.
