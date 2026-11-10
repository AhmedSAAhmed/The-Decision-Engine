# Two-year thesis: autonomy becomes a permission, not a prompt

By late 2028 the decision layer will be a separate product, bought and audited the way companies buy
identity and access management today. Every serious agent platform will call one before it acts.

**1. "Can it act?" splits from "can it do the task?"** Models will keep getting more capable, but no bank or
telco will let the component that writes the reply also authorise the refund. Agents will need two keys:
the model's competence and the decision layer's permission. That split matters more than any model upgrade.

**2. Autonomy budgets replace binary permissions.** "Agent may refund" is the wrong primitive. The right one is
"this agent may risk up to N in expected loss per decision on this action class". The budget grows with a verified
track record and shrinks after incidents, like an employee's signing authority. Insurers and regulators will
price expected loss, not confidence.

**3. Decision logs become the compliance artefact.** GCC and EU regulators will ask for replayable,
tamper-evident records of *why* an AI acted, not model cards. Hash-chained logs with policy hashes are what
auditors will sample.

**4. The attack surface moves into the system of record.** Once conversation-level manipulation is gated, the
cheap attack is poisoning what the decision layer trusts: approvals, customer history, outage logs. The next
generation will verify *provenance* (signed records, separation of duties, cross-source checks), not just
presence. My second failure test sits exactly there.

**5. Escalation becomes a product surface.** "Escalate" will mean a routed, pre-researched case with the missing
evidence listed, and the human's verdict will feed the next policy version. Decision layers will be judged on
how few escalations they need and how fast each one closes.

The winners won't have the smartest agents. They'll own the layer that decides when an agent is trusted to act.
