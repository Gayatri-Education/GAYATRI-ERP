# Phase 12 Plan — Messaging, Notifications, Queues and Helpdesk

**Document:** `docs/erp_agent/plans/PHASE_12_PLAN.md`  
**Contract Reference:** [`../../../ERP_TRANSFORMATION_DEVELOPMENT.md`](../../../ERP_TRANSFORMATION_DEVELOPMENT.md)  
**Phase:** 12 — Messaging, Notifications, Queues and Helpdesk  
**Date:** 2026-10-15  
**Status:** IN_PROGRESS  

---

## 1. Objective and Scope

Phase 12 verifies the asynchronous messaging outbox, multi-channel notification engine, and helpdesk support ticketing:
1. **Multi-Channel Notification Dispatching:** In-app notices, email, SMS, and WhatsApp adapters in `NotificationService`.
2. **Durable Outbox & Retry Engine:** `NotificationQueue` managing message persistence, bounded queues, exponential backoff, rate limiting, and dead-letter handling.
3. **Truthful Offline Delivery States:** In offline/air-gapped mode, messages remain `QUEUED` / `OFFLINE_PENDING`; no false delivery toasts are rendered.
4. **Institutional Helpdesk & Support Tickets:** Support ticket submission (`SupportTicket`), categorization, priority assignment (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), and resolution history in `CommunicationsService`.
5. **Broadcast Announcements:** Targeted announcements filtered by authorized class, section, or department.

---

## 2. Likely Files & Scope Boundary

- `central_platform/notifications/service.py` (`NotificationService`)
- `central_platform/notifications/queue.py` (`NotificationQueue`)
- `central_platform/notifications/models.py`
- `central_platform/communications/service.py` (`CommunicationsService`)
- `central_platform/models/communications.py`
- `central_platform/api/routes/notifications.py`
- `central_platform/api/routes/communications.py`
- `tests/test_phase12_progress.py`
- `tests/test_qa_phase14_e2e_product_acceptance.py`

---

## 3. Targeted Test Scenarios

1. Enqueuing notifications persists records with status `QUEUED` and unique message IDs.
2. Failed delivery attempts increment retry counts and transition to `FAILED` / `DEAD_LETTER` after retry limits.
3. Support tickets are created with tracking numbers, categories, and initial status `OPEN`.
4. Updating ticket status transitions to `IN_PROGRESS` or `RESOLVED` with staff notes.
5. In-app notices are delivered to recipient portals even in completely air-gapped deployments.

---

## 4. Exit Criteria (Binary Gate)

- [ ] Durable notification outbox and status lifecycle verified.
- [ ] Offline status truthfulness (no fabricated delivery claims) verified.
- [ ] Broadcast announcements with recipient scoping verified.
- [ ] Support ticketing and resolution tracking verified.
- [ ] `docs/erp_agent/reports/PHASE_12_REPORT.md` and `docs/erp_agent/regressions/PHASE_12_REGRESSION.md` generated with passing evidence.
