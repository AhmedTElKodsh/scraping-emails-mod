# Apollo-Compliant Data Acquisition Plan

## Summary

Build a compliant lead acquisition workbench around Apollo and cheaper/free sources instead of scraping the logged-in Apollo app. The winning strategy is to maximize permitted sources over days/weeks: existing public-directory data, user-owned CSVs, Apollo's official API and exports, low-cost email finder/verification vendors, and selective paid enrichment only after scoring and dedupe.

This plan intentionally excludes IP-block evasion, fake-account rotation, CAPTCHA bypass, hidden endpoint scraping, automated scraping of logged-in Apollo pages, and any attempt to bypass credits, rate limits, export limits, or account limits.

Current repo fit:

- Existing YellowPages pipeline already stores business/contact data in SQLite and exposes Streamlit filtering.
- `src/scraper/sites/apollo_public.py` is a low-yield public-page POC and should not become an app-scraping path.
- The new work should add a source-agnostic acquisition layer, not replace the working YellowPages flow.
- Implementation starts in a separate acquisition database and separate Streamlit UI. The schema keeps normalized business, people, contact, source, confidence, and provenance fields so data can be merged into the main results database later when the Apollo plan is stable.

## Research Findings

Apollo constraints and official paths:

- Apollo's Terms prohibit automated bots/crawlers/data scraping to access or extract platform data unless it is expressly included in the platform or approved in writing by Apollo. They also prohibit measures intended to circumvent credits, authorized users, rate limits, or usage limits.
- Apollo's People API Search endpoint is official, does not consume credits, and does not return email addresses or phone numbers. It requires a master API key and has a 50,000-record display limit via 100 records per page, up to 500 pages.
- Apollo API pricing docs say Organization Search, Organization Job Postings, Complete Organization Info, News Articles, Person Details, People Enrichment, Bulk People Enrichment, Organization Enrichment, and Bulk Organization Enrichment consume credits.
- Apollo exposes an API usage/rate-limit endpoint, and limits vary by plan. The pipeline must read usage before and during runs and fail closed when usage cannot be checked.
- Apollo supports CSV export of enriched contacts. Exporting does not enrich by itself; enrichment must happen before export.
- Apollo credits are used for actions such as requesting verified phones or emails; Apollo says verified net-new emails are credit-charged, and credits expire by billing cycle.
- Apollo pricing is volatile, but Apollo-published 2026 material lists a free plan and annual paid plans starting at Basic around `$49/user/month`, Professional around `$79/user/month`, and Organization around `$119/user/month` with a 3-user minimum. Confirm directly before purchase.

Cheap/free adjacent sources:

- Hunter has a no-time-limit free plan with 50 credits/month, and its pricing page lists annual Starter at `$34/month` with shared monthly quotas.
- Snov.io has a free trial tier and credits usable for prospect search, email search, and verification.
- Findymail offers 10 free credits and an API; its API uses credits for email/profile enrichment.
- Reoon Email Verifier offers up to 600 free verifications/month and low-cost paid credits. Use this for verification, not discovery.
- ZeroBounce offers 100 free monthly email verifications for eligible business/premium-domain signups. Use it as a benchmark verifier, not the primary acquisition source.

Free-path clarification:

- Apollo People API Search is useful for candidate discovery only. It can identify relevant people and companies through official API filters, but it does not return email addresses or phone numbers.
- Reoon, ZeroBounce, MillionVerifier, and similar tools are email verifiers, not email finders. They validate email addresses that the system already has from public websites, user CSV imports, Apollo CSV exports, or finder APIs.
- Hunter, Snov.io, Findymail, and similar finder tools are the discovery layer for missing emails, but free tiers are small and should be treated as pilot quotas, not unlimited acquisition.
- Business websites can often be found from YellowPages, public directories, imported CSVs, or company-domain fields returned by candidate/search APIs. Website discovery should happen before any paid personal-contact enrichment.
- Phone numbers are the hardest field to obtain for free. Use only phones that are already public, user-owned/imported, or returned by an official enrichment path with explicit budget approval.
- The completely free route is therefore: existing YellowPages/public directories and user-owned CSVs first; Apollo People Search for target candidates; public website/contact-page discovery; verifier tools to clean known emails. It should not be described as a free way to get personal emails and phones from Apollo.

