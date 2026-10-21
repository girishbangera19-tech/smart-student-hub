// Dashboard-only behaviour: progress charts and task check-boxes.

document.addEventListener("DOMContentLoaded", () => {
  // ---- Charts (data comes from the server as JSON) ----
  const dataEl = document.getElementById("chart-data");
  if (dataEl && window.Chart) {
    const data = JSON.parse(dataEl.textContent);
    const css = getComputedStyle(document.documentElement);
    const color = (name) => css.getPropertyValue(name).trim();
    const options = {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "68%",
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true, color: color("--text-muted") } } },
    };

    const assignmentCanvas = document.getElementById("assignmentChart");
    if (assignmentCanvas) {
      new Chart(assignmentCanvas, {
        type: "doughnut",
        data: {
          labels: ["Completed", "Open", "Overdue"],
          datasets: [{ data: data.assignments, backgroundColor: [color("--success"), color("--secondary"), color("--danger")], borderWidth: 0 }],
        },
        options,
      });
    }

    const taskCanvas = document.getElementById("taskChart");
    if (taskCanvas) {
      new Chart(taskCanvas, {
        type: "doughnut",
        data: {
          labels: ["Completed", "Remaining"],
          datasets: [{ data: data.tasks, backgroundColor: [color("--success"), color("--border")], borderWidth: 0 }],
        },
        options,
      });
    }
  }

  // ---- Task check-boxes: POST to the server, then reload so every number updates ----
  document.querySelectorAll(".task-check[data-url]").forEach((box) => {
    box.addEventListener("change", async () => {
      box.disabled = true;
      try {
        const res = await fetch(box.dataset.url, {
          method: "POST",
          headers: { "X-CSRFToken": window.csrfToken(), "X-Requested-With": "fetch" },
        });
        if (!res.ok) throw new Error("Request failed");
        window.location.reload();
      } catch (err) {
        box.checked = !box.checked;
        box.disabled = false;
        alert("Could not update the task. Please try again.");
      }
    });
  });
});
