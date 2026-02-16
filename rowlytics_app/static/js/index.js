(function () {
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    const url = `${stage}/api/count/capture-workout`;
    fetch(url)
      .then(r => r.ok ? r.json() : Promise.reject(new Error(r.statusText || "error")))
      .then(data => {
        const el = document.getElementById("cw-views");
        if (el && data && typeof data.count === "number") {
          el.textContent = data.count;
        }
      })
      .catch(() => {});
  })();
