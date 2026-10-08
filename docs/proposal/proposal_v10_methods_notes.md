# Methods notes for proposal version 10

These notes explain the analysis and evaluation in `docs/proposal/proposal_v10.md` in plain terms, with quick examples. The proposal has room for about one sentence per method, so the rest lives here, for the team and for questions in class. Numbers marked *made up* only illustrate a method. They are not results. Citations in brackets use the proposal's reference numbers.

## 1. The analysis, step by step

1. **Score each segment.** A segment is one awarding agency, one product code and one fiscal year. We compute its HHI and its top-4 share. In DoD's fixed-wing aircraft purchases for FY2025, the largest vendor held 76%, so that vendor alone puts the HHI at 76 × 76 = 5,776 or more.
2. **Form trend lines.** One agency and one product code, scored in every year from FY2008 to FY2025, give a line of up to 18 points. There are thousands of these lines.
3. **Sort the lines into shapes, for question 2.** k-means clustering finds a handful of typical shapes and puts each line with the one it most resembles. Typical shapes might look like these *made-up* ones.
   - Flat near 1,500.
   - A steady climb from 1,200 to 4,000.
   - Flat at 2,000, then a jump to 6,000 in FY2015 that stays.
   - One spike that falls back.
4. **Compare shapes regardless of height.** Each line is centered and scaled first. A line that goes from 1,000 to 2,000 and one that goes from 5,000 to 6,000 then both count as a climb. Scaling also stretches a nearly flat line with small wiggles until it looks like a big swing. The thin-line rule removes some of these. Clustering on the change from the first year is the alternative.
5. **Pick the number of shapes.** We try 2 to 10 shapes. For each number, the average silhouette width scores whether every line sits clearly closer to its own shape than to the next closest one. The score runs from −1 to 1, and we keep the number of shapes with the best score.
6. **Set aside thin lines.** A product an agency bought in only 3 years, or for $50K in all, is mostly noise. The rule must be fixed before any clustering run, and its numbers are not chosen yet. A line also needs at least 6 years for the rising rule, so its first 3 and last 3 years do not overlap.
7. **Label rising lines, for question 3.** Section 2 gives the rule.
8. **Find what rising lines have in common.** Sections 3 and 4 explain the features and the two models.

## 2. What "rising" means

Rising means concentration went up over time. More of an agency's money for a product ended up with fewer vendors. It measures how the money is split. Total spending can double while concentration stays flat.

The example from our pitch works over time too. In FY2008 an agency splits $100M on a product evenly across five vendors, so the HHI is 2,000. By FY2025 one vendor gets $80M and the other four get $5M each, so the HHI is 6,500. The line rose from 2,000 to 6,500. In plain words, the agency came to rely on one vendor.

**The rule in version 10.** A line is rising if its average HHI over its last 3 years is at least 500 points above its average over its first 3 years. The analysis is repeated with cutoffs of 250 and 1,000 points. Yearly scores bounce around, and averaging over 3 years softens the effect of one large award.

| Line (*made up*) | First 3 years, average | Last 3 years, average | Rising? |
|---|---|---|---|
| A | 2,000 | 6,500 | Yes. A large, lasting climb. |
| B | 3,000 | 3,100 | No. A rise of 100 points is below the cutoff. |
| C | 5,000 | 2,500 | No. Concentration fell. |
| D | 2,000 | 2,000 | No. Its one spike, 8,000 in FY2016, falls in the middle years and fades. |

**The 500-point cutoff is a judgment call.** No source fixes the number. We have not yet measured how much lines bounce from year to year, and that spread is a good guide for setting it. The 2023 merger guidelines call a change of more than 100 points a significant increase [17], but that figure judges the effect of one merger, and our lines also move with lumpy awards. The team can change the cutoff before the first run and should then leave it fixed. The runs at 250 and 1,000 points show whether the answer depends on it.

