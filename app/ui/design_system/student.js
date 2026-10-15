/**
 * Gayatri AI Platform — Student Portal UI Controller (Phase 27)
 * Controls tab switching for Dashboard, Curriculum, Learning Graph, Progress,
 * Review Queue, Assignments, Assessments, Activity Stream, Profile, and Notifications.
 */

window.GayatriStudent = (function () {
  'use strict';

  let currentTab = 'dashboard';

  // 1. Switch Tab
  function switchStudentTab(tabName) {
    const validTabs = [
      'dashboard', 'curriculum', 'learning_graph', 'progress',
      'review_queue', 'assignments', 'assessments', 'activity',
      'profile', 'notifications'
    ];
    if (!validTabs.includes(tabName)) return;

    currentTab = tabName;

    // Update tab buttons
    const buttons = document.querySelectorAll('.student-tab-btn');
    buttons.forEach((btn) => {
      if (btn.getAttribute('data-tab') === tabName) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    // Update view panels
    const views = document.querySelectorAll('.student-view-panel');
    views.forEach((panel) => {
      if (panel.id === `view-${tabName}`) {
        panel.style.display = 'block';
      } else {
        panel.style.display = 'none';
      }
    });
  }

  // 2. Render Functions
  function renderDashboardStats(stats) {
    const container = document.querySelector('.student-dashboard-grid');
    if (!container || !stats) return;

    container.innerHTML = `
      <div class="stat-card">
        <div class="stat-value">${parseInt(stats.mastery_pct, 10) || 0}%</div>
        <div class="stat-label">Overall Concept Mastery</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${parseInt(stats.review_due_count, 10) || 0}</div>
        <div class="stat-label">Review Items Due</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${parseInt(stats.assignments_pending, 10) || 0}</div>
        <div class="stat-label">Pending Assignments</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">${parseInt(stats.streak_days, 10) || 0} Days</div>
        <div class="stat-label">Learning Streak</div>
      </div>
    `;
  }

  function renderReviewQueue(items) {
    const list = document.querySelector('.review-queue-list');
    if (!list || !Array.isArray(items)) return;

    if (items.length === 0) {
      list.innerHTML = `<div class="empty-state"><div class="empty-state-title">No review items due!</div></div>`;
      return;
    }

    list.innerHTML = items.map(item => {
      const safeName = window.GayatriUI ? window.GayatriUI.escapeHtml(item.concept_name) : item.concept_name;
      const safeId = window.GayatriUI ? window.GayatriUI.escapeHtml(item.concept_id) : item.concept_id;
      const retainPct = Math.round((Number(item.retainability) || 0) * 100);
      return `
        <div class="review-item-card">
          <div>
            <strong>${safeName}</strong>
            <div class="caption">Retainability: ${retainPct}%</div>
          </div>
          <button class="btn btn-primary btn-sm review-now-btn" data-concept-id="${safeId}">Review Now</button>
        </div>
      `;
    }).join('');

    // Attach safe event listener via querySelectorAll
    list.querySelectorAll('.review-now-btn').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        const conceptId = e.currentTarget.getAttribute('data-concept-id');
        startReview(conceptId);
      });
    });
  }

  async function startReview(conceptId, studentId, courseId) {
    if (!conceptId) return;
    if (window.GayatriUI) {
      window.GayatriUI.showToast(`Starting review session for ${conceptId}...`, 'info');
    }
    const resolvedStudentId = studentId || 'current';
    try {
      const resp = await fetch(`/api/v1/students/${encodeURIComponent(resolvedStudentId)}/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({
          action_type: 'review_start',
          concept_id: conceptId,
          course_id: courseId || 'crs-chem-101'
        })
      });
      if (!resp.ok) {
        if (window.GayatriUI) {
          window.GayatriUI.showToast(`Unable to record review session on server (${resp.status})`, 'error');
        }
        return null;
      }
      const data = await resp.json();
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Review session started for ${conceptId}`, 'success');
      }
      return data;
    } catch (e) {
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Network error starting review: ${e.message}`, 'error');
      }
      return null;
    }
  }

  async function loadReviewQueue(studentId, courseId) {
    const resolvedStudentId = studentId || 'current';
    try {
      const url = courseId
        ? `/api/v1/students/${encodeURIComponent(resolvedStudentId)}/review-queue?course_id=${encodeURIComponent(courseId)}`
        : `/api/v1/students/${encodeURIComponent(resolvedStudentId)}/review-queue`;
      const resp = await fetch(url, {
        headers: { 'Accept': 'application/json' }
      });
      if (!resp.ok) {
        if (window.GayatriUI) {
          window.GayatriUI.showToast(`Unable to load review queue (${resp.status})`, 'error');
        }
        return [];
      }
      const data = await resp.json();
      const items = data.data || [];
      renderReviewQueue(items);
      return items;
    } catch (e) {
      if (window.GayatriUI) {
        window.GayatriUI.showToast(`Error fetching review queue: ${e.message}`, 'error');
      }
      return [];
    }
  }

  return {
    switchStudentTab,
    renderDashboardStats,
    renderReviewQueue,
    startReview,
    loadReviewQueue,
  };
})();

