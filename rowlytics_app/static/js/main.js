(function () {
  const ctaForm = document.querySelector('.cta-form');
  if (!ctaForm) return;

  ctaForm.addEventListener('submit', function (event) {
    const button = ctaForm.querySelector('button[type="submit"]');
    if (button) {
      button.textContent = 'Sending…';
      button.disabled = true;
    }
    setTimeout(() => {
      if (button) {
        button.textContent = 'Book a call';
        button.disabled = false;
      }
    }, 2000);
  });
})();