**Two other rules we considered.**
1. **Band rule.** A line is rising if it moved up a band under the 2010 guidelines [18]. HHI below 1,500 is unconcentrated, 1,500 to 2,500 is moderately concentrated, and above 2,500 is highly concentrated. The bands have a source, but the rule misses large rises inside a band, such as 3,000 to 9,000.
2. **Shape rule.** A line is rising if the clustering put it in a shape that goes up. The definition would change whenever the number of shapes changes, and it is hard to explain in one sentence. It also ties question 3 to how the clustering turns out.

## 3. Sole-source share

Sole-source share is the percentage of a line's dollars that went out without competition, meaning the agency picked one vendor directly and no other firm could bid. An agency that spends $100M on a product in a year, $60M of it on contracts nobody else could bid on, has a sole-source share of 60%. It matters for the reason in our pitch. With one bidder there is nothing to negotiate against.

Agencies may skip competition for reasons the rules allow. Only one firm can do the work, the need is urgent, the work follows on from an earlier contract, or a law directs the work to a program.

**The source field.** Every transaction has a field called `extent_competed_code`. The codes below come from our column guide and should be checked against the FPDS data dictionary before we rely on them.
- **Competed.** A (full and open), D (full and open after excluding some sources, such as a small business set-aside), F (competed under simplified procedures) and CDO (competitive delivery order).
- **Not competed.** B (not available for competition), C (not competed), G (not competed under simplified procedures) and NDO (non-competitive delivery order).
- **Unclear.** E (follow-on to a competed action).

The share is the dollars on not-competed rows divided by all of the line's dollars. Deobligations count as negative dollars here too, so a line with large reversals can show a share below 0% or above 100%. The team should cap or flag those lines.

**Three complications.**
1. **Follow-ons, code E.** The original contract was competed, but the follow-on went to the same firm without a new competition. It could count either way. Counting it both ways, as a robustness run, is the simplest answer.
2. **Orders under umbrella contracts.** These are the pitch's "twenty firms win a slot" deals. Our column guide says `extent_competed` describes how the umbrella was competed, and `fair_opportunity_limited_sources` records whether each order was competed among the holders. The guide flags this as unconfirmed. Should it hold, a $50M order handed straight to one holder can still show as competed. Version 10 measures the share both ways, for the umbrella and for the order, as the pitch planned.
3. **Competed with only one offer.** An award can be competed on paper and still draw a single offer. Hyatt [7] counts that as competition that was not effective. Offers received is coded consistently only from FY2012 to FY2017, so for now this feature covers those years alone. The team will look for another source that could fill the other years.

## 4. The two models for question 3

Each line gets a yes or no for rising, by the rule in section 2. Each line also becomes one row of features, measured over its first 3 years, before any rise.

| Line (*made up*) | Sole-source share | Mostly fixed-price? | Kind | Vendors at start | Rising? |
|---|---|---|---|---|---|
| Aircraft parts | 60% | No | Product | 40 | Yes |
| IT help desk | 10% | Yes | Service | 120 | No |
| Lab research | 55% | No | Research | 8 | Yes |

The kind comes from the product code. Codes that start with a digit are products, codes that start with A are research, and codes that start with any other letter are services. The other features are the share placed through contract vehicles, the share set aside for small business and the line's size. The vendor count is the starting count. A falling count raises HHI by itself, so the change in vendor count would partly predict the answer with itself.

**Logistic regression with an L1 penalty.** It gives each feature a number for how much it raises or lowers the odds that a line is rising, holding the other features fixed. The penalty pushes weak features to exactly zero, so the result is a short list. A *made-up* output might read, "10 more points of sole-source share goes with 1.3 times the odds of rising. Set-aside share and size dropped out."
- The model is log-odds of rising = b₀ + b₁ × (sole-source share) + b₂ × (fixed-price share) + and so on.
- The L1 penalty adds λ × Σ|bᵢ| to the loss. A larger λ zeroes out more features, and cross-validation picks λ.
- Features are standardized first, so the penalty treats them equally.
- A coefficient becomes an odds ratio through exp(b). In the made-up example, b = 0.26 per 10 points gives e^0.26 ≈ 1.30.
- Features that overlap, such as sole-source share and vendor count, can make L1 keep one and drop the other somewhat arbitrarily. Which features survive should be checked across resamples.

