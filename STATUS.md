# Status

Interface source phase (2026-10-17): Public methodology prototype; Specification 1 source candidate; no scientific, runtime or publication acceptance.

This interface candidate is not qualified or published. Existing source, host-binding,
scientific and operational holds remain in force. Empty platform declarations make
no portability claim; the operational-state field makes no live-state assertion.

The gate-tooling candidate adds shared exact-version Quarto selection for the
merge gate and report renderer, with explicit, prepared-local and PATH precedence
and fail-closed selection, plus a separately prepared pinned advisory-audit tool.
Its 2026-10-26 staged local gate passed 280 tests, dependency auditing, frozen-result
and evidence checks, wheel containment, and all site/report renders with the pinned
Quarto 1.10.18. Hosted CI, independent publication review and publication remain
separate pending steps; scientific inputs, results and authorization are unchanged.

- **Status:** Prototype — public methodology and verification code; repository-versioned, with no distributed release
- **Evidence:** Synthetic and representative examples, plus one confounded historical smoke summary — no admissible real-model comparison
- **Decision:** No promotion recommendation — the draft evidence contract recomputes `NOT_EVALUABLE`, meaning no scientific conclusion can be drawn from its evidence
- **Demonstrates:** Independent, fail-closed evaluation reporting on synthetic evidence
- **Does not demonstrate:** Performance of any real model
- **Relevant to:** Model testing, challenger evaluation, and model-risk review

## Readiness verdict

The audited baseline passes its current CI and exact-result checks. The evaluation system is not
ready for a powered scientific promotion decision or production use.

The 2026-09-14 maintenance pass verified Ruff 0.16.7, Quarto 1.10.18, 213 tests, exact-result checks, wheel containment, public-boundary validation, and all site/report renders. No merge, publication, real-model run, or scientific authorization occurred in that verification.

The 2026-10-14 local report-dependency repair updates the lock to JupyterLab 4.6.4,
notebook 7.6.3, and urllib3 2.8.0, and points the source links to the canonical
organization repository. The full merge gate passed with Python 3.13.15, uv 0.13.0,
Ruff 0.16.7, and Quarto 1.10.18: 213 tests, exact-result and frozen-evidence checks,
wheel containment, public-safe evidence validation, and site/report renders passed;
the dependency audit found no known vulnerabilities. Scientific inputs, results,
and authorization are unchanged. This is local validation, with no new CI,
deployment, publication, or real-model result claimed.

## Organization adoption candidate

The owner confirmed the Governed tier and provisional adoption of the Jefahnierocks
child-repo baseline 0.1.0. The only unmet rule is a producer-approved public-safe
host-contract binding. That binding remains unresolved; no private producer
identifier is published as a substitute.

On 2026-10-14 the owner separately approved Quarto 1.10.18 itself reading and
writing only its native macOS `~/Library/Caches/quarto` cache during source
validation. This narrow cache exception permits no agent browsing or cleanup,
`HOME` or global configuration change, host installation, credential access,
deployment or publication. Earlier successful rendering did not establish cache
confinement; the native path ignores `XDG_CACHE_HOME` on macOS. The declaration is
now explicit. This decision leaves the public-safe host binding unresolved and
supplies no runtime or scientific admission.

The source candidate pins Python 3.13.15, uv 0.13.0 and Gitleaks 8.30.1, retains the
existing Quarto and dependency locks, and adds index-path and native secret scans
to the canonical local/CI gate. Source security covers all reachable history and
separate staged/unstaged tracked changes, not ignored or unstaged untracked files.
It supplements the unchanged path-scoped evidence-publication scanners. The full local
merge gate passed with 238 tests, and independent review accepted the source
candidate. No new CI, publication, service admission, real-model evidence, or
scientific authorization is claimed.

## Verified now

