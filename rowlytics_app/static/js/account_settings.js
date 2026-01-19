(() => {
  const form = document.getElementById("accountNameForm");
  const nameInput = document.getElementById("accountName");
  const message = document.getElementById("accountMessage");
  const deleteBtn = document.getElementById("deleteAccountBtn");
  const confirmWrap = document.getElementById("accountDeleteConfirm");
  const confirmBtn = document.getElementById("confirmDeleteAccount");
  const cancelBtn = document.getElementById("cancelDeleteAccount");

  if (!form || !nameInput || !message) return;

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("team-message--error", "team-message--success");
    if (tone === "error") message.classList.add("team-message--error");
    if (tone === "success") message.classList.add("team-message--success");
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
      const response = await fetch("/api/account/name", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to update name");
      }
      nameInput.value = data.name || name;
      setMessage("Name updated.", "success");
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
        const response = await fetch("/api/account/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Unable to delete account");
        }
        window.location = "/signin";
      } catch (err) {
        setMessage(err.message || "Unable to delete account", "error");
        confirmBtn.disabled = false;
        cancelBtn.disabled = false;
      }
    });
  }
})();
