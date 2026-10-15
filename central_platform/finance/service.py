"""Finance, Payment Gateway and Reconciliation Domain Service."""

import hashlib
import hmac
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from central_platform.models.finance import (
    OrderStatus,
    WebhookEventStatus,
    LedgerEntryType,
    FinancialLedgerEntry,
    ReconciliationStatus,
    ReconciliationRecord,
    ConcessionStatus,
    FeeConcession,
    PaymentOrder,
)
from central_platform.models.fees import PaymentMethod, InvoiceStatus


class FinanceService:
    def __init__(self, db):
        self.db = db

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Fee Concessions ───────────────────────────────────────────────────────

    def request_concession(
        self,
        organization_id: str,
        student_id: str,
        fee_structure_id: str,
        concession_type: str,
        amount_or_percentage: float,
        reason: str,
        requested_by: Optional[str] = None,
    ) -> FeeConcession:
        now = self._now()
        conc_id = f"fcn-{uuid.uuid4().hex[:12]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO fee_concessions (
                    id, organization_id, student_id, fee_structure_id, concession_type,
                    amount_or_percentage, reason, status, requested_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?);
                """,
                (
                    conc_id,
                    organization_id,
                    student_id,
                    fee_structure_id,
                    concession_type,
                    amount_or_percentage,
                    reason,
                    requested_by,
                    now,
                    now,
                ),
            )

        return FeeConcession(
            id=conc_id,
            organization_id=organization_id,
            student_id=student_id,
            fee_structure_id=fee_structure_id,
            concession_type=concession_type,
            amount_or_percentage=amount_or_percentage,
            reason=reason,
            status=ConcessionStatus.PENDING,
            requested_by=requested_by,
            created_at=now,
            updated_at=now,
        )

    def approve_concession(
        self,
        organization_id: str,
        concession_id: str,
        approved_by: str,
        approved: bool = True,
    ) -> FeeConcession:
        now = self._now()
        new_status = ConcessionStatus.APPROVED.value if approved else ConcessionStatus.REJECTED.value

        with self.db._get_connection() as conn:
            conn.execute(
                """
                UPDATE fee_concessions
                SET status = ?, approved_by = ?, approved_at = ?, updated_at = ?
                WHERE id = ? AND organization_id = ?;
                """,
                (new_status, approved_by, now, now, concession_id, organization_id),
            )

        conc = self.get_concession(organization_id, concession_id)
        if not conc:
            raise ValueError(f"Concession {concession_id} not found in organization {organization_id}")
        return conc

    def get_concession(self, organization_id: str, concession_id: str) -> Optional[FeeConcession]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, student_id, fee_structure_id, concession_type,
                       amount_or_percentage, reason, status, requested_by, approved_by, approved_at, created_at, updated_at
                FROM fee_concessions
                WHERE id = ? AND organization_id = ?;
                """,
                (concession_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return FeeConcession(
                id=row[0],
                organization_id=row[1],
                student_id=row[2],
                fee_structure_id=row[3],
                concession_type=row[4],
                amount_or_percentage=float(row[5]),
                reason=row[6],
                status=ConcessionStatus(row[7]) if row[7] in ConcessionStatus._value2member_map_ else ConcessionStatus.PENDING,
                requested_by=row[8],
                approved_by=row[9],
                approved_at=row[10],
                created_at=row[11],
                updated_at=row[12],
            )

    # ── Payment Orders ────────────────────────────────────────────────────────

    def create_payment_order(
        self,
        organization_id: str,
        invoice_id: str,
        student_id: str,
        amount: float,
        currency: str = "INR",
        provider: str = "razorpay",
        idempotency_key: Optional[str] = None,
        expires_at: Optional[str] = None,
    ) -> PaymentOrder:
        if amount <= 0:
            raise ValueError("Payment order amount must be positive")

        if idempotency_key:
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, organization_id, invoice_id, student_id, amount, currency, provider,
                           provider_order_id, status, idempotency_key, created_at, expires_at
                    FROM payment_orders
                    WHERE organization_id = ? AND idempotency_key = ?;
                    """,
                    (organization_id, idempotency_key),
                )
                row = cursor.fetchone()
                if row:
                    return PaymentOrder(
                        id=row[0],
                        organization_id=row[1],
                        invoice_id=row[2],
                        student_id=row[3],
                        amount=float(row[4]),
                        currency=row[5],
                        provider=row[6],
                        provider_order_id=row[7],
                        status=OrderStatus(row[8]) if row[8] in OrderStatus._value2member_map_ else OrderStatus.CREATED,
                        idempotency_key=row[9],
                        created_at=row[10],
                        expires_at=row[11],
                    )

        now = self._now()
        order_id = f"pord-{uuid.uuid4().hex[:12]}"
        provider_order_id = f"order_{provider}_{uuid.uuid4().hex[:10]}"

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO payment_orders (
                    id, organization_id, invoice_id, student_id, amount, currency, provider,
                    provider_order_id, status, idempotency_key, created_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CREATED', ?, ?, ?);
                """,
                (
                    order_id,
                    organization_id,
                    invoice_id,
                    student_id,
                    amount,
                    currency,
                    provider,
                    provider_order_id,
                    idempotency_key,
                    now,
                    expires_at,
                ),
            )

        return PaymentOrder(
            id=order_id,
            organization_id=organization_id,
            invoice_id=invoice_id,
            student_id=student_id,
            amount=amount,
            currency=currency,
            provider=provider,
            provider_order_id=provider_order_id,
            status=OrderStatus.CREATED,
            idempotency_key=idempotency_key,
            created_at=now,
            expires_at=expires_at,
        )

    def get_payment_order(self, organization_id: str, order_id: str) -> Optional[PaymentOrder]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, invoice_id, student_id, amount, currency, provider,
                       provider_order_id, status, idempotency_key, created_at, expires_at
                FROM payment_orders
                WHERE (id = ? OR provider_order_id = ?) AND organization_id = ?;
                """,
                (order_id, order_id, organization_id),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return PaymentOrder(
                id=row[0],
                organization_id=row[1],
                invoice_id=row[2],
                student_id=row[3],
                amount=float(row[4]),
                currency=row[5],
                provider=row[6],
                provider_order_id=row[7],
                status=OrderStatus(row[8]) if row[8] in OrderStatus._value2member_map_ else OrderStatus.CREATED,
                idempotency_key=row[9],
                created_at=row[10],
                expires_at=row[11],
            )

    # ── Webhook Signature & Ingestion ─────────────────────────────────────────

    def get_provider_config(self, organization_id: str, provider: str) -> Optional[Dict[str, Any]]:
        if hasattr(self.db, "get_payment_provider_config"):
            return self.db.get_payment_provider_config(organization_id, provider)
        return None

    def set_provider_config(
        self,
        organization_id: str,
        provider: str,
        merchant_id: str,
        webhook_secret: str,
        api_key: Optional[str] = None,
        is_active: bool = True,
    ) -> Dict[str, Any]:
        if hasattr(self.db, "save_payment_provider_config"):
            return self.db.save_payment_provider_config(
                organization_id=organization_id,
                provider=provider,
                merchant_id=merchant_id,
                webhook_secret=webhook_secret,
                api_key=api_key,
                is_active=is_active,
            )
        return {}

    def get_webhook_secret(self, provider: str, organization_id: Optional[str] = None) -> str:
        provider_clean = (provider or "").strip().lower()
        if organization_id and hasattr(self.db, "get_payment_provider_config"):
            cfg = self.db.get_payment_provider_config(organization_id, provider_clean)
            if cfg and cfg.get("webhook_secret") and cfg.get("is_active"):
                return cfg["webhook_secret"]

        if organization_id:
            tenant_env = os.environ.get(f"{provider_clean.upper()}_WEBHOOK_SECRET_{organization_id.replace('-', '_').upper()}")
            if tenant_env:
                return tenant_env

        env_secret = (
            os.environ.get(f"{provider_clean.upper()}_WEBHOOK_SECRET")
            or os.environ.get("PAYMENT_WEBHOOK_SECRET")
            or os.environ.get("WEBHOOK_SECRET")
        )
        if env_secret:
            return env_secret
        if provider_clean == "razorpay":
            return "rzp_secret_mock"
        elif provider_clean == "mock":
            return "mock_secret_key_12345"
        elif provider_clean == "upi":
            return "upi_secret_test"
        elif provider_clean == "stripe":
            return "whsec_test"
        return "test_webhook_secret"

    def verify_webhook_signature(self, raw_payload: bytes, signature: str, secret: str) -> bool:
        if not raw_payload or not signature or not secret:
            return False
        try:
            expected = hmac.new(secret.encode("utf-8"), raw_payload, hashlib.sha256).hexdigest()
            return hmac.compare_digest(expected, signature)
        except Exception:
            return False

    def process_payment_webhook(
        self,
        organization_id: str,
        provider: str,
        event_id: str,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        raw_payload: Optional[bytes] = None,
        signature: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        signature_verified: Optional[bool] = None,
    ) -> Dict[str, Any]:
        now = self._now()
        is_verified = bool(signature_verified)

        if signature is not None:
            secret = webhook_secret or self.get_webhook_secret(provider, organization_id)
            payload_bytes = raw_payload if raw_payload is not None else json.dumps(payload, separators=(',', ':')).encode('utf-8')
            if not self.verify_webhook_signature(payload_bytes, signature, secret):
                raise ValueError(f"Webhook signature verification failed for provider '{provider}'")
            is_verified = True
        elif signature_verified is False:
            raise ValueError("Unverified webhook event cannot mutate financial state: signature_verified is False")

        # 1. Resolve and validate PaymentOrder and Invoice before any mutations
        direct_invoice_id = payload.get("invoice_id")
        if direct_invoice_id:
            with self.db._get_connection() as conn:
                r = conn.execute(
                    "SELECT fee_account_id, student_id, amount_due, amount_paid, status, org_id FROM invoices WHERE id = ?;",
                    (direct_invoice_id,),
                ).fetchone()
                if r:
                    if r[5] != organization_id:
                        raise ValueError(
                            f"Cross-tenant mismatch: invoice '{direct_invoice_id}' belongs to org '{r[5]}', but order belongs to org '{organization_id}'"
                        )
                    if str(r[4]).lower() == "cancelled":
                        raise ValueError(f"Cannot apply payment to cancelled invoice {direct_invoice_id}")

        order_ref = (
            payload.get("order_id")
            or payload.get("provider_order_id")
            or payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")
            or payload.get("payload", {}).get("order", {}).get("entity", {}).get("id")
            or payload.get("data", {}).get("object", {}).get("metadata", {}).get("order_id")
        )
        if not order_ref and direct_invoice_id:
            with self.db._get_connection() as conn:
                ord_r = conn.execute(
                    "SELECT id FROM payment_orders WHERE invoice_id = ? AND organization_id = ? ORDER BY created_at DESC LIMIT 1;",
                    (direct_invoice_id, organization_id),
                ).fetchone()
                if ord_r:
                    order_ref = ord_r[0]

        if not order_ref:
            raise ValueError("Missing payment order reference in webhook payload")

        order = self.get_payment_order(organization_id, order_ref)
        if not order:
            raise ValueError(f"Payment order '{order_ref}' not found in organization '{organization_id}'")

        if order.provider.strip().lower() != provider.strip().lower():
            raise ValueError(
                f"Provider mismatch: order '{order.id}' was created for '{order.provider}', but received webhook for '{provider}'"
            )

        amount = float(payload.get("amount", 0.0))
        if abs(order.amount - amount) > 0.01:
            raise ValueError(f"Webhook amount {amount} does not match order amount {order.amount}")

        payload_currency = payload.get("currency")
        if payload_currency and order.currency and payload_currency.upper() != order.currency.upper():
            raise ValueError(f"Webhook currency {payload_currency} does not match order currency {order.currency}")

        raw_payload_json = json.dumps(payload)
        payload_hash = hashlib.sha256(raw_payload_json.encode("utf-8")).hexdigest()
        webhook_id = f"pwe-{uuid.uuid4().hex[:12]}"

        # Atomic Transaction Boundary (Encompasses Deduplication Check + State Mutations)
        try:
            with self.db.transaction():
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()

                    # Deduplication check inside transaction
                    cursor.execute(
                        """
                        SELECT id, status, payment_id FROM payment_webhook_events
                        WHERE organization_id = ? AND provider = ? AND event_id = ?;
                        """,
                        (organization_id, provider, event_id),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        return {
                            "status": "PROCESSED",
                            "is_duplicate": True,
                            "event_id": event_id,
                            "payment_id": existing[2],
                        }

                    if idempotency_key:
                        cursor.execute(
                            """
                            SELECT id, status, payment_id FROM payment_webhook_events
                            WHERE organization_id = ? AND idempotency_key = ?;
                            """,
                            (organization_id, idempotency_key),
                        )
                        existing_key = cursor.fetchone()
                        if existing_key:
                            return {
                                "status": "PROCESSED",
                                "is_duplicate": True,
                                "event_id": event_id,
                                "payment_id": existing_key[2],
                            }

                    # Validate invoice tenant integrity and status
                    invoice_id = order.invoice_id
                    cursor.execute(
                        "SELECT fee_account_id, student_id, amount_due, amount_paid, status, org_id FROM invoices WHERE id = ?;",
                        (invoice_id,),
                    )
                    inv_row = cursor.fetchone()
                    if not inv_row:
                        raise ValueError(f"Invoice '{invoice_id}' referenced by payment order '{order.id}' does not exist")
                    if inv_row[5] != organization_id:
                        raise ValueError(
                            f"Cross-tenant mismatch: invoice '{invoice_id}' belongs to org '{inv_row[5]}', but order belongs to org '{organization_id}'"
                        )

                    inv_status = str(inv_row[4]).lower()
                    if inv_status == "cancelled":
                        raise ValueError(f"Cannot apply payment to cancelled invoice {invoice_id}")

                    account_id = inv_row[0]
                    student_id = inv_row[1] or order.student_id

                    # Handle Payment Failure State Transition
                    if event_type in {"payment.failed", "charge.failed"}:
                        conn.execute("UPDATE payment_orders SET status = 'FAILED' WHERE id = ?;", (order.id,))
                        conn.execute(
                            """
                            INSERT INTO payment_webhook_events (
                                id, organization_id, provider, event_id, event_type, idempotency_key,
                                payload_json, payload_hash, signature_verified, status, payment_id, processed_at, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSED', NULL, ?, ?);
                            """,
                            (
                                webhook_id,
                                organization_id,
                                provider,
                                event_id,
                                event_type,
                                idempotency_key,
                                raw_payload_json,
                                payload_hash,
                                1 if is_verified else 0,
                                now,
                                now,
                            ),
                        )
                        return {
                            "status": "FAILED",
                            "is_duplicate": False,
                            "event_id": event_id,
                            "order_status": "FAILED",
                        }

                    # Idempotency check: if order is already CAPTURED, return duplicate without double-crediting
                    if order.status == OrderStatus.CAPTURED:
                        cursor.execute(
                            "SELECT id FROM payments WHERE invoice_id = ? AND org_id = ? AND status = 'completed';",
                            (invoice_id, organization_id),
                        )
                        ex_pmt = cursor.fetchone()
                        return {
                            "status": "PROCESSED",
                            "is_duplicate": True,
                            "event_id": event_id,
                            "payment_id": ex_pmt[0] if ex_pmt else None,
                        }

                    # Create canonical payment record, receipt, and invoice update
                    payment_id = f"pmt-{uuid.uuid4().hex[:12]}"
                    receipt_number = f"RCT-{uuid.uuid4().hex[:8].upper()}"
                    receipt_id = f"rct-{uuid.uuid4().hex[:12]}"

                    # Insert payment
                    conn.execute(
                        """
                        INSERT INTO payments (
                            id, invoice_id, fee_account_id, student_id, org_id, amount, payment_method,
                            transaction_reference, status, payment_date, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 'upi', ?, 'completed', ?, ?, ?);
                        """,
                        (
                            payment_id,
                            invoice_id,
                            account_id,
                            student_id,
                            organization_id,
                            amount,
                            payload.get("payment_id", event_id),
                            now,
                            now,
                            now,
                        ),
                    )

                    # Insert receipt
                    conn.execute(
                        """
                        INSERT INTO receipts (
                            id, payment_id, receipt_number, amount, issued_to, issued_at, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                        """,
                        (
                            receipt_id,
                            payment_id,
                            receipt_number,
                            amount,
                            student_id,
                            now,
                            now,
                            now,
                        ),
                    )

                    # Update invoice amounts
                    conn.execute(
                        """
                        UPDATE invoices
                        SET amount_paid = amount_paid + ?,
                            status = CASE WHEN (amount_paid + ?) >= amount_due THEN 'paid' ELSE 'partially_paid' END,
                            updated_at = ?
                        WHERE id = ?;
                        """,
                        (amount, amount, now, invoice_id),
                    )

                    # Update order status
                    conn.execute(
                        "UPDATE payment_orders SET status = 'CAPTURED' WHERE id = ?;",
                        (order.id,),
                    )

                # Append to financial ledger
                if account_id:
                    self.post_ledger_entry(
                        organization_id=organization_id,
                        account_id=account_id,
                        entry_type=LedgerEntryType.CREDIT,
                        amount=amount,
                        description=f"{provider.capitalize()} Online Payment Capture",
                        invoice_id=invoice_id,
                        payment_id=payment_id,
                    )

                # Record webhook event for deduplication with truthful signature_verified
                with self.db._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO payment_webhook_events (
                            id, organization_id, provider, event_id, event_type, idempotency_key,
                            payload_json, payload_hash, signature_verified, status, payment_id, processed_at, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PROCESSED', ?, ?, ?);
                        """,
                        (
                            webhook_id,
                            organization_id,
                            provider,
                            event_id,
                            event_type,
                            idempotency_key,
                            raw_payload_json,
                            payload_hash,
                            1 if is_verified else 0,
                            payment_id,
                            now,
                            now,
                        ),
                    )

            return {
                "status": "PROCESSED",
                "is_duplicate": False,
                "payment_id": payment_id,
                "receipt_number": receipt_number,
            }
        except sqlite3.IntegrityError:
            # Race condition during concurrent duplicate delivery; retrieve existing event
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, status, payment_id FROM payment_webhook_events
                    WHERE organization_id = ? AND provider = ? AND event_id = ?;
                    """,
                    (organization_id, provider, event_id),
                )
                existing = cursor.fetchone()
                if existing:
                    return {
                        "status": "PROCESSED",
                        "is_duplicate": True,
                        "event_id": event_id,
                        "payment_id": existing[2],
                    }
            raise

    def get_receipt(self, organization_id: str, receipt_id_or_number: str) -> Optional[Dict[str, Any]]:
        """Retrieve persisted receipt with payment, student, and tenant isolation metadata."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.id, r.payment_id, r.receipt_number, r.amount, r.issued_to, r.issued_at,
                       r.notes, r.created_at, p.org_id, p.student_id, p.invoice_id,
                       p.payment_method, p.transaction_reference, p.status
                FROM receipts r
                JOIN payments p ON r.payment_id = p.id
                WHERE (r.id = ? OR r.receipt_number = ?)
                  AND r.is_deleted = 0
            """
            params = [receipt_id_or_number, receipt_id_or_number]
            if organization_id:
                query += " AND p.org_id = ?"
                params.append(organization_id)
            cursor.execute(query, tuple(params))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row[0],
                "payment_id": row[1],
                "receipt_number": row[2],
                "amount": float(row[3]),
                "issued_to": row[4],
                "issued_at": row[5],
                "notes": row[6] or "",
                "created_at": row[7],
                "organization_id": row[8],
                "student_id": row[9],
                "invoice_id": row[10],
                "payment_method": row[11],
                "transaction_reference": row[12],
                "payment_status": row[13],
            }

    # ── Append-Only Financial Ledger ──────────────────────────────────────────

    def post_ledger_entry(
        self,
        organization_id: str,
        account_id: str,
        entry_type: LedgerEntryType,
        amount: float,
        description: str,
        invoice_id: Optional[str] = None,
        payment_id: Optional[str] = None,
    ) -> FinancialLedgerEntry:
        now = self._now()
        entry_id = f"fle-{uuid.uuid4().hex[:12]}"
        et_val = entry_type.value if hasattr(entry_type, "value") else str(entry_type)

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO financial_ledger_entries (
                    id, organization_id, account_id, invoice_id, payment_id, entry_type,
                    amount, description, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    entry_id,
                    organization_id,
                    account_id,
                    invoice_id,
                    payment_id,
                    et_val,
                    amount,
                    description,
                    now,
                ),
            )

        return FinancialLedgerEntry(
            id=entry_id,
            organization_id=organization_id,
            account_id=account_id,
            entry_type=LedgerEntryType(et_val) if et_val in LedgerEntryType._value2member_map_ else LedgerEntryType.DEBIT,
            amount=amount,
            description=description,
            invoice_id=invoice_id,
            payment_id=payment_id,
            balance_after=None,
            created_at=now,
        )

    def get_account_ledger(self, organization_id: str, account_id: str) -> List[FinancialLedgerEntry]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, account_id, invoice_id, payment_id, entry_type,
                       amount, balance_after, description, created_at
                FROM financial_ledger_entries
                WHERE account_id = ? AND organization_id = ?
                ORDER BY created_at ASC;
                """,
                (account_id, organization_id),
            )
            rows = cursor.fetchall()

        return [
            FinancialLedgerEntry(
                id=r[0],
                organization_id=r[1],
                account_id=r[2],
                invoice_id=r[3],
                payment_id=r[4],
                entry_type=LedgerEntryType(r[5]) if r[5] in LedgerEntryType._value2member_map_ else LedgerEntryType.DEBIT,
                amount=float(r[6]),
                balance_after=float(r[7]) if r[7] is not None else None,
                description=r[8],
                created_at=r[9],
            )
            for r in rows
        ]

    def calculate_ledger_balance(self, organization_id: str, account_id: str) -> float:
        entries = self.get_account_ledger(organization_id, account_id)
        balance = 0.0
        for e in entries:
            if e.entry_type == LedgerEntryType.DEBIT:
                balance += e.amount
            elif e.entry_type == LedgerEntryType.CREDIT:
                balance -= e.amount
        return round(balance, 2)

    # ── Reconciliation Engine ─────────────────────────────────────────────────

    def execute_reconciliation(
        self,
        organization_id: str,
        run_date: str,
        provider: str,
        total_expected: float,
        total_settled: float,
        reconciled_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ReconciliationRecord:
        now = self._now()
        rec_id = f"rcn-{uuid.uuid4().hex[:12]}"
        discrepancy = round(abs(total_expected - total_settled), 2)
        rec_status = ReconciliationStatus.RESOLVED if discrepancy == 0.0 else ReconciliationStatus.DISCREPANCY_FLAGGED

        with self.db._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reconciliation_records (
                    id, organization_id, run_date, provider, total_expected, total_settled,
                    discrepancy_amount, status, notes, reconciled_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    rec_id,
                    organization_id,
                    run_date,
                    provider,
                    total_expected,
                    total_settled,
                    discrepancy,
                    rec_status.value,
                    notes,
                    reconciled_by,
                    now,
                ),
            )

        return ReconciliationRecord(
            id=rec_id,
            organization_id=organization_id,
            run_date=run_date,
            provider=provider,
            total_expected=total_expected,
            total_settled=total_settled,
            discrepancy_amount=discrepancy,
            status=rec_status,
            notes=notes,
            reconciled_by=reconciled_by,
            created_at=now,
        )

    def list_reconciliation_records(self, organization_id: str) -> List[ReconciliationRecord]:
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, organization_id, run_date, provider, total_expected, total_settled,
                       discrepancy_amount, status, notes, reconciled_by, created_at
                FROM reconciliation_records
                WHERE organization_id = ?
                ORDER BY run_date DESC;
                """,
                (organization_id,),
            )
            rows = cursor.fetchall()

        return [
            ReconciliationRecord(
                id=r[0],
                organization_id=r[1],
                run_date=r[2],
                provider=r[3],
                total_expected=float(r[4]),
                total_settled=float(r[5]),
                discrepancy_amount=float(r[6]),
                status=ReconciliationStatus(r[7]) if r[7] in ReconciliationStatus._value2member_map_ else ReconciliationStatus.RESOLVED,
                notes=r[8],
                reconciled_by=r[9],
                created_at=r[10],
            )
            for r in rows
        ]
