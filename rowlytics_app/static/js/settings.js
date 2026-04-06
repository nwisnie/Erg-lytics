(() => {
  const form = document.getElementById("accountNameForm");
  const nameInput = document.getElementById("accountName");
  const message = document.getElementById("accountMessage");
  const deleteBtn = document.getElementById("deleteAccountBtn");
  const confirmWrap = document.getElementById("accountDeleteConfirm");
  const confirmBtn = document.getElementById("confirmDeleteAccount");
  const cancelBtn = document.getElementById("cancelDeleteAccount");
  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
  const updateNameUrl = document.body?.dataset?.accountNameUrl || "";
  const deleteAccountUrl = document.body?.dataset?.accountDeleteUrl || "";
  const homeUrl = document.body?.dataset?.homeUrl || "/";
  const signinUrl = document.body?.dataset?.signinUrl || "/signin";
  const requireDisplayName = document.body?.dataset?.requireDisplayName === "true";

  if (!form || !nameInput || !message) return;

  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
  };

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("team-message--error", "team-message--success");
    if (tone === "error") message.classList.add("team-message--error");
    if (tone === "success") message.classList.add("team-message--success");
  };

  const updateProfileName = (name) => {
    const profileNameValue = document.getElementById("profileNameValue");
    if (profileNameValue) {
      profileNameValue.textContent = name || "Not set";
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = nameInput.value.trim();
    if (!name) {
      setMessage("Enter a display name.", "error");
      return;
    }

      setMessage("Saving...", "info");
    try {
      const response = await fetch(updateNameUrl || getApiUrl("/api/account/name"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || data.error || "Unable to update name");
      }
      nameInput.value = data.name || name;
      updateProfileName(data.name || name);
      setMessage("Name updated.", "success");
      if (requireDisplayName) {
        window.location = homeUrl;
        return;
      }
    } catch (err) {
      setMessage(err.message || "Unable to update name", "error");
    }
  });

  if (deleteBtn && confirmWrap && confirmBtn && cancelBtn) {
    deleteBtn.addEventListener("click", () => {
      confirmWrap.classList.remove("account-delete--hidden");
      deleteBtn.classList.add("account-delete--hidden");
    });

    cancelBtn.addEventListener("click", () => {
      confirmWrap.classList.add("account-delete--hidden");
      deleteBtn.classList.remove("account-delete--hidden");
    });

    confirmBtn.addEventListener("click", async () => {
      setMessage("Deleting account...", "info");
      confirmBtn.disabled = true;
      cancelBtn.disabled = true;

      try {
        const response = await fetch(deleteAccountUrl || getApiUrl("/api/account/delete"), {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail || data.error || "Unable to delete account");
        }
        window.location = signinUrl;
      } catch (err) {
        setMessage(err.message || "Unable to delete account", "error");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      }
    });
  }
})();
