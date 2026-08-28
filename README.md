# CalcuGrid Open Data

Seven datasets that were surprisingly hard to find in machine-readable form, so they got assembled, unit-checked and audited. Published under **CC BY 4.0** — use them for anything, just say where they came from.

Every file is plain CSV and JSON. No API, no key, no signup. Clone it or link the raw file.

```bash
git clone https://github.com/bigfe-efe/calcugrid-open-data.git
```

---

## What's here

| Dataset | Rows | Files |
|---|---:|---|
| AKC dog breed standards | 274 breeds | `dog-breed-standards.csv` · `.json` |
| US state income tax, TY2026 | 51 jurisdictions | `us-state-income-tax-2026.csv` · `.json` |
| — state tax brackets | 461 brackets | `us-state-tax-brackets-2026.csv` |
| — state payroll taxes | 19 taxes | `us-state-payroll-taxes-2026.csv` |
| National grading scales | 56 countries | `grading-scales.csv` · `.json` |
| — grade bands | 333 bands | `grading-scale-bands.csv` |
| GPU power specifications | 34 cards | `gpu-power-specs.csv` |
| EV efficiency | 50 vehicles | `ev-efficiency.csv` |
| US residential electricity rates | 51 states | `us-electricity-rates.csv` |
| 1099 vs W-2 tax, by state | 51 states | `us-1099-vs-w2-by-state.csv` · `.json` |

`manifest.json` lists every file with row counts and the generation date.

---

## Read this before using any of it

Each dataset has one thing that will bite you if you assume the obvious. They are listed here rather than buried, because every one of these caused a real bug during the work that produced them.

### Dog breed standards — the units are metric

**Weights are kilograms. Heights are centimetres.** Reading them as pounds and inches overstates every figure by a factor of 2.2, and nothing downstream will complain. Spot-check against the published AKC standard: Akita 32–59 kg (70–130 lb), Afghan Hound 63.5–68.6 cm (25–27 in).

**Thirteen breeds have `min_kg == max_kg`.** That is not a data error. Some AKC standards state a single figure or a ceiling — "not to exceed 28 pounds" for the French Bulldog — rather than a range. Handle the zero-width case or you will print `12.7–12.7 kg`.

A breed standard describes the breed, not the individual animal. A dog at the bottom of its range is not underweight.

The calorie column uses the standard allometric formula, `RER kcal/day = 70 × kg^0.75`, multiplied by 1.6 for a neutered adult. Life-stage factors are in `dog-breed-standards.json`. It is a starting point a vet adjusts, not a prescription.

### National grading scales — there is no official conversion

This is the most important caveat in the repository.

**`us_letter_convention` and `us_gpa_convention` are a convention, not an answer.** WES, Scholaro, ECE and individual university admissions offices publish tables that disagree with each other, most sharply at the top of each scale — which is exactly where an application is decided. Anyone presenting a single figure as *the* conversion is overstating what exists.

**`local_classification` is the reliable field.** "First-Class Honours", "2:1", "sehr gut", "Notable" are printed on the transcript and mean something precise in their own system.

**Four scales are inverted** — `higher_is_better = false`. On these, the *lowest* number is the best grade:

- Germany (1.0 best, 5.0 fail)
- Austria (1 best, 5 fail)
- Czechia (1 best, 4 fail)
- Philippines (1.00 best, 5.00 fail)

A German 1.3 or a Filipino 1.25 is excellent work. Reading either as a US GPA turns a top student into a failing one. Check the flag.

**Band intervals are contiguous, not the printed bounds.** `grade_from`/`grade_to` are written the way a human reads them (60 to 69.99, then 70 to 100). When matching a grade, treat each band as running up to where the next one starts — otherwise a grade of 69.995 falls in no band at all.

### 1099 vs W-2 by state — computed, not observed

**This one is derived data.** Every other file here records something published;
this one applies the published TY2026 rules to a worked example. The distinction
matters: change an assumption and the numbers change.