**Shallow decision tree.** It is a flowchart of 2 or 3 yes or no questions, each chosen by the computer to best separate rising lines from the rest. A *made-up* tree might read like this.
- Is the sole-source share above 40%? No leads to 15% of lines rising.
- Yes leads to a second question. Is it research? Yes leads to 70% rising, and no leads to 45% rising.

It is a standard classification tree (CART). Each split is chosen to make the two branches as pure as possible, and a depth limit of 2 to 3 with a minimum branch size keeps it from memorizing noise.

**Why both.** The regression gives the size of each feature's effect. The tree catches combinations, such as sole-source awards mattering mostly for research. Both pointing at the same features is more convincing than either alone.

**Better than nothing.** Both models must predict rising better than a baseline that knows only the agency and the line's size. The gain in AUC must be at least 0.05, about 5 more pairs ranked correctly out of every 100, so the gain is large enough to matter. Its 95% bootstrap interval must also stay above zero, so the gain is not luck. With thousands of lines even a tiny gain can pass a test of luck alone, which is why the rule needs both parts. A failure is still a result. The honest answer to question 3 would then be that nothing beyond agency and size stands out.

**What the models cannot say.** They find what goes together. Suppose sole-source awards go with rising lines. Sole-sourcing could push purchases toward one vendor. A vendor that already dominates could also win sole-source follow-on work because no one else can do it. Both stories fit the same numbers, which is why the proposal claims no causes.

## 5. The evaluation checks, with examples

| Check | In plain terms | Example |
|---|---|---|
| Totals | Our yearly totals must match GAO's within 2% in every year GAO reports one | FY2025 is ours against GAO's $793 billion, a gap of +0.02%, which passes. GAO gives exact figures only for FY2022 to FY2025. |
| Data decisions | Rerun with each alternative choice on the nine open decisions | Count negative vendor totals as zero in place of keeping them. Fixed-wing aircraft should still rise, and we report how many segments change band. |
| Robustness | The pattern must survive other ways of measuring | Use top-4 share in place of HHI, code group 15 (aircraft) in place of 1510, a start in FY2012, and 3-year windows so one large award cannot fake a jump. |
| Clusters | The shapes must be real and stable | A silhouette width of at least 0.25 means the groups are distinct. Resample the lines 100 times and sort them again. The groupings must agree, with a mean adjusted Rand index of at least 0.6, where 1 means identical and 0 means chance. |
| Descriptive models | The features must predict rising better than agency and size alone | Hide a fifth of the lines, train on the rest, predict the hidden fifth, and repeat 5 times. AUC is the chance that a rising line outscores a line that did not rise, and 0.5 is a coin flip. The gain must be at least 0.05, and its 95% bootstrap interval must stay above zero. A *made-up* baseline of 0.62 against our 0.71 passes, and our 0.63 would fail. |
| Face validity | Known cases should come out right | Aircraft carriers come from one shipyard, so that purchase should score near the top. |

## 6. Decisions still open for the team

1. **The 500-point cutoff for rising.** Version 10 proposes it. The team can change it before the first run.
2. **Code E, follow-ons to a competed action.** Count it as competed, as not competed, or both ways.
3. **The umbrella-order field.** Confirm in the FPDS data dictionary what `extent_competed` and `fair_opportunity_limited_sources` record for orders.
4. **Sole-source shares outside 0% to 100%.** Cap them or flag the lines.
5. **The thin-line rule.** Fix the minimum years and dollars before any clustering run.
6. **Scaling the lines.** Keep centering and scaling, or cluster on the change from the first year.
7. **The methods and thresholds.** k-means, silhouette width of 0.25, adjusted Rand index of 0.6, the L1 regression and the tree are proposed. The team will fix them before the first run. The AUC rule, a gain of at least 0.05 with a 95% interval above zero, is agreed.
8. **The price index** for charts in constant FY2025 dollars.
9. **The word "segment"** for one agency, product code and year. Alternatives are "market" and "agency-product-year".
10. **Another source for offers received.** FY2012 to FY2017 is the window for now. The team will look for data that could fill the other years.
