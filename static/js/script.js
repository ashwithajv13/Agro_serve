// Opens and closes the menu on small screens (the full navbar shows on desktop).
const toggle = document.getElementById("navToggle");
const links = document.getElementById("navLinks");
toggle.addEventListener("click", () => links.classList.toggle("open"));
