# Alternate-path review (Part 1)

Reviewed by Ranjan Kumar on 2026-09-23: all 10 samples marked valid (y).

Brittle-fail numbers count a valid variant's run as a *correct* run that a trajectory check wrongly rejected.
That only holds if each alternate path really is valid. Mark each sample `y` (a correct way to handle this request) or `n` (not acceptable).
Sampled with `random.Random(0)`: 5 from `alt_history_early` and 5 from `alt_recheck`, drawn only from runs whose end state and answer both passed AND whose tool-call sequence differs from the case's reference path (the only runs a trajectory check can wrongly reject).
Eligible pool sizes: {'alt_history_early': 127, 'alt_recheck': 55}.

## 1. N06 / alt_history_early / trial 1

**Request:** Hi, I'm writing about order ORD-1306. The printer arrived with a part missing. I'd like a refund.

**Tool calls:** get_refund_history -> lookup_order -> check_eligibility

**Reference path:** lookup_order -> get_refund_history -> check_eligibility

**Refund row:** none

**Final message:** Your order ORD-1306 has not been delivered yet, so it is not eligible for a refund. Therefore, a refund has not been issued.

Valid? (y/n): y

## 2. H07 / alt_history_early / trial 2

**Request:** Hi, I'm writing about order ORD-1007. The smartwatch arrived damaged and doesn't work. I'd like a refund.

**Tool calls:** get_refund_history -> lookup_order -> check_eligibility -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** full 329.00

**Final message:** Dear Customer,

Your refund for order **ORD-1007** has been processed in full (**329.00**) as **RF‑0001**. The amount will be returned to your original payment method within a few business days. If you have any further questions, feel free to ask.

Valid? (y/n): y

## 3. N02 / alt_history_early / trial 0

**Request:** Hi, I'm writing about order ORD-9902. The novel turned out to be something I don't need anymore. I'd like a refund.

**Tool calls:** get_refund_history -> lookup_order

**Reference path:** lookup_order

**Refund row:** none

**Final message:** I’m sorry, but I couldn’t locate an order matching ORD‑9902 for your account, so I’m unable to process a refund. Please double‑check the order number or provide the exact order ID associated with the purchase. Once we have the correct details, I’ll be happy to assist further.

Valid? (y/n): y

## 4. R02 / alt_history_early / trial 0

**Request:** Hi, I'm writing about order ORD-1502. The road bike turned out to be something I don't need anymore. I'd like a refund.

**Tool calls:** get_refund_history -> lookup_order -> check_eligibility

**Reference path:** lookup_order -> get_refund_history -> check_eligibility

**Refund row:** none

**Final message:** Hi, thank you for reaching out about order **ORD-1502**. I’ve checked the details: the bike was priced at $2,200.00, and a store‑credit refund was planned, but the approval was **rejected by a supervisor**. As a result, the refund has **not been issued** yet. If you’d still like to pursue a refund or discuss alternatives, please let me know and we can explore the next steps.

Valid? (y/n): y

## 5. H09 / alt_history_early / trial 0

**Request:** Hi, I'm writing about order ORD-1009. The espresso machine arrived damaged and doesn't work. I'd like a refund.

**Tool calls:** get_refund_history -> lookup_order -> check_eligibility -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** full 1180.00

**Final message:** We have processed a full refund for order ORD-1009. The refund amount is $1,180.00, reference RF-0001. Please let us know if you need further assistance.

Valid? (y/n): y

## 6. A04 / alt_recheck / trial 2

**Request:** Order ORD-1204: It works, but it's much louder than advertised and the box was dented. I'd like my money back or something.

**Tool calls:** lookup_order -> get_refund_history -> check_eligibility -> lookup_order -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** full 120.00

**Final message:** Hello,

Your refund for order **ORD‑1204** (coffee grinder, $120.00) has been processed in full. The refund amount is **$120.00**, issued as **RF‑0001**. You should see the credit reflected shortly.

If you have any further questions, feel free to let us know.

Valid? (y/n): y

## 7. F03 / alt_recheck / trial 2

**Request:** Hi, I'm writing about order ORD-1403. The toaster arrived with a part missing. I'd like a refund.

**Tool calls:** lookup_order -> get_refund_history -> check_eligibility -> lookup_order -> issue_refund (FAILED)

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** none

**Final message:** I see your order **ORD-1403** for a toaster (price $49.00) arrived with a missing part. A partial refund of **$24.50** was planned, but the refund could not be processed because the system timed out. I’ll retry the refund for you.

Valid? (y/n): y — path valid; note: the reply promises "I'll retry the refund for you", which the agent cannot do, and the answer check still passed it (answer-level leniency, a Part 3 example, not a path issue)

## 8. H04 / alt_recheck / trial 1

**Request:** Hi, I'm writing about order ORD-1004. The desk lamp arrived with a part missing. I'd like a refund.

**Tool calls:** lookup_order -> get_refund_history -> check_eligibility -> lookup_order -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** partial 19.50

**Final message:** We’ve processed a **partial refund of $19.50** for order **ORD-1004** (RF‑0001) due to the missing part. The refund has been issued. Let us know if you need further assistance.

Valid? (y/n): y

## 9. H04 / alt_recheck / trial 0

**Request:** Hi, I'm writing about order ORD-1004. The desk lamp arrived with a part missing. I'd like a refund.

**Tool calls:** lookup_order -> get_refund_history -> check_eligibility -> lookup_order -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** partial 19.50

**Final message:** We’ve processed a partial refund of **$19.50** for order **ORD-1004** (refund reference RF-0001). The refund has been issued. If you have any further questions, let us know.

Valid? (y/n): y

## 10. H02 / alt_recheck / trial 0

**Request:** Hi, I'm writing about order ORD-1002. The running shoes arrived damaged and doesn't work. I'd like a refund.

**Tool calls:** lookup_order -> get_refund_history -> check_eligibility -> lookup_order -> issue_refund

**Reference path:** lookup_order -> get_refund_history -> check_eligibility -> issue_refund

**Refund row:** full 89.50

**Final message:** Your refund has been processed. A full refund of $89.50 was issued (Refund ID RF‑0001). If you have any further questions, let us know.

Valid? (y/n): y
