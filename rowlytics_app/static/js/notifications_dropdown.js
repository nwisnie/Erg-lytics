(() => {
  const dropdown = document.getElementById("notificationsDropdown");
  const trigger = document.querySelector("[data-notifications-open]");

  if (!dropdown || !trigger) return;

  const isOpen = () => dropdown.getAttribute("aria-hidden") === "false";

  const openDropdown = () => {
    dropdown.setAttribute("aria-hidden", "false");
  };

  const closeDropdown = () => {
    dropdown.setAttribute("aria-hidden", "true");
  };

  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();

    if (isOpen()) {
      closeDropdown();
    } else {
      openDropdown();
    }
  });

  dropdown.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.addEventListener("click", () => {
    closeDropdown();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeDropdown();
    }
  });
})();
