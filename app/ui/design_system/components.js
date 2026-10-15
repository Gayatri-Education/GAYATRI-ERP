/**
 * Gayatri AI Platform — Shared UI Component Controller (Phase 24)
 * Provides client-side helpers for theme switching, toast alerts, modals,
 * tabs, drawers, skeletons, and chat components.
 */

window.GayatriUI = (function () {
  'use strict';

  // 1. Theme Management
  function setTheme(theme) {
    const validTheme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', validTheme);
    document.body.classList.remove('theme-dark', 'theme-light');
    document.body.classList.add(`theme-${validTheme}`);
    try {
      localStorage.setItem('gayatri_theme', validTheme);
    } catch (e) {}
  }

  function getTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  function toggleTheme() {
    const current = getTheme();
    const next = current === 'dark' ? 'light' : 'dark';
    setTheme(next);
    return next;
  }

  // 2. Toast Notifications
  function showToast(message, type = 'info', durationMs = 3500) {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${escapeHtml(message)}</span>
      <button class="btn btn-ghost btn-sm" onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.remove();
    }, durationMs);
  }

  // 3. Modal Control
  function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
    }
  }

  function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
    }
  }

  // 4. Drawer Control
  function openDrawer(drawerId) {
    const drawer = document.getElementById(drawerId);
    if (drawer) {
      drawer.classList.add('active');
    }
  }

  function closeDrawer(drawerId) {
    const drawer = document.getElementById(drawerId);
    if (drawer) {
      drawer.classList.remove('active');
    }
  }

  // 5. Tab Selection
  function selectTab(tabListId, targetTabId) {
    const tabList = document.getElementById(tabListId);
    if (!tabList) return;

    const tabs = tabList.querySelectorAll('.tab-item');
    tabs.forEach((tab) => {
      if (tab.getAttribute('data-tab') === targetTabId) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });

    const panels = document.querySelectorAll(`[data-tab-group="${tabListId}"]`);
    panels.forEach((panel) => {
      if (panel.id === targetTabId) {
        panel.classList.add('active');
      } else {
        panel.classList.remove('active');
      }
    });
  }

  // Helper: HTML escaping
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // Auto-init theme from localStorage
  document.addEventListener('DOMContentLoaded', () => {
    try {
      const saved = localStorage.getItem('gayatri_theme');
      if (saved) {
        setTheme(saved);
      }
    } catch (e) {}
  });

  return {
    setTheme,
    getTheme,
    toggleTheme,
    showToast,
    openModal,
    closeModal,
    openDrawer,
    closeDrawer,
    selectTab,
    escapeHtml,
  };
})();
