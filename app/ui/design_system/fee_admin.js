/**
 * Gayatri AI Platform — Fee Administration UI Controller (Phase 31)
 * Manages tab switching, fee structure management, monthly billing generation,
 * student ledger viewing, payment recording, receipt printing, and CSV export.
 */

window.GayatriFeeAdmin = (function () {
  'use strict';

  let currentTab = 'fee_setup';

  // 1. Switch Tab
  function switchTab(tabName) {
    const validTabs = [
      'fee_setup',
      'monthly_billing',
      'student_accounts',
      'record_payment',
      'receipts',
      'outstanding_reports'
    ];
    if (!validTabs.includes(tabName)) return;

    currentTab = tabName;

    // Update tab buttons
    const buttons = document.querySelectorAll('.fee-admin-tab-btn');
    buttons.forEach((btn) => {
      if (btn.getAttribute('data-tab') === tabName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update panels
    const panels = document.querySelectorAll('.fee-admin-panel');
    panels.forEach((panel) => {
      if (panel.id === `fee-panel-${tabName}`) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });
  }

  // 2. Trigger Batch Monthly Billing
  async function generateMonthlyBilling(monthYear) {
    if (window.GayatriUI) {
      window.GayatriUI.showToast(`Initiating batch monthly billing for ${monthYear}...`, 'info');
    }
    try {
      const resp = await fetch('/api/v1/finance/billing/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ month_year: monthYear })
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Batch billing request failed' }));
        if (window.GayatriUI) {
          window.GayatriUI.showToast(`Batch billing failed: ${err.detail || resp.statusText}`, 'error');
        }
        return null;
      }
      const data = await resp.json();
      if (window.GayatriUI) {
        window.GayatriUI.showToast(
          `Batch monthly billing completed for ${monthYear}: ${data.invoices_generated || 0} invoices generated.`,
          'success'
        );
      }
      return data;
    } catch (e) {
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Network error initiating monthly billing: ${e.message}`, 'error');
      }
      return null;
    }
  }

  // 3. Export Outstanding Report CSV
  async function exportOutstandingReport() {
    if (window.GayatriUI) {
      window.GayatriUI.showToast('Exporting Outstanding Fee Report (CSV)...', 'info');
    }
    try {
      const resp = await fetch('/api/v1/finance/reports/outstanding/export', {
        headers: { 'Accept': 'text/csv' }
      });
      if (!resp.ok) {
        if (window.GayatriUI) {
          window.GayatriUI.showToast('Failed to export outstanding fee report.', 'error');
        }
        return;
      }
      const csvBlob = await resp.blob();
      const downloadUrl = window.URL.createObjectURL(csvBlob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = 'outstanding_fee_report.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
      if (window.GayatriUI) {
        window.GayatriUI.showToast('Outstanding Fee Report exported successfully.', 'success');
      }
    } catch (e) {
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Export error: ${e.message}`, 'error');
      }
    }
  }

  // 4. Print Receipt
  async function printReceipt(receiptId) {
    if (!receiptId) {
      window.print();
      return;
    }
    try {
      const resp = await fetch(`/api/v1/finance/receipts/${encodeURIComponent(receiptId)}`, {
        headers: { 'Accept': 'application/json' }
      });
      if (!resp.ok) {
        if (window.GayatriUI) {
          window.GayatriUI.showToast(`Unable to verify persisted receipt ${receiptId}`, 'error');
        }
        return;
      }
      const receiptData = await resp.json();
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Verified receipt ${receiptData.receipt_number || receiptId}. Printing...`, 'success');
      }
      window.print();
    } catch (e) {
      window.print();
    }
  }

  return {
    switchTab,
    generateMonthlyBilling,
    exportOutstandingReport,
    printReceipt
  };
})();
