// Shared behaviour for every page.

document.addEventListener("DOMContentLoaded", () => {
  // 1. Show flash messages as Bootstrap toasts.
  document.querySelectorAll("#toastArea .toast").forEach((el) => {
    // Success/info messages fade after 5 s; errors and warnings stay until the user closes them.
    const sticky = el.classList.contains("toast-danger") || el.classList.contains("toast-warning");
    new bootstrap.Toast(el, { delay: 5000, autohide: !sticky }).show();
  });

  // 2. Forms marked data-loading-form show a spinner on submit (stops double clicks).
  document.querySelectorAll("form[data-loading-form]").forEach((form) => {
    form.addEventListener("submit", () => {
      const btn = form.querySelector("button[type=submit]");
      if (btn) {
        btn.classList.add("is-loading");
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Please wait…';
      }
    });
  });

  // 3. Mobile sidebar drawer.
  const sidebar = document.getElementById("sidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  const toggle = document.getElementById("sidebarToggle");
  if (sidebar && toggle && backdrop) {
    const setOpen = (open) => {
      sidebar.classList.toggle("open", open);
      backdrop.classList.toggle("show", open);
    };
    toggle.addEventListener("click", () => setOpen(!sidebar.classList.contains("open")));
    backdrop.addEventListener("click", () => setOpen(false));
  }

  // 3b. The top-bar search box filters whatever list/table rows are on the current page.
  const pageSearch = document.getElementById("pageSearch");
  if (pageSearch) {
    pageSearch.addEventListener("input", () => {
      const term = pageSearch.value.trim().toLowerCase();
      document.querySelectorAll(".item-list li, .data-table tbody tr, [data-searchable]").forEach((row) => {
        row.style.display = !term || row.textContent.toLowerCase().includes(term) ? "" : "none";
      });
    });
  }

  // 4. Any button with data-confirm asks before submitting (used for deletes later).
  document.querySelectorAll("[data-confirm]").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (!window.confirm(el.dataset.confirm)) e.preventDefault();
    });
  });
});

// Helper other scripts can use: the CSRF token for fetch() calls.
window.csrfToken = () => document.querySelector('meta[name="csrf-token"]').content;