## Acquisition Order: Free to Cheapest

1. **Existing YellowPages and permitted public business directories**
   - Cost: free, already built.
   - Yield: business names, phones, addresses, categories, locations; email yield varies.
   - Use for: broad company/domain discovery and local business coverage.
   - Guardrail: each new directory gets a `terms_profile`; no scraping where robots/terms prohibit it.

2. **User-owned CSV imports**
   - Cost: free when the user already has exports from Apollo, CRMs, Sheets, directories, or past campaigns.
   - Yield: potentially highest-quality starting data.
   - Use for: importing Apollo CSV exports and any user-owned lead/customer files.
   - Guardrail: require a source/license note and store provenance per row.

3. **Apollo manual UI workflows plus CSV export**
   - Cost: free/trial/low-plan credits depending on account.
   - Yield: higher quality for selected records, but limited by credits and export rules.
   - Use for: human-run Apollo searches/enrichment, then import the exported CSV into this repo.
   - Guardrail: no UI automation of Apollo; only ingest files the user exports.

4. **Apollo People API Search for candidate discovery**
   - Cost: no Apollo credits according to current docs.
   - Yield: people/company candidate metadata, but no emails/phones.
   - Use for: building candidate pools filtered by title, seniority, location, company domain, employee range, revenue, technology, and job signals.
   - Not for: collecting emails, phone numbers, or bypassing enrichment credits.
   - Guardrail: enforce 100/page, 500-page, 50,000-display caps; split broad queries into narrower batches.

5. **Free/cheap business-domain discovery**
   - Cost: free to low-cost depending on source.
   - Yield: company websites, generic business emails, contact pages, structured metadata.
   - Use for: enriching company domains before spending personal-contact credits.
   - Guardrail: crawl only websites/directories whose terms permit access; respect robots and conservative rate limits.

6. **Email verification first**
   - Cost: free/cheap via Reoon, ZeroBounce, MillionVerifier, or similar.
   - Yield: no new leads, but protects sender reputation and removes invalid/risky addresses.
   - Use for: validating emails found from public websites, user CSVs, and finder APIs.
   - Not for: discovering missing emails, phone numbers, or websites.
   - Guardrail: never treat verifier "valid" as consent to contact; keep verification status separate from outreach eligibility.

7. **Cheap email finder waterfall**
   - Cost: paid but lower-cost than broad Apollo enrichment at small/medium scale.
   - Yield: emails for scored candidate records; phone yield usually weaker.
   - Order: test Hunter free credits, Snov.io trial/free credits, Findymail free credits, then a small paid month/credit pack from the best performer.
   - Guardrail: require per-vendor ToS notes, budget limits, and source-level confidence scores. Do not use vendors for contacts or regions their terms disallow.

8. **Apollo official enrichment endpoints**
   - Cost: Apollo credits.
   - Yield: best fit for high-priority selected records needing verified business email or phone.
   - Use for: top-scored leads only after dedupe and cheaper enrichment attempts.
   - Guardrail: require explicit `enable_paid_apollo=true`, per-run credit budget, usage check, and automatic stop on unknown remaining credits.

9. **Apollo paid plan upgrade**
   - Cost: paid subscription and credits.
   - Yield: higher volume and operational convenience.
   - Use for: only after a measured pilot proves Apollo's cost per usable verified contact beats cheaper vendor waterfall.
   - Guardrail: confirm internal-use/resale/customer-facing rights before purchase.

## Implementation Changes

### 1. Source registry and policy gate

