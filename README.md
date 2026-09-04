# CalcuGrid Open Data

Nine datasets that were surprisingly hard to find in machine-readable form, so they got assembled, unit-checked and audited. Published under **CC BY 4.0** — use them for anything, just say where they came from.

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
| LLM model architectures | 20 models | `llm-model-architectures.csv` |
| — memory by quantisation | 120 rows | `llm-vram-by-quantisation.csv` |
| — accelerators | 30 devices | `llm-accelerators.csv` |
| — model × accelerator fit | 600 rows | `llm-model-accelerator-fit.csv` |
| — everything, with caveats | — | `llm-vram.json` |
| Desktop CPU power limits | 26 CPUs | `pc-cpu-power-specs.csv` |
| Desktop GPU power limits | 34 cards | `pc-gpu-power-specs.csv` |
| PSU sizing by build | 884 pairings | `pc-psu-sizing-by-build.csv` |
| — method and caveats | — | `pc-psu-sizing.json` |

`manifest.json` lists every file with row counts and the generation date.

The four LLM tables are also published as a dataset on the Hugging Face Hub, with a browsable data viewer:
[huggingface.co/datasets/BigFe/llm-vram-requirements](https://huggingface.co/datasets/BigFe/llm-vram-requirements)

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

### LLM architectures and VRAM — the head_dim trap

**`parameters` is computed, not copied.** Derived from the architecture rather
than taken from the model's name, so a transcription error in any config field
shows up immediately as a model that is the wrong size. Compare `parameters_b`
against `stated_size_b` — all twenty agree within 0.2%, which is the check
that the architecture fields are right.

**`head_dim` is read from the config, never derived.** It is tempting to
compute it as `hidden_size / attention_heads`. That is wrong for Gemma 2, which
sets 256 where the division gives 224 — deriving it understates the KV cache by
14% on those models.

**Size the cache by `key_value_heads`, not `attention_heads`.** Grouped-query
attention shares one key-value pair across several query heads. The `gqa_ratio`
column is how much that saves: up to 16× in this dataset. Using the query head
count is the commonest error in VRAM estimates and produces the wildly
pessimistic numbers people quote.

```
kv_cache_bytes = 2 × layers × key_value_heads × head_dim × context × bytes
weights_bytes  = parameters × bits_per_weight / 8
```

**Mixture-of-experts models publish two parameter counts.** `parameters_b` is
what gets loaded; `active_parameters_b` is what each token is routed through.
Memory follows the first, throughput follows the second, and they point at
different hardware — Qwen3 30B-A3B occupies 30.5B of weights and computes like
a 3.35B model. `num_experts` and `experts_per_token` are 0 on a dense model,
where the two parameter columns are equal, so code that reads either column
works on both kinds.

**Sliding-window attention is not modelled.** Gemma 2 alternates local and
global attention layers, so its real cache at long context is smaller than
shown. Those figures are an upper bound. Modelling it means knowing exactly
which layers use the window, and getting that fraction wrong would be worse
than not claiming it.

**GGUF K-quants are not their nominal bit width.** Q4_K_M averages about 4.5
bits per weight once block scales and higher-precision attention tensors are
counted, so files run roughly 12% larger than "4-bit" implies. The
`bits_per_weight` column carries the effective figure.

**`assumed_usable_gb` is an assumption, not a measurement.** Discrete cards are
assumed to keep 8% back for driver and display; Apple Silicon follows the
documented macOS cap on what one process may take. Your mileage will differ
with the runtime, batch size and what else is on the device — which is why the
fit table reports `tight` above 95% of usable memory rather than `yes`.

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

### PSU sizing — TDP is not a power limit

This is the trap the dataset exists to document, and it is the same shape as
the `head_dim` one above: a published number that looks like the right input
and is not.

A CPU's TDP is a thermal design figure. It is not what the chip is allowed to
draw. AMD permits 1.35× the rated TDP as Package Power Tracking; Intel
publishes Maximum Turbo Power as a separate number entirely. Both are on the
manufacturer's own spec sheet. Neither is the number most calculators use.

The `pc-cpu-power-specs.csv` columns put them side by side:

```
name                 tdp_watts   peak_watts   ratio
Core i9-14900K             125          253    2.02
Core Ultra 9 285K          125          250    2.00
Ryzen 9 9950X              170          230    1.35
```

`pc-psu-sizing-by-build.csv` carries what that costs. For each of the 884
CPU × GPU pairings, `recommended_from_tdp_watts` is the supply you would buy
having summed TDPs, and `computed_psu_watts` is the one the real ceilings ask
for. `sizes_missed_by_tdp` counts the standard supply sizes between them:

```
sizes missed    pairings
      0            157   (18%)
     +1            433   (49%)
     +2            128   (14%)
     +3            144   (16%)
     +4             22    (2%)
```

In 727 of 884 combinations — 82% — sizing on TDP selects a supply that is too
small. Use `peak_watts`.

Two caveats on the sizing itself. These are computed ceilings, not wall-meter
readings: a real system spends almost all its time well below the sum, which
is the point, because a supply is chosen for the worst case rather than the
average. And `recommended_psu_watts` is the larger of our arithmetic and the
GPU vendor's own recommendation — `binding_constraint` records which of the
two decided each row, so you can drop the vendor floor if you would rather
size purely on the numbers.

Board makers ship power profiles that raise these limits further. The Core
Ultra 9 285K has a 295 W extreme profile some boards enable by default; where
that applies the `note` column says so.

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
| LLM architectures | Each model's own `config.json` on Hugging Face. Meta gates its repositories, so those were read from public mirrors hosting the file unmodified — the computed parameter counts landing on the published sizes is the check that the mirrors are faithful |
| Accelerator memory | Manufacturer specifications |
| CPU power limits | Manufacturer specifications: AMD Package Power Tracking, Intel Maximum Turbo Power |
| PSU sizing | Computed from the CPU and GPU tables plus a fixed platform allowance; standard supply sizes as sold |

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
