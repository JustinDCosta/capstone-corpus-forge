/* ============================================================
   Corpus Forge presentation — slide controller
   - Keyboard navigation (←/→/Space/Home/End/F/O/Esc)
   - Click on left/right edge to navigate
   - Fullscreen toggle
   - Overview grid (press O)
   - URL hash sync (?#3 jumps to slide 3)
   ============================================================ */

(function () {
  "use strict";

  const slides = Array.from(document.querySelectorAll(".slide"));
  const total = slides.length;
  const totalEl = document.getElementById("total");
  const curEl = document.getElementById("cur");
  const speakerTag = document.getElementById("speakerTag");
  const prevBtn = document.getElementById("prevBtn");
  const nextBtn = document.getElementById("nextBtn");
  const fullBtn = document.getElementById("fullBtn");
  const overviewBtn = document.getElementById("overviewBtn");
  const overviewPane = document.getElementById("overviewPane");
  const overviewGrid = document.getElementById("overviewGrid");

  let current = 0;

  totalEl.textContent = total;

  // ---------- Render slide ----------
  function show(index) {
    if (index < 0) index = 0;
    if (index >= total) index = total - 1;
    slides.forEach((s, i) => s.classList.toggle("active", i === index));
    current = index;
    curEl.textContent = index + 1;
    const speaker = slides[index].dataset.speaker || "—";
    speakerTag.innerHTML = `Speaker: <span>${speaker}</span>`;
    // Sync URL hash so browser back/forward + bookmarks work.
    if (window.location.hash !== `#${index + 1}`) {
      history.replaceState(null, "", `#${index + 1}`);
    }
  }

  function next() { show(current + 1); }
  function prev() { show(current - 1); }
  function first() { show(0); }
  function last() { show(total - 1); }

  // ---------- Build overview thumbnails ----------
  function buildOverview() {
    overviewGrid.innerHTML = "";
    slides.forEach((slide, i) => {
      const titleEl =
        slide.querySelector(".hero-title") ||
        slide.querySelector("h2") ||
        slide.querySelector(".demo-title");
      const title = titleEl ? titleEl.textContent.trim() : `Slide ${i + 1}`;
      const speaker = slide.dataset.speaker || "—";

      const thumb = document.createElement("div");
      thumb.className = "overview-thumb";
      thumb.innerHTML = `
        <div class="ot-num">${String(i + 1).padStart(2, "0")} · ${speaker}</div>
        <div class="ot-title">${title}</div>
      `;
      thumb.addEventListener("click", () => {
        overviewPane.classList.remove("visible");
        show(i);
      });
      overviewGrid.appendChild(thumb);
    });
  }

  function toggleOverview() {
    overviewPane.classList.toggle("visible");
  }

  // ---------- Fullscreen ----------
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
  }

  // ---------- Wiring ----------
  prevBtn.addEventListener("click", prev);
  nextBtn.addEventListener("click", next);
  fullBtn.addEventListener("click", toggleFullscreen);
  overviewBtn.addEventListener("click", toggleOverview);

  // Keyboard
  document.addEventListener("keydown", (e) => {
    // Ignore typing in inputs (we don't have any, but future-proof).
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

    switch (e.key) {
      case "ArrowRight":
      case "PageDown":
      case " ":
        e.preventDefault();
        next();
        break;
      case "ArrowLeft":
      case "PageUp":
        e.preventDefault();
        prev();
        break;
      case "Home":
        e.preventDefault();
        first();
        break;
      case "End":
        e.preventDefault();
        last();
        break;
      case "f":
      case "F":
        toggleFullscreen();
        break;
      case "o":
      case "O":
        toggleOverview();
        break;
      case "Escape":
        if (overviewPane.classList.contains("visible")) {
          overviewPane.classList.remove("visible");
        }
        break;
    }
  });

  // Click left / right thirds to navigate (skip when clicking interactive UI).
  document.addEventListener("click", (e) => {
    if (e.target.closest(".hud, .speaker-tag, .overview-pane, .nav-btn")) return;
    const w = window.innerWidth;
    if (e.clientX < w * 0.25) prev();
    else if (e.clientX > w * 0.75) next();
  });

  // Touch swipe
  let touchStartX = 0;
  document.addEventListener("touchstart", (e) => {
    touchStartX = e.changedTouches[0].screenX;
  }, { passive: true });
  document.addEventListener("touchend", (e) => {
    const dx = e.changedTouches[0].screenX - touchStartX;
    if (Math.abs(dx) < 50) return;
    if (dx < 0) next(); else prev();
  }, { passive: true });

  // Initial slide from hash (e.g. ?#5)
  const hash = parseInt(window.location.hash.replace("#", ""), 10);
  const startIndex = !isNaN(hash) && hash >= 1 && hash <= total ? hash - 1 : 0;

  buildOverview();
  show(startIndex);
})();