| Item | Evidence | Status |
|---|---|---|
| Public site | Offline-freeze publication baseline `cdb4690`: Render run `29668338617` and Pages run `29668338608` passed | published |
| Core version | `pyproject.toml` and frozen core identify `0.2.0`; wheel containment is tested | repository-versioned, not distributed — the version names code in this repository, not a release anyone can install from a registry |
| Experimental calculations | Committed synthetic results regenerate byte-for-byte | decision input only — the numbers inform, but do not make, the pending method decision |
| Calibration SAP family | Separate E4, E1, and E2 candidate protocols incorporate the reviewed decisions; the content-free E4 construction contract and E2 exact leading-rule/base-grid manifest regenerate byte-for-byte | not preregistered; no observations authorized; no corpus, grader result, operating-characteristic result, or scientific verdict exists |
| Contract B v2 draft | Exact schema, verifier, renderer, safety scanner, fixture, report, and delivery manifest are digest-bound (every implementation byte is hash-pinned) | synthetic conformance only — the draft evidence contract is validated against invented data, not real campaigns |
| Independent refusal | The public verifier derives `NOT_EVALUABLE` from the synthetic fixture and rejects mutations — it recomputes the result from frozen evidence bytes and refuses any altered copy | verified for the fixture |
| Publication scanning | Evidence inputs are recursively scanned in the parameterized report path; Contract B checks its bound public payload separately | path-scoped; no whole-repository scan — leak scanning covers the report inputs, not every file in the repository |

There is no Git tag, GitHub release, or package-registry publication for version `0.2.0`. “Version”
therefore identifies repository and wheel metadata, not a distributed release.

## Not ready

| Requirement | Current gap |
|---|---|
| Scientific design | E2 now has a frozen equal-class estimand and leading exact-rule candidate for calibration, but no enforcing test has been admitted or selected for a powered campaign; the replicate policy and minimum practically important benefit also remain undecided |
| Operating characteristics | Type I error (how often the rule would be wrong), power (how often it would detect a real difference), dependence sensitivity, and feasibility are not established for the intended design |
| Measurement validity | Grader validation, protected-task policy, and governed task selection are incomplete — the scoring instrument itself is not yet validated |
| Operational provenance | Registration signing/timestamp verification and runtime owner receipts are not operational — runtime evidence is not yet signed and independently verified in production |
| Calibration | No accepted grader study, A/A session-position invariance study, or rule-calibration study exists — nothing yet shows the measurement apparatus is quiet and consistent enough to trust |
| Real result | No powered, registered, scientifically admissible model comparison has been published |
| Historical smoke reproducibility | Only summary statistics are public; raw per-attempt outcomes required to recompute the interval are absent — outside readers cannot independently re-derive it |
| Publication enforcement | Active no-bypass ruleset `18954954` requires pull requests, signed commits, linear history, resolved review threads, and the strict `Render public evidence reports` check; approval count is zero under the disclosed solo-maintainer model | protected, but not independent review |

## Claim policy

Current public artifacts support claims about software structure, exact-byte verification, synthetic
recomputation, and explicit refusal behavior. They do not support claims that:

- one model or harness is better than another;
- the historical bootstrap rule has validated error control for the intended design;
- identity-domain equality alone establishes reproducibility;
- Contract B v2 is an accepted or operational evidence contract; or
- the end-to-end private system is production-ready.

## Path to a first admissible result

1. Accept a scientific analysis plan and publish the corresponding versioned method contract.
2. Complete owner-issued runtime observations and operational registration verification.
3. Freeze the grader, task-selection record, task suite, assignment, retry, and attrition policies.
4. Run and review grader validation, A/A session-position invariance calibration, and operating-
   characteristic analysis.
5. Register and execute the first powered local comparison.
6. Independently recompute, sanitize, review, and publish the result, including a no-go or
   `NOT_EVALUABLE` outcome if that is what the evidence supports.

Remote GPU evaluation is a separate later baseline. It must not inherit local-lane validity by
convention.

## Known errata

The frozen identity-domain v1 module docstring overstates what hash equality establishes. The
versioned interpretation correction is recorded in [ERRATA.md](ERRATA.md); frozen v1 bytes and the
conformance vector are unchanged.

## Provenance

- Status date: 2026-10-14
- Baseline reviewed for this local repair: `d8cb7820e24d7d46b9f890c0093906ea259ef714`
