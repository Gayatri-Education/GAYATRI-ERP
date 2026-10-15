/**
 * Gayatri AI Platform — Teacher Portal UI Controller (Phase 28)
 * Controls tab switching for Class Overview, Students, Learning Health,
 * Student Profile, Interventions, Assessments, Teacher Instructions, and AI Copilot.
 */

window.GayatriTeacher = (function () {
  'use strict';

  let currentTab = 'class_overview';

  // 1. Switch Tab
  function switchTeacherTab(tabName) {
    const validTabs = [
      'class_overview', 'students', 'learning_health', 'student_profile',
      'interventions', 'assessments', 'teacher_instructions', 'ai_copilot'
    ];
    if (!validTabs.includes(tabName)) return;

    currentTab = tabName;

    // Update tab buttons
    const buttons = document.querySelectorAll('.teacher-tab-btn');
    buttons.forEach((btn) => {
      if (btn.getAttribute('data-tab') === tabName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update view panels
    const views = document.querySelectorAll('.teacher-view-panel');
    views.forEach((panel) => {
      if (panel.id === `teacher-view-${tabName}`) {
        panel.style.display = 'block';
      } else {
        panel.style.display = 'none';
      }
    });
  }

  // 2. Render Functions
  function renderClassOverview(data) {
    const container = document.querySelector('.class-overview-grid');
    if (!container || !data) return;

    container.innerHTML = `
      <div class="cohort-stat-card">
        <div class="stat-value">${parseInt(data.enrolled_count, 10) || 0}</div>
        <div class="stat-label">Enrolled Students</div>
      </div>
      <div class="cohort-stat-card">
        <div class="stat-value">${parseFloat(data.average_mastery_pct) || 0}%</div>
        <div class="stat-label">Average Cohort Mastery</div>
      </div>
      <div class="cohort-stat-card">
        <div class="stat-value">${parseInt(data.at_risk_count, 10) || 0}</div>
        <div class="stat-label">At-Risk Students</div>
      </div>
      <div class="cohort-stat-card">
        <div class="stat-value">${parseInt(data.active_interventions, 10) || 0}</div>
        <div class="stat-label">Active Interventions</div>
      </div>
    `;
  }

  async function triggerCopilotAnalysis(courseId) {
    if (window.GayatriUI) {
      window.GayatriUI.showToast("AI Copilot analyzing cohort learning health...", "info");
    }
    try {
      const url = courseId
        ? `/api/v1/teachers/copilot/briefing?course_id=${encodeURIComponent(courseId)}`
        : '/api/v1/teachers/copilot/briefing';
      const resp = await fetch(url, {
        headers: { 'Accept': 'application/json' }
      });
      if (!resp.ok) {
        if (window.GayatriUI) {
          window.GayatriUI.showToast("Unable to retrieve AI Copilot analysis from backend.", "error");
        }
        return null;
      }
      const data = await resp.json();
      const briefing = data.data || data;

      // Update Copilot UI panel if present
      const panel = document.querySelector('.copilot-panel') || document.querySelector('#teacher-view-ai_copilot');
      if (panel) {
        const recText = briefing.recommended_action || briefing.summary || "Cohort analysis completed with active monitoring.";
        const safeText = window.GayatriUI ? window.GayatriUI.escapeHtml(recText) : recText;
        const recEl = panel.querySelector('.copilot-rec');
        if (recEl) {
          recEl.innerHTML = `<strong>💡 Copilot Pedagogical Recommendation:</strong> ${safeText}`;
        }
      }

      if (window.GayatriUI) {
        window.GayatriUI.showToast("AI Copilot analysis completed successfully.", "success");
      }
      return briefing;
    } catch (e) {
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Copilot analysis error: ${e.message}`, "error");
      }
      return null;
    }
  }

  return {
    switchTeacherTab,
    renderClassOverview,
    triggerCopilotAnalysis,
  };
})();
