(() => {
  const modal = document.getElementById("profileModal");
  const triggers = document.querySelectorAll(".profile-link");
  const nameValue = document.getElementById("profileNameValue");
  const emailValue = document.getElementById("profileEmailValue");
  const userIdValue = document.getElementById("profileUserIdValue");
  if (!modal || triggers.length === 0) return;

  const closeTriggers = modal.querySelectorAll("[data-profile-close]");
  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");

  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
  };

  const setProfileValues = ({ name, email, userId }) => {
    if (nameValue) {
      nameValue.textContent = name || "Not set";
    }
    if (emailValue) {
      emailValue.textContent = email || "Not set";
    }
    if (userIdValue) {
      userIdValue.textContent = userId || "Not set";
    }
  };

  const refreshProfile = async () => {
    try {
      const response = await fetch(getApiUrl("/api/account/profile"));
      const data = await response.json();
      if (!response.ok) {
        return;
      }
      setProfileValues(data);
    } catch (_error) {
      // Keep the existing rendered values if the refresh fails.
    }
  };

  const openModal = () => {
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  };

  const closeModal = () => {
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", async (event) => {
      event.preventDefault();
      await refreshProfile();
      openModal();
    });
  });

  closeTriggers.forEach((trigger) => {
    trigger.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeModal();
    }
  });
})();
