document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".service-card").forEach(card => {
    const img = card.dataset.img;
    card.style.backgroundImage = `url('/static/knopki/${img}')`;
  });
});