- Add a separate local acquisition database, defaulting to `data/acquisition.sqlite`, instead of mixing Apollo/source policy state into the current YellowPages `data/scraper.sqlite`.
- Add `sources` records for `yellowpages`, `csv_import`, `apollo_csv_export`, `apollo_people_search`, `apollo_enrichment`, `hunter`, `snov`, `findymail`, `reoon`, and `zerobounce`.
- Each source stores: `source_name`, `source_type`, `allowed_use_note`, `terms_url`, `requires_api_key`, `can_collect_people`, `can_collect_contacts`, `can_enrich`, `is_paid`, `enabled`.
- Add a startup policy gate: disabled sources cannot run; paid sources cannot run without an explicit budget; unknown terms block execution.
- Mark `apollo_public.py` as deprecated for production acquisition. Keep only parser tests if useful, or replace it with official Apollo API adapters.
- Remove or block CLI/app paths that present Apollo browser/page scraping as a supported production feature. Any Apollo implementation must use official APIs or user-exported CSV imports.

### 2. Acquisition ledger and queue

- Add SQLite tables for source-agnostic operation:
  - `acquisition_runs`: source, query JSON, status, dry-run flag, record budget, credit budget, started/finished, error.
  - `acquisition_tasks`: run, task type, cursor/page, status, attempts, next_run_at, estimated credits, actual credits.
  - `credit_ledger`: source, run, task, credit kind, estimated, actual, checked_at.
  - `raw_records`: immutable source payload JSON, source record id, acquired_at, provenance.
  - `source_links`: normalized entity id, source, source record id, confidence, acquired_at.
  - `suppression_list`: email/domain/phone/person/company, reason, source, created_at.
- Task statuses: `pending`, `leased`, `succeeded`, `retry_wait`, `blocked_budget`, `blocked_rate`, `skipped_duplicate`, `skipped_policy`, `failed`.
- Use SQLite queueing first. No Celery or external worker until local queue limits are proven.

### 3. Adapter interface

Create a small adapter contract:

```python
class AcquisitionAdapter(Protocol):
    source_name: str

    def estimate_cost(self, query: dict) -> CostEstimate: ...
    def prepare_tasks(self, run: AcquisitionRun) -> list[AcquisitionTask]: ...
    def execute_task(self, task: AcquisitionTask) -> AcquisitionResult: ...
    def normalize(self, raw: RawRecord) -> NormalizedBatch: ...
    def rate_policy(self) -> RatePolicy: ...
    def terms_profile(self) -> TermsProfile: ...
```

V1 adapters:

- `CsvImportAdapter`: maps Apollo/user CSV files into normalized businesses, people, and contacts.
- `ApolloPeopleSearchAdapter`: official People API Search only, no email/phone fields expected.
- `ApolloUsageAdapter`: reads API usage/rate limits before and during Apollo runs.
- `EmailVerifierAdapter`: generic verification contract with Reoon first, ZeroBounce optional.
- `EmailFinderAdapter`: generic finder contract; implement one cheap provider first after API docs are checked.

### 4. Normalization and dedupe

- Normalize around entities:
  - `businesses`: canonical company/business data.
  - `people`: person name, title, seniority, company link, location.
  - `contacts`: email, phone, contact type, verification status, confidence, source.
- Dedupe keys:
  - Strong: exact normalized email, company domain, normalized phone, Apollo person/company id.
  - Medium: normalized company name + city + website.
  - Weak: fuzzy company/person name + title + location.
- Preserve every source link. Never overwrite higher-confidence contact data without keeping the old source provenance.

### 5. Credit and rate safety

- Add config:
  - `max_records_per_run`
  - `max_credits_per_run`
  - `max_credits_per_month`
  - `max_requests_per_minute`
  - `enable_paid_apollo`
  - `enable_paid_finders`
  - `fail_closed_on_unknown_usage`
- Apollo paid/enrichment tasks must:
  - check usage/rate limits first,
  - estimate credits,
  - block if budget is missing or insufficient,
  - stop immediately on 401/403/422/429 or unknown usage response,
  - persist the stop reason in `acquisition_tasks`.

