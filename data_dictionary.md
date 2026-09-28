# Data Dictionary — Insurance Dashboard Agent

**Purpose:** This document defines every table and column in the dashboard agent's data model.  
It is the "source of truth" the agent reads before answering any dashboard request.  
Treat it the same way you would an Atlan or Collibra governance document.

---

## Table: policies

**What it represents:** One row = one active or expired insurance policy. A policy is the contract between the insurer and the customer. It only appears here if the customer accepted a quote (i.e., "bound" the policy).

| Column | Business Name | Definition | Example Values | Links To |
|--------|--------------|------------|----------------|----------|
| `policy_id` | Policy ID | Unique identifier for the policy contract. Assigned at binding. | POL000001, POL000742 | `quotes.policy_id`, `claims.policy_id` |
| `customer_id` | Customer ID | Unique identifier for the insured customer. One customer may have multiple policies over time, but in this dataset each customer has one policy. | CUS000001, CUS000742 | `quotes.customer_id`, `claims.customer_id` |
| `state` | State | Two-letter US state abbreviation where the policy is written. Drives premium pricing and regulatory requirements. | CA, TX, FL, NY, OH | — |
| `product` | Product Line | The type of insurance. "auto" covers vehicles; "home" covers residential property. | auto, home | — |
| `channel` | Sales Channel | How the policy was sold. "agent" = through a licensed captive agent; "direct" = customer bought online or by phone with no intermediary; "broker" = through an independent broker who shops multiple carriers. | agent, direct, broker | — |
| `effective_date` | Effective Date | The date the policy coverage starts. The customer is protected from losses on or after this date. Format: YYYY-MM-DD. | 2024-03-15 | — |
| `expiry_date` | Expiry Date | The date the policy coverage ends. Always exactly 365 days after the effective date (one-year term). The policy must be renewed or it lapses. Format: YYYY-MM-DD. | 2025-03-15 | — |
| `annual_premium` | Annual Premium | The total amount the customer pays per year for this policy, in US dollars. Auto range: $800–$2,500. Home range: $1,200–$4,000. | 1245.00, 2890.50 | — |

---

## Table: quotes

**What it represents:** One row = one price quote given to a prospective customer. A quote may or may not convert into a policy. This is the primary table for measuring sales funnel performance (quote volume, conversion rate, lost business).

| Column | Business Name | Definition | Example Values | Links To |
|--------|--------------|------------|----------------|----------|
| `quote_id` | Quote ID | Unique identifier for the quote. | QUO000001, QUO001456 | — |
| `policy_id` | Policy ID | Links to the policy that was created when this quote was accepted. **Blank when status is "quoted" or "lost"** — only populated for "bound" quotes. | POL000001, (blank) | `policies.policy_id` |
| `customer_id` | Customer ID | The customer who requested the quote. For lost/quoted rows, this customer never became a policyholder. | CUS000001, CUS002500 | `policies.customer_id` |
| `state` | State | State where the coverage is requested. Same definition as in policies. | CA, TX | — |
| `product` | Product Line | Type of insurance quoted. Same values as in policies. | auto, home | — |
| `channel` | Sales Channel | How the quote was requested. Same values as in policies. | agent, direct, broker | — |
| `quote_date` | Quote Date | Date the quote was generated and presented to the customer. Always before `bind_date` for bound quotes. Format: YYYY-MM-DD. | 2024-03-01 | — |
| `quoted_premium` | Quoted Premium | The annual premium shown to the customer in this quote. May differ slightly from `annual_premium` in policies (rounding, final underwriting adjustments). | 1190.00, 2750.00 | — |
| `status` | Quote Status | The outcome of the quote. "quoted" = still open, awaiting customer decision; "bound" = customer accepted, policy created; "lost" = customer declined or chose a competitor. | quoted, bound, lost | — |
| `bind_date` | Bind Date | The date the customer accepted the quote and the policy was activated. Equals `effective_date` in policies. **Blank when status is "quoted" or "lost".** Format: YYYY-MM-DD. | 2024-03-15, (blank) | `policies.effective_date` |

---

## Table: claims

**What it represents:** One row = one insurance claim filed by a policyholder. A claim is a formal request for the insurer to pay for a covered loss. A single policy can have multiple claims. Only policyholders can file claims (no claims from lost/quoted-only customers).

| Column | Business Name | Definition | Example Values | Links To |
|--------|--------------|------------|----------------|----------|
| `claim_id` | Claim ID | Unique identifier for the claim. | CLM000001, CLM000512 | — |
| `policy_id` | Policy ID | Links to the policy under which the claim was filed. | POL000001, POL000500 | `policies.policy_id` |
| `customer_id` | Customer ID | The insured customer who filed the claim. | CUS000001 | `policies.customer_id` |
| `state` | State | State where the loss occurred (inherited from the policy). | CA, TX | — |
| `product` | Product Line | Type of coverage under which the claim was filed. | auto, home | — |
| `claim_date` | Claim Date | Date the claim was formally filed with the insurer. Always falls within the policy's effective–expiry window. Format: YYYY-MM-DD. | 2024-07-22 | — |
| `claim_type` | Claim Type | The type of loss being claimed. Auto types: collision (crash with another vehicle or object), comprehensive (non-collision damage: theft, weather), liability (damage to third-party property), bodily_injury (injury to a third party). Home types: fire, water_damage, theft, wind_damage. | collision, water_damage | — |
| `claim_amount` | Claim Amount | The dollar amount paid or estimated for the claim, in US dollars. Auto range: $500–$25,000. Home range: $1,000–$80,000. Open claims show the current reserve (estimate). | 4250.00, 18900.00 | — |
| `claim_status` | Claim Status | Current processing status. "open" = under investigation, not yet paid; "closed" = paid and resolved; "denied" = insurer determined the loss is not covered. | open, closed, denied | — |

---

## Key Relationships

```
quotes ──(policy_id)──► policies ──(policy_id)──► claims
quotes ──(customer_id)─ policies ──(customer_id)─ claims
```

- Every claim has a matching policy. Claims never exist without a policy.
- Every bound quote has a matching policy. Lost/quoted quotes have no policy.
- Customer IDs link across all three tables, but only bound customers appear in policies and claims.

---

## Common Business Metrics (for agent reference)

| Metric | How to Calculate | Table(s) Needed |
|--------|-----------------|-----------------|
| Quote volume | COUNT rows in quotes | quotes |
| Bind rate / Conversion rate | COUNT(status='bound') / COUNT(*) in quotes | quotes |
| Written premium | SUM(annual_premium) in policies | policies |
| Claim frequency | COUNT(claims) / COUNT(policies) | claims, policies |
| Average claim severity | AVG(claim_amount) in claims | claims |
| Loss ratio | SUM(claim_amount) / SUM(annual_premium) | claims, policies |
| Open claim backlog | COUNT(claim_status='open') in claims | claims |