The assumptions, all stated in the JSON: $100,000 of net business profit, sole
proprietor filing Schedule C, single, no employees, no qualified property, no
other income, no retirement contribution.

**`tax_difference_usd` is negative in California**, and that is not an error.
State disability and paid-family-leave payroll taxes are charged to employees and
not to sole proprietors. California's SDI is 1.3% with no wage ceiling, which is
enough to reverse the federal difference — a contractor there pays about $412
less tax than an employee on the same $100,000.

**`break_even_contract_usd` prices tax only.** It is the contract value leaving
the same money after tax as a $100,000 salary. It buys no health insurance, no
paid leave, no employer retirement match, and covers no unpaid weeks between
contracts. Treat it as a floor, not a target.

The Section 199A figure behind it assumes no W-2 wages paid, so above the
threshold the deduction ramps to zero. A business that pays wages keeps more.

### US state income tax — state level only

Brackets, standard deductions and state payroll taxes for **tax year 2026**. Federal brackets, FICA and city/county taxes are **not** included — those are applied separately.

`system` is `progressive`, `flat` or `none`. Nine states have no wage income tax. `income_to_usd` is `null` on the top bracket, which is unbounded.

Rates change. Check the `generatedAt` field before relying on this for anything real, and check your state's own revenue department for the current year.

### GPU power — TGP is a ceiling, not an average

`total_graphics_power_w` is the manufacturer's limit. A real game at a real frame rate sits below it. Multiplying TGP by hours to estimate energy use overstates it by a wide margin; apply a load factor.

`recommended_psu_w` is the vendor recommendation, which deliberately leaves headroom for transient spikes above the rated limit.

### EV efficiency — EPA figures

`kwh_per_100_miles` and `epa_range_miles` are EPA test-cycle figures. Real-world consumption varies with temperature, speed and terrain, usually worse in winter.

`usable_battery_kwh` is derived, not a nameplate capacity.

---

## Sources

| Dataset | Source |
|---|---|
| Dog breeds | American Kennel Club breed standards |
| Dog energy formula | Merck Veterinary Manual, small-animal nutritional requirements |
| State income tax | State revenue department publications, TY2026 |
| Grading scales | National qualifications frameworks and ministry of education grading regulations |
| US GPA convention | The mapping common to US credential evaluation |
| GPU specs | Manufacturer specification pages (NVIDIA, AMD) |
| EV efficiency | US EPA fuel economy data |
| Electricity rates | US EIA residential average |
| 1099 vs W-2 comparison | Computed from the above, plus IRC 1401-1402, Rev. Proc. 2025-32 and the One Big Beautiful Bill Act |

Per-row source strings are in the CSVs where they differ by row (`gpu-power-specs.csv`) and in the JSON `source` field per state (`us-state-income-tax-2026.json`).

---

## How this was checked

These files are exported from the data layer of [calcugrid.com](https://calcugrid.com), where they pass an audit on every build. The audits are domain-specific rather than schema checks:

- **Units** are range-checked against physical plausibility, which is what caught the kilogram/pound question
- **Monotonicity** — a bigger dog must need more calories; a better grade must never produce a lower GPA
- **Coverage** — grade bands must tile their whole scale with no gaps, which caught 0.01-wide holes in six countries where a grade matched nothing and scored zero
- **Direction** — every inverted scale is verified to actually run in the direction it declares
- **Cross-implementation parity** — each calculation exists as a Python reference and a TypeScript port, held to each other by golden fixtures

None of that makes the data correct. It makes a whole class of silent errors loud.

---

## Corrections

If you find something wrong, please open an issue with the source you are checking against. Corrections to the underlying data are more useful than almost anything else you could contribute.

---

## Licence

[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0). See `LICENSE`.

You may share and adapt this for any purpose, including commercially. The only condition is attribution:

> Data from [CalcuGrid](https://calcugrid.com), CC BY 4.0

The underlying facts — a breed standard, a tax rate, a grading scale — are not copyrightable and you may use them freely regardless. The licence covers this particular compilation.