### 6. Streamlit operations UI

Add a separate Streamlit acquisition workbench while keeping the existing YellowPages results UI unchanged for now:

- Source toggles and status cards.
- Run builder: source, query filters, max records, max pages, credit budget, dry-run checkbox.
- Dry-run preview: estimated records, estimated credits, exact source terms note, expected output fields.
- Queue dashboard: pending, succeeded, blocked, failed, retry-wait.
- Budget dashboard: estimated/actual credits by source and run.
- Data quality dashboard: new records, duplicates merged, contacts verified, risky contacts rejected.
- Export controls: filter by source, contact availability, verification status, confidence, date, and suppression status.
- Later merge path: once adapters and policy gates are stable, add a reviewed export/merge command from `data/acquisition.sqlite` into the main results database using shared normalized fields.

## Test Plan

- Policy tests:
  - disabled source cannot run,
  - unknown terms block execution,
  - paid Apollo enrichment blocks unless `enable_paid_apollo=true` and a budget exists,
  - app-scraping modes do not exist.
- Adapter contract tests:
  - CSV import maps common Apollo/export headers,
  - Apollo People Search normalizes mocked API responses without emails/phones,
  - verifier/finder adapters record confidence and source.
- Queue tests:
  - task leasing is idempotent,
  - retry waits do not spin,
  - blocked budget/rate states are resumable,
  - failed runs preserve partial raw records.
- Credit safety tests:
  - Apollo usage endpoint success updates the ledger,
  - missing usage response fails closed,
  - 429 blocks more tasks,
  - estimated spend cannot exceed per-run or monthly budgets.
- Dedupe tests:
  - duplicate imported CSV + Apollo API records merge source links,
  - exact email/domain/phone matches dedupe strongly,
  - conflicting data preserves provenance.
- Streamlit/browser checks:
  - dry-run preview is visible before any live run,
  - paid-source warnings appear,
  - queue and budget dashboards update after mocked runs,
  - filtered exports exclude suppressed/risky contacts by default.
- Live gates:
  - run only a one-page Apollo People Search dry run first,
  - run one small CSV import,
  - run one verifier sample of 10 emails,
  - no bulk paid enrichment until all mocked and dry-run gates pass.

## Acceptance Criteria

- The app can acquire and import data from free sources and user CSVs without using Apollo credits.
- Apollo People Search can build candidate pools through the official API while respecting documented display/page limits.
- Paid enrichment cannot run accidentally; it requires explicit config and budget.
- Every row can answer: source, method, time acquired, permission/terms note, raw record, normalized entity, and confidence.
- Streamlit shows what will happen before a run starts, including expected credit impact and stop conditions.
- Existing YellowPages tests and UI behavior continue to pass.

## Source Links

- Apollo Terms of Service: https://www.apollo.io/terms-of-service
- Apollo API Terms: https://www.apollo.io/terms/api
- Apollo People API Search: https://docs.apollo.io/reference/people-api-search
- Apollo API Pricing: https://docs.apollo.io/docs/api-pricing
- Apollo API Rate Limits: https://docs.apollo.io/reference/rate-limits
- Apollo CSV Export: https://knowledge.apollo.io/hc/en-us/articles/4409237712141-Export-Contacts-to-a-CSV
- Apollo Credits: https://knowledge.apollo.io/hc/en-us/articles/9527776320781-What-Are-Credits
- Hunter Free Plan: https://help.hunter.io/en/articles/11060999-what-s-included-in-hunter-s-free-plan
- Hunter Pricing: https://hunter.io/pricing
- Snov.io Pricing: https://snov.io/pricing
- Findymail Pricing: https://www.findymail.com/pricing/
- Findymail API: https://www.findymail.com/api/
- Reoon Email Verifier: https://www.reoon.com/email-verifier/
- ZeroBounce Pricing: https://www.zerobounce.net/email-validation-pricing
