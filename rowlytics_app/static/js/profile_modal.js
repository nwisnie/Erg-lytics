(() => {
  const modal = document.getElementById("profileModal");
  const triggers = document.querySelectorAll(".profile-link");
  if (!modal || triggers.length === 0) return;

  const closeTriggers = modal.querySelectorAll("[data-profile-close]");

  const openModal = () => {
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("modal-open");
  };

  const closeModal = () => {
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("modal-open");
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
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
