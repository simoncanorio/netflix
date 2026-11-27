/**
 * NETFLIX GLOBAL STREAMING, GRAPH AI & EXECUTIVE ANALYTICS (CLIENT ENGINE v4.0)
 * - Desambiguación canónica de títulos homónimos
 * - Descripciones, géneros y episodios traducidos al español (es-ES)
 * - Sección 'Mi Lista' con recomendador dedicado
 * - Actualización sutil y no intrusiva de carruseles (off-viewport / cross-fade)
 * - Tráilers de YouTube embebidos, Hook Episode Analysis, Contextual Bandit y Matriz de Doblaje
 */

const PERSONAL_BASE_ID = "session_" + (localStorage.getItem("netflix_user_id") || (() => {
  const id = Math.random().toString(36).substring(2, 9);
  localStorage.setItem("netflix_user_id", id);
  return id;
})());

const PERSONA_META = {
  custom: { sessionId: PERSONAL_BASE_ID, name: "Tu Perfil", avatar: "🎬", bg: "#e50914" },
  persona_kdrama_anime: { sessionId: "persona_kdrama_anime", name: "K-Drama & Anime", avatar: "🐉", bg: "#b81d24" },
  persona_cine_ar_eu: { sessionId: "persona_cine_ar_eu", name: "Cine AR & Autor", avatar: "🎭", bg: "#1f7a3f" },
  persona_nuevo_cero: { sessionId: "persona_nuevo_cero", name: "Invitado (0 pts)", avatar: "✨", bg: "#8a6d0b" }
};

const SAVED_PERSONA_KEY = localStorage.getItem("netflix_active_persona") || "custom";

const CONFIG = {
  MIN_HOVER_DWELL_MS: 800,
  API_BASE: "",
  ACTIVE_PERSONA: PERSONA_META[SAVED_PERSONA_KEY] ? SAVED_PERSONA_KEY : "custom",
  SESSION_ID: (PERSONA_META[SAVED_PERSONA_KEY] || PERSONA_META.custom).sessionId
};

let STATE = {
  activeSection: "home",
  isSearching: false,
  infinitePage: 1,
  isLoadingInfinite: false,
  businessDataCache: null,
  pendingRecData: null,
  currentModalMovie: null,
  currentModalTrailerKey: null,
  heroItems: [],
  heroIndex: 0,
  heroTimer: null,
  heroPreviewActive: false,
  activeCountryCode: "KR",
  tableSortKey: "potential_score",
  tableSortAsc: false,
  lastSearchRawData: null,
  searchTypeFilter: "all",
  searchSortMode: "relevance",
  myList: JSON.parse(localStorage.getItem("netflix_my_list") || "[]"),
  userProfile: {
    genres: {},
    countries: {},
    actors: {},
    suggested_actors: {},
    liked_tconsts: [],
    disliked_tconsts: [],
    continue_watching: [],
    active_bandit_arm: "global_hit",
    signal_score: 0,
    recent_actions: []
  },
  hoverTimers: {},
  gemsUnlocked: false,
  toastTimer: null
};

// ==============================================================================
// 1. INICIALIZACIÓN
// ==============================================================================
document.addEventListener("DOMContentLoaded", () => {
  updateMyListBadge();
  initNavbar();
  initProfileSwitcher();
  initSurpriseMeButtons();
  initSearch();
  initDebugPanel();
  initInfiniteScroll();
  loadPersistedUserProfile();
  loadOfflineRecommenderMetrics();
  loadInitialCatalog();
});

async function loadPersistedUserProfile() {
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/user/profile?session_id=${encodeURIComponent(CONFIG.SESSION_ID)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.profile) {
      STATE.userProfile = data.profile;
      STATE.gemsUnlocked = Boolean(data.gems_unlocked);
      if (CONFIG.ACTIVE_PERSONA !== "custom") {
        STATE.myList = Array.isArray(data.profile.my_list) ? [...data.profile.my_list] : [];
      } else {
        const localCustom = JSON.parse(localStorage.getItem("netflix_my_list") || "[]");
        const merged = Array.from(new Set([...localCustom, ...(data.profile.my_list || [])]));
        STATE.myList = merged;
      }
      updateMyListBadge();
      updateDebugPanel();
    }
  } catch (err) {
    console.warn("[Profile SQLite] No se pudo restaurar sesión previa:", err);
  }
}

function initProfileSwitcher() {
  const btn = document.getElementById("btn-profile-switcher");
  const dropdown = document.getElementById("profile-dropdown");
  const wrap = document.getElementById("profile-menu-wrap");
  const resetBtn = document.getElementById("btn-reset-active-profile");
  if (!btn || !dropdown) return;

  const syncHeaderUI = () => {
    const meta = PERSONA_META[CONFIG.ACTIVE_PERSONA] || PERSONA_META.custom;
    const av = document.getElementById("active-profile-avatar");
    const nm = document.getElementById("active-profile-name");
    if (av) {
      av.textContent = meta.avatar;
      av.style.background = meta.bg;
    }
    if (nm) nm.textContent = meta.name;
    dropdown.querySelectorAll(".profile-option").forEach(opt => {
      opt.classList.toggle("active", opt.dataset.persona === CONFIG.ACTIVE_PERSONA);
    });
  };
  syncHeaderUI();

  btn.onclick = (e) => {
    e.stopPropagation();
    dropdown.style.display = dropdown.style.display === "none" ? "block" : "none";
  };

  document.addEventListener("click", (e) => {
    if (wrap && !wrap.contains(e.target)) {
      dropdown.style.display = "none";
    }
  });

  dropdown.querySelectorAll(".profile-option").forEach(opt => {
    opt.onclick = async () => {
      const personaKey = opt.dataset.persona;
      const meta = PERSONA_META[personaKey] || PERSONA_META.custom;
      CONFIG.ACTIVE_PERSONA = personaKey;
      CONFIG.SESSION_ID = meta.sessionId;
      localStorage.setItem("netflix_active_persona", personaKey);
      dropdown.style.display = "none";
      syncHeaderUI();

      // Quitar carrusel de joyas previo si cambiamos a un perfil con < 15 pts
      document.getElementById("carousel-hidden_gems")?.remove();
      document.getElementById("carousel-continue_watching")?.remove();

      await loadPersistedUserProfile();
      await refreshUserRecommendations(true);
      if (STATE.activeSection === "mylist") loadMyListSection();
      showSubtleToast(`${meta.avatar} Perfil activo: ${meta.name}`);
    };
  });

  if (resetBtn) {
    resetBtn.onclick = async () => {
      dropdown.style.display = "none";
      try {
        const res = await fetch(`${CONFIG.API_BASE}/api/user/profile/reset`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: CONFIG.SESSION_ID, restore_demo: false })
        });
        const data = await res.json();
        if (data.profile) {
          STATE.userProfile = data.profile;
          STATE.gemsUnlocked = false;
          if (CONFIG.ACTIVE_PERSONA === "custom") {
            STATE.myList = [];
            localStorage.setItem("netflix_my_list", "[]");
          } else {
            STATE.myList = [];
          }
          updateMyListBadge();
          updateDebugPanel();
          document.getElementById("carousel-hidden_gems")?.remove();
          document.getElementById("carousel-continue_watching")?.remove();
          await refreshUserRecommendations(true);
          showSubtleToast("↺ Aprendizaje reiniciado a 0.0 pts");
        }
      } catch (err) {
        console.error("[Profile Reset] Error:", err);
      }
    };
  }
}

function initSurpriseMeButtons() {
  const navBtn = document.getElementById("btn-nav-surprise");
  const heroBtn = document.getElementById("btn-hero-surprise");
  const handler = async () => {
    showSubtleToast("🎲 Buscando una joya internacional ideal para vos...");
    try {
      const res = await fetch(`${CONFIG.API_BASE}/api/user/surprise-me?session_id=${encodeURIComponent(CONFIG.SESSION_ID)}`);
      const data = await res.json();
      if (data && data.movie) {
        openModal(data.movie, true, data.reasons || []);
      }
    } catch (err) {
      console.error("[Surprise Me] Error:", err);
    }
  };
  if (navBtn) navBtn.onclick = handler;
  if (heroBtn) heroBtn.onclick = handler;
}

async function loadOfflineRecommenderMetrics() {
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/recommender/metrics`);
    if (!res.ok) return;
    const data = await res.json();
    const box = document.getElementById("debug-offline-benchmark");
    if (!box || !data || !data.models || !data.models.Hibrido_NLP_Grafo_v5) return;
    const hyb = data.models.Hibrido_NLP_Grafo_v5;
    const gen = data.models.Baseline_Solo_Generos || { recall_at_k: 11.7, ndcg_at_k: 0.058 };
    const pop = data.models.Baseline_Popularidad || { recall_at_k: 0.0 };
    box.innerHTML = `
      <div><strong style="color:#46d369;">Híbrido NLP + Grafo v5:</strong> Recall@${data.k || 10} <strong>${hyb.recall_at_k}%</strong> | NDCG <strong>${Number(hyb.ndcg_at_k).toFixed(3)}</strong></div>
      <div style="color:#888;">Solo Géneros: ${gen.recall_at_k}% (${Number(gen.ndcg_at_k).toFixed(3)}) • Pop: ${pop.recall_at_k}% • SQLite WAL</div>
    `;
  } catch (err) {
    console.warn("[Metrics] Error cargando benchmark offline:", err);
  }
}

// ------------------------------------------------------------------------------
// 2. NAVEGACIÓN ENTRE INICIO, MI LISTA Y PAÍSES CON MAYOR POTENCIAL
// ------------------------------------------------------------------------------
function initNavbar() {
  const navbar = document.querySelector(".navbar");
  window.addEventListener("scroll", () => {
    if (window.scrollY > 40) {
      navbar.classList.add("scrolled");
    } else {
      navbar.classList.remove("scrolled");
    }
    // Si había una actualización en cola y el carrusel ya salió de la vista, aplicarla sutilmente
    if (STATE.pendingRecData) {
      tryApplyPendingRecommendationsSubtly();
    }
  });

  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const target = link.dataset.target;
      if (target === "home" && STATE.isSearching) {
        clearSearchAndGoHome();
      } else {
        switchSection(target);
      }
    });
  });
}

function switchSection(sectionId) {
  STATE.activeSection = sectionId;
  document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));
  const activeLink = document.querySelector(`[data-target="${sectionId}"]`);
  if (activeLink) activeLink.classList.add("active");

  const homeSec = document.querySelector(".section-home");
  const mylistSec = document.getElementById("section-mylist");
  const bizSec = document.getElementById("section-business");

  homeSec.style.display = "none";
  if (mylistSec) mylistSec.style.display = "none";
  if (bizSec) bizSec.classList.remove("active");

  if (sectionId === "business") {
    bizSec.classList.add("active");
    loadBusinessSection();
  } else if (sectionId === "mylist") {
    mylistSec.style.display = "block";
    loadMyListSection();
  } else {
    homeSec.style.display = "block";
    if (STATE.pendingRecData) {
      applyRecommendationsToDOM(STATE.pendingRecData, false);
      STATE.pendingRecData = null;
    }
  }
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showSubtleToast(message) {
  const toast = document.getElementById("subtle-update-toast");
  const textEl = document.getElementById("subtle-toast-text");
  if (!toast || !textEl) return;

  textEl.textContent = message;
  toast.classList.add("show");
  clearTimeout(STATE.toastTimer);
  STATE.toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 2600);
}

// ------------------------------------------------------------------------------
// 3. CARGA DE CATÁLOGO INICIAL Y HERO BANNER (EN ESPAÑOL)
// ------------------------------------------------------------------------------
async function loadInitialCatalog() {
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/initial`);
    const data = await res.json();

    STATE.heroItems = (data.hero_items && data.hero_items.length > 0) ? data.hero_items : (data.hero ? [data.hero] : []);
    if (STATE.heroItems.length > 0) {
      initHeroCarousel(STATE.heroItems);
    }
    if (data.carousels) renderCarousels(data.carousels);
    
    refreshUserRecommendations(true);
  } catch (err) {
    console.error("[Catalog] Error al cargar:", err);
  }
}

function initHeroCarousel(items) {
  STATE.heroIndex = 0;
  renderHero(items[0], 0, items.length);

  const dotsBox = document.getElementById("hero-dots");
  if (dotsBox) {
    dotsBox.innerHTML = "";
    if (items.length > 1) {
      items.forEach((_, idx) => {
        const dot = document.createElement("button");
        dot.className = idx === 0 ? "hero-dot active" : "hero-dot";
        dot.title = items[idx].primaryTitle;
        dot.onclick = () => {
          stopHeroVideoPreview();
          STATE.heroIndex = idx;
          renderHero(items[idx], idx, items.length);
          restartHeroAutoTimer();
        };
        dotsBox.appendChild(dot);
      });
    }
  }
  restartHeroAutoTimer();
}

function restartHeroAutoTimer() {
  clearInterval(STATE.heroTimer);
  if (!STATE.heroItems || STATE.heroItems.length <= 1) return;
  STATE.heroTimer = setInterval(() => {
    const modalOpen = document.getElementById("modal-backdrop")?.classList.contains("active");
    if (STATE.activeSection !== "home" || STATE.isSearching || modalOpen || STATE.heroPreviewActive) return;
    STATE.heroIndex = (STATE.heroIndex + 1) % STATE.heroItems.length;
    renderHero(STATE.heroItems[STATE.heroIndex], STATE.heroIndex, STATE.heroItems.length);
  }, 11000);
}

function stopHeroVideoPreview() {
  STATE.heroPreviewActive = false;
  const wrap = document.getElementById("hero-bg-video-wrap");
  const iframe = document.getElementById("hero-bg-iframe");
  const btn = document.getElementById("btn-hero-preview-video");
  if (iframe) iframe.src = "";
  if (wrap) wrap.style.display = "none";
  if (btn) btn.innerHTML = "&#127902; Vista Previa";
}

function renderHero(hero, slideIdx = 0, totalSlides = 1) {
  const heroEl = document.querySelector(".hero-banner");
  const contentBox = document.getElementById("hero-content-box");
  if (!heroEl || !hero) return;

  if (contentBox) {
    contentBox.classList.remove("hero-crossfade");
    void contentBox.offsetWidth;
    contentBox.classList.add("hero-crossfade");
  }

  const backdropUrl = `${CONFIG.API_BASE}/api/backdrop/${hero.tconst}`;
  heroEl.style.backgroundImage = `linear-gradient(to right, rgba(20, 20, 20, 0.95) 25%, rgba(20, 20, 20, 0.58) 60%, rgba(20, 20, 20, 0.15) 100%), linear-gradient(0deg, #141414 0%, transparent 60%), url('${backdropUrl}')`;

  const tagEl = document.getElementById("hero-tag-badge");
  if (tagEl) {
    tagEl.textContent = totalSlides > 1
      ? `DESTACADO GLOBAL #${slideIdx + 1} DE ${totalSlides} • TOP HORAS EN STREAMING`
      : `TÍTULO DESTACADO GLOBAL • N° 1 EN STREAMING`;
  }

  document.querySelector(".hero-title").textContent = hero.primaryTitle || "Título Destacado";
  const matchEl = document.querySelector(".hero-match");
  if (matchEl) matchEl.textContent = `${hero.match_pct || 98}% para vos`;
  document.querySelector(".hero-year").textContent = hero.startYear || "2024";
  document.querySelector(".hero-bayes").textContent = `★ ${hero.bayesian_rating || '8.6'} Bayes`;
  document.querySelector(".hero-country").textContent = hero.pais_origen || "Internacional";
  document.querySelector(".hero-genres").textContent = hero.genres_es || hero.genres || "Drama, Fantasía";
  
  document.querySelector(".hero-desc").textContent = hero.overview_es || "Una de las producciones más destacadas del catálogo internacional de Netflix.";

  document.querySelector(".btn-hero-info").onclick = () => openModal(hero, false);
  document.querySelector(".btn-hero-play").onclick = () => openModal(hero, true);

  // Actualizar dots activos
  document.querySelectorAll("#hero-dots .hero-dot").forEach((d, i) => {
    d.classList.toggle("active", i === slideIdx);
  });

  // Botón de vista previa de video embebida en portada si el título posee trailer_key
  const previewBtn = document.getElementById("btn-hero-preview-video");
  if (previewBtn) {
    stopHeroVideoPreview();
    if (hero.trailer_key) {
      previewBtn.style.display = "inline-block";
      previewBtn.onclick = () => {
        if (STATE.heroPreviewActive) {
          stopHeroVideoPreview();
        } else {
          const wrap = document.getElementById("hero-bg-video-wrap");
          const iframe = document.getElementById("hero-bg-iframe");
          if (wrap && iframe) {
            iframe.src = `https://www.youtube.com/embed/${hero.trailer_key}?autoplay=1&mute=1&controls=0&loop=1&playlist=${hero.trailer_key}&modestbranding=1`;
            wrap.style.display = "block";
            STATE.heroPreviewActive = true;
            previewBtn.innerHTML = "&#9209; Detener Vista";
          }
        }
      };
    } else {
      previewBtn.style.display = "none";
    }
  }
}

function renderCarousels(carousels) {
  const container = document.getElementById("carousels-container");
  container.innerHTML = "";

  carousels.forEach(c => {
    const section = createCarouselElement(c);
    container.appendChild(section);
  });
}

function createCarouselElement(carouselData) {
  const sec = document.createElement("section");
  sec.className = "carousel-section";
  sec.id = `carousel-${carouselData.id}`;

  sec.innerHTML = `
    <div class="carousel-header">
      <h2 class="carousel-title">${carouselData.title}</h2>
      ${carouselData.subtitle ? `<span class="carousel-subtitle">${carouselData.subtitle}</span>` : ""}
    </div>
    <div class="carousel-wrapper">
      <button class="carousel-btn left" aria-label="Anterior">&#10094;</button>
      <div class="carousel-track"></div>
      <button class="carousel-btn right" aria-label="Siguiente">&#10095;</button>
    </div>
  `;

  const track = sec.querySelector(".carousel-track");
  const isTop10Row = carouselData.id === "trending";
  (carouselData.items || []).forEach((movie, idx) => {
    const rankNum = (isTop10Row && idx < 10) ? (idx + 1) : null;
    const card = createMovieCard(movie, false, rankNum);
    track.appendChild(card);
  });

  const leftBtn = sec.querySelector(".carousel-btn.left");
  const rightBtn = sec.querySelector(".carousel-btn.right");
  leftBtn.onclick = () => track.scrollBy({ left: -620, behavior: "smooth" });
  rightBtn.onclick = () => track.scrollBy({ left: 620, behavior: "smooth" });

  return sec;
}

function createMovieCard(movie, subtleEnter = false, rankNum = null) {
  const card = document.createElement("div");
  let cls = subtleEnter ? "movie-card subtle-enter" : "movie-card";
  if (rankNum !== null) cls += " top10-ranked";
  card.className = cls;
  card.dataset.tconst = movie.tconst;

  const inList = STATE.myList.includes(movie.tconst);
  const isLiked = (STATE.userProfile.liked_tconsts || []).includes(movie.tconst);
  const genresDisplay = movie.genres_es || movie.genres || "";
  const banditVariant = (STATE.userProfile.active_bandit_arm === "actor_focus") ? 1 : 0;
  const posterSrc = `${CONFIG.API_BASE}/api/poster/${movie.tconst}?title=${encodeURIComponent(movie.primaryTitle)}&year=${movie.startYear}&rating=${movie.bayesian_rating}&genres=${encodeURIComponent(genresDisplay)}&variant=${banditVariant}`;
  const isSeriesBadge = (movie.is_series || movie.titleType === "tvSeries" || movie.titleType === "tvMiniSeries")
    ? `<span style="background:#e50914; color:#fff; font-size:9px; font-weight:800; padding:1px 5px; border-radius:2px;">SERIE</span>`
    : "";

  const rankSvgHtml = rankNum !== null
    ? `<svg class="top10-rank-svg" viewBox="0 0 110 200" aria-hidden="true">
         <text x="${rankNum === 10 ? '-4' : '18'}" y="172" font-size="${rankNum === 10 ? '138' : '176'}" font-weight="900"
               font-family="Arial Black, Impact, sans-serif" fill="#141414" stroke="#6b6b6b" stroke-width="4.5" letter-spacing="-10">${rankNum}</text>
       </svg>`
    : "";

  const top10CornerHtml = (Number(movie.in_netflix_top10) === 1 && rankNum === null)
    ? `<div class="card-top10-ribbon">TOP<br>10</div>`
    : "";

  const progressBarHtml = movie.progress_pct
    ? `<div class="card-progress-track"><div class="card-progress-fill" style="width:${movie.progress_pct}%;"></div></div>`
    : "";

  card.innerHTML = `
    ${rankSvgHtml}
    ${top10CornerHtml}
    <img class="poster-img" src="${posterSrc}" alt="${movie.primaryTitle}" loading="lazy" />
    ${progressBarHtml}
    <div class="card-overlay">
      <div class="card-title" title="${movie.primaryTitle}">${movie.primaryTitle}</div>
      <div class="card-meta">
        <span style="color:#46d369; font-weight:800;">${movie.match_pct || 94}%</span>
        <span class="bayes-score">★ ${movie.bayesian_rating}</span>
        <span>${movie.startYear}</span>
        ${isSeriesBadge}
      </div>
      <div class="card-country">${movie.pais_origen || ''}</div>
      <div class="card-genres">${genresDisplay}</div>
      ${movie.explanation ? `<div class="explanation-badge">${movie.explanation}</div>` : ''}
      <div class="card-actions">
        <button class="btn-card-action btn-play-card" title="Ver Tráiler / Reproducir">&#9658;</button>
        <button class="btn-card-action btn-list-card ${inList ? 'in-list' : ''}" title="${inList ? 'Quitar de Mi Lista' : 'Agregar a Mi Lista'}">${inList ? '&#10003;' : '+'}</button>
        <button class="btn-card-action btn-like-card ${isLiked ? 'liked' : ''}" title="Me encanta (+8 pts)">&#128077;</button>
        <button class="btn-card-action btn-dislike-card" title="No es para mí (ocultar y ajustar)">&#128078;</button>
        <button class="btn-card-action btn-info-card" title="Más Información y Episodios">&#9432;</button>
      </div>
    </div>
  `;

  // Tracking de Hover >= 800 ms (actualiza el perfil en segundo plano sin sacudir la pantalla)
  card.addEventListener("mouseenter", () => {
    STATE.hoverTimers[movie.tconst] = setTimeout(() => {
      sendInteraction({
        event_type: "hover",
        tconst: movie.tconst,
        title: movie.primaryTitle,
        genres: movie.genres || "",
        country_code: movie.domestic_region || "",
        actors: movie.actors_str || "",
        dwell_ms: CONFIG.MIN_HOVER_DWELL_MS
      });
    }, CONFIG.MIN_HOVER_DWELL_MS);
  });

  card.addEventListener("mouseleave", () => {
    clearTimeout(STATE.hoverTimers[movie.tconst]);
    delete STATE.hoverTimers[movie.tconst];
  });

  card.addEventListener("click", (e) => {
    if (e.target.closest(".btn-card-action")) return;
    sendInteraction({
      event_type: "click",
      tconst: movie.tconst,
      title: movie.primaryTitle,
      genres: movie.genres || "",
      country_code: movie.domestic_region || "",
      actors: movie.actors_str || ""
    });
    openModal(movie, false);
  });

  const playBtn = card.querySelector(".btn-play-card");
  const listBtn = card.querySelector(".btn-list-card");
  const likeBtn = card.querySelector(".btn-like-card");
  const dislikeBtn = card.querySelector(".btn-dislike-card");
  const infoBtn = card.querySelector(".btn-info-card");

  playBtn.onclick = (e) => {
    e.stopPropagation();
    openModal(movie, true);
  };

  infoBtn.onclick = (e) => {
    e.stopPropagation();
    openModal(movie, false);
  };

  listBtn.onclick = (e) => {
    e.stopPropagation();
    toggleMyList(movie, listBtn);
  };

  if (likeBtn) {
    likeBtn.onclick = (e) => {
      e.stopPropagation();
      likeBtn.classList.add("liked");
      sendInteraction({
        event_type: "like",
        tconst: movie.tconst,
        title: movie.primaryTitle,
        genres: movie.genres || "",
        country_code: movie.domestic_region || "",
        actors: movie.actors_str || ""
      });
      showSubtleToast(`👍 Afinidad reforzada con "${movie.primaryTitle}" (+8 pts)`);
    };
  }

  if (dislikeBtn) {
    dislikeBtn.onclick = (e) => {
      e.stopPropagation();
      dismissDislikedTitleEverywhere(movie);
    };
  }

  return card;
}

function dismissDislikedTitleEverywhere(movie) {
  sendInteraction({
    event_type: "dislike",
    tconst: movie.tconst,
    title: movie.primaryTitle,
    genres: movie.genres || "",
    country_code: movie.domestic_region || "",
    actors: movie.actors_str || ""
  });
  document.querySelectorAll(`.movie-card[data-tconst="${movie.tconst}"]`).forEach(el => {
    el.classList.add("card-dismissing");
    setTimeout(() => el.remove(), 290);
  });
  showSubtleToast(`👎 Ocultado "${movie.primaryTitle}" y ajustadas tus preferencias`);
}

function recordWatchProgress(movie, progressPct = 35, watchLabel = "Tráiler / En curso") {
  if (!movie || !movie.tconst) return;
  sendInteraction({
    event_type: "watch_progress",
    tconst: movie.tconst,
    title: movie.primaryTitle || "",
    progress_pct: progressPct,
    watch_label: watchLabel
  }).then(() => refreshUserRecommendations(false));
}

// ------------------------------------------------------------------------------
// 4. SCROLL INFINITO (GENERACIÓN CONTINUA DE CATEGORÍAS COMO EN NETFLIX)
// ------------------------------------------------------------------------------
function initInfiniteScroll() {
  const sentinel = document.getElementById("infinite-scroll-sentinel");
  if (!sentinel) return;

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && STATE.activeSection === "home" && !STATE.isSearching && !STATE.isLoadingInfinite) {
        loadMoreInfiniteCarousels();
      }
    });
  }, { rootMargin: "320px" });

  observer.observe(sentinel);
}

async function loadMoreInfiniteCarousels() {
  if (STATE.isLoadingInfinite) return;
  STATE.isLoadingInfinite = true;

  try {
    const pageToFetch = STATE.infinitePage;
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/infinite-scroll?page=${pageToFetch}&session_id=${CONFIG.SESSION_ID}`);
    const data = await res.json();

    const container = document.getElementById("carousels-container");
    if (data.carousels && data.carousels.length > 0) {
      data.carousels.forEach(c => {
        if (!document.getElementById(`carousel-${c.id}`)) {
          const sec = createCarouselElement(c);
          container.appendChild(sec);
        }
      });
      STATE.infinitePage += 1;
    }
  } catch (err) {
    console.error("[Infinite Scroll] Error:", err);
  } finally {
    setTimeout(() => {
      STATE.isLoadingInfinite = false;
    }, 350);
  }
}

// ------------------------------------------------------------------------------
// 5. MOTOR DE APRENDIZAJE E INTERACCIÓN SUTIL (NO INTRUSIVO EN LA CARA DEL USUARIO)
// ------------------------------------------------------------------------------
function isElementVisibleInViewport(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  return rect.bottom > 70 && rect.top < (window.innerHeight - 60);
}

async function sendInteraction(eventData) {
  try {
    const payload = {
      session_id: CONFIG.SESSION_ID,
      ...eventData
    };
    const res = await fetch(`${CONFIG.API_BASE}/api/user/interact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const result = await res.json();
    
    if (result.profile) {
      STATE.userProfile = result.profile;
      STATE.gemsUnlocked = result.gems_unlocked;
      updateDebugPanel();
    }

    // Solo pedir nuevas recomendaciones en interacciones intencionales o cuando se acumuló señal
    if (["click", "modal_open", "my_list", "actor_click", "like", "dislike"].includes(eventData.event_type)) {
      refreshUserRecommendations(false);
    }
  } catch (err) {
    console.error("[Interaction] Error:", err);
  }
}

async function refreshUserRecommendations(isInitialLoad = false) {
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/user/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: CONFIG.SESSION_ID })
    });
    const data = await res.json();

    if (isInitialLoad) {
      applyRecommendationsToDOM(data, false);
      return;
    }

    // Verificar si el carrusel de afinidad está actualmente frente a los ojos del usuario
    const existingAffinity = document.getElementById("carousel-user_affinity");
    const modalOpen = document.getElementById("modal-backdrop")?.classList.contains("active");

    if (existingAffinity && isElementVisibleInViewport(existingAffinity) && !modalOpen) {
      // ¡NO reemplazar bruscamente el carrusel en la cara del usuario!
      // En su lugar, agregar sutilmente al final del carrusel las nuevas sugerencias que aún no estén
      STATE.pendingRecData = data;
      mergeNewCardsSubtlyIntoTrack(existingAffinity, data.affinity_carousel);
      showSubtleToast("✦ Nuevas recomendaciones añadidas al final del carrusel");
    } else {
      applyRecommendationsToDOM(data, true);
    }
  } catch (err) {
    console.error("[Recommender] Error al refrescar:", err);
  }
}

function mergeNewCardsSubtlyIntoTrack(carouselEl, newCarouselData) {
  if (!carouselEl || !newCarouselData || !newCarouselData.items) return;
  const track = carouselEl.querySelector(".carousel-track");
  if (!track) return;

  const existingIds = new Set(
    Array.from(track.querySelectorAll(".movie-card")).map(c => c.dataset.tconst)
  );

  let added = 0;
  newCarouselData.items.forEach(item => {
    if (!existingIds.has(item.tconst) && added < 4) {
      track.appendChild(createMovieCard(item, true));
      existingIds.add(item.tconst);
      added++;
    }
  });
}

function tryApplyPendingRecommendationsSubtly() {
  if (!STATE.pendingRecData) return;
  const existingAffinity = document.getElementById("carousel-user_affinity");
  if (!existingAffinity || !isElementVisibleInViewport(existingAffinity)) {
    applyRecommendationsToDOM(STATE.pendingRecData, true);
    STATE.pendingRecData = null;
  }
}

function applyRecommendationsToDOM(data, notifyToast = false) {
  const container = document.getElementById("carousels-container");
  if (!container) return;

  // 1. Fila "Continuar viendo" con barras rojas de progreso
  if (data.continue_watching_carousel && data.continue_watching_carousel.items && data.continue_watching_carousel.items.length > 0) {
    let existingCW = document.getElementById("carousel-continue_watching");
    const newCW = createCarouselElement(data.continue_watching_carousel);
    if (existingCW) {
      container.replaceChild(newCW, existingCW);
    } else {
      container.insertBefore(newCW, container.children[1] || null);
    }
  }

  const affinityInsertIndex = document.getElementById("carousel-continue_watching") ? 2 : 1;

  if (data.affinity_carousel && data.affinity_carousel.items && data.affinity_carousel.items.length > 0) {
    let existingAffinity = document.getElementById("carousel-user_affinity");
    if (existingAffinity) {
      // Actualizar título y tarjetas manteniendo el scroll horizontal si ya existía
      const prevScroll = existingAffinity.querySelector(".carousel-track")?.scrollLeft || 0;
      const newAffinity = createCarouselElement(data.affinity_carousel);
      container.replaceChild(newAffinity, existingAffinity);
      const newTrack = newAffinity.querySelector(".carousel-track");
      if (newTrack) newTrack.scrollLeft = prevScroll;
    } else {
      const newAffinity = createCarouselElement(data.affinity_carousel);
      container.insertBefore(newAffinity, container.children[affinityInsertIndex] || null);
    }
  }

  if (data.gems_carousel && data.gems_carousel.items && data.gems_carousel.items.length > 0) {
    let existingGems = document.getElementById("carousel-hidden_gems");
    const newGems = createCarouselElement(data.gems_carousel);
    if (existingGems) {
      container.replaceChild(newGems, existingGems);
    } else {
      container.insertBefore(newGems, container.children[affinityInsertIndex + 1] || null);
      if (notifyToast) showSubtleToast("💎 ¡Desbloqueaste el carrusel 'Joyas Escondidas para vos'!");
    }
  }
}

// ------------------------------------------------------------------------------
// 6. SECCIÓN "MI LISTA" (GUARDADO PERSISTENTE Y RECOMENDACIONES DE MI LISTA)
// ------------------------------------------------------------------------------
function updateMyListBadge() {
  const badge = document.getElementById("mylist-count-badge");
  if (badge) {
    badge.textContent = STATE.myList.length;
  }
}

function toggleMyList(movie, btnEl) {
  const idx = STATE.myList.indexOf(movie.tconst);
  if (idx > -1) {
    STATE.myList.splice(idx, 1);
    if (btnEl) {
      btnEl.classList.remove("in-list");
      btnEl.innerHTML = "+";
    }
    showSubtleToast(`Quitado de Mi Lista: ${movie.primaryTitle}`);
  } else {
    STATE.myList.push(movie.tconst);
    if (btnEl) {
      btnEl.classList.add("in-list");
      btnEl.innerHTML = "&#10003;";
    }
    sendInteraction({
      event_type: "my_list",
      tconst: movie.tconst,
      title: movie.primaryTitle,
      genres: movie.genres || "",
      country_code: movie.domestic_region || "",
      actors: movie.actors_str || ""
    });
    showSubtleToast(`✓ Agregado a Mi Lista: ${movie.primaryTitle}`);
  }
  localStorage.setItem("netflix_my_list", JSON.stringify(STATE.myList));
  updateMyListBadge();

  if (STATE.activeSection === "mylist") {
    loadMyListSection();
  }
}

async function loadMyListSection() {
  const emptyState = document.getElementById("mylist-empty-state");
  const contentBox = document.getElementById("mylist-content-box");
  const savedGrid = document.getElementById("mylist-saved-grid");
  const recsGrid = document.getElementById("mylist-recs-grid");
  const totalLabel = document.getElementById("mylist-total-label");

  if (!STATE.myList || STATE.myList.length === 0) {
    if (emptyState) emptyState.style.display = "block";
    if (contentBox) contentBox.style.display = "none";
    return;
  }

  if (emptyState) emptyState.style.display = "none";
  if (contentBox) contentBox.style.display = "block";
  if (totalLabel) totalLabel.textContent = STATE.myList.length;

  savedGrid.innerHTML = `<div style="color:#aaa; padding:20px;">Cargando tu colección...</div>`;
  recsGrid.innerHTML = "";

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/mylist`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tconsts: STATE.myList, session_id: CONFIG.SESSION_ID })
    });
    const data = await res.json();

    savedGrid.innerHTML = "";
    (data.items || []).forEach(movie => {
      savedGrid.appendChild(createMovieCard(movie));
    });

    recsGrid.innerHTML = "";
    (data.recommendations || []).forEach(movie => {
      recsGrid.appendChild(createMovieCard(movie));
    });
  } catch (err) {
    console.error("[My List] Error:", err);
  }
}

async function loadHiddenGemsSection(region = "all", btnEl = null) {
  if (btnEl) {
    document.querySelectorAll(".gem-region-btn").forEach(b => b.classList.remove("coactor"));
    btnEl.classList.add("coactor");
  }
  const headingEl = document.getElementById("gems-featured-heading");
  const featGrid = document.getElementById("gems-featured-grid");
  const carouselsBox = document.getElementById("gems-carousels-container");
  if (!featGrid || !carouselsBox) return;

  featGrid.innerHTML = `<div style="color:#aaa; padding:20px;">Buscando Joyas Escondidas Internacionales...</div>`;
  carouselsBox.innerHTML = "";

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/hidden-gems?region=${encodeURIComponent(region)}`);
    const data = await res.json();

    if (headingEl) {
      headingEl.textContent = `💎 Joyas Escondidas Destacadas: ${data.region_label || 'Internacional'}`;
    }

    featGrid.innerHTML = "";
    (data.featured_gems || []).forEach(movie => {
      featGrid.appendChild(createMovieCard(movie, true));
    });

    carouselsBox.innerHTML = "";
    (data.carousels || []).forEach(c => {
      carouselsBox.appendChild(createCarouselElement(c));
    });
  } catch (err) {
    console.error("[Hidden Gems] Error:", err);
  }
}

// ------------------------------------------------------------------------------
// 7. MODAL DE DETALLE (SINOPSIS EN ESPAÑOL, TRÁILER YOUTUBE, HOOK EPISODE Y SERIES)
// ------------------------------------------------------------------------------
async function openModal(movie, autoplayTrailer = false, surpriseReasons = null) {
  const modalBackdrop = document.getElementById("modal-backdrop");
  if (!modalBackdrop) return;

  stopHeroVideoPreview();
  stopModalTrailer();
  STATE.currentModalMovie = movie;
  STATE.currentModalTrailerKey = null;

  const surpriseBox = document.getElementById("modal-surprise-box");
  if (surpriseBox) {
    if (surpriseReasons && surpriseReasons.length > 0) {
      surpriseBox.style.display = "block";
      surpriseBox.innerHTML = `
        <div style="font-weight:800; color:#ffd54f; margin-bottom:5px;">🎲 Selección "Sorprendeme" personalizada para vos:</div>
        ${surpriseReasons.map(r => `<div style="margin-top:2px;">• ${r}</div>`).join("")}
      `;
    } else {
      surpriseBox.style.display = "none";
      surpriseBox.innerHTML = "";
    }
  }

  const modalHero = document.getElementById("modal-hero-banner");
  if (modalHero) {
    modalHero.style.backgroundImage = `linear-gradient(180deg, rgba(24, 24, 24, 0.15) 0%, rgba(24, 24, 24, 0.95) 100%), url('${CONFIG.API_BASE}/api/backdrop/${movie.tconst}')`;
  }

  sendInteraction({
    event_type: "modal_open",
    tconst: movie.tconst,
    title: movie.primaryTitle,
    genres: movie.genres || "",
    country_code: movie.domestic_region || "",
    actors: movie.actors_str || ""
  });

  const isTvGuess = movie.is_series || movie.titleType === "tvSeries" || movie.titleType === "tvMiniSeries";
  document.getElementById("modal-type-badge").textContent = isTvGuess ? "SERIE DE TV" : "PELÍCULA";
  document.getElementById("modal-title").textContent = movie.primaryTitle;
  document.getElementById("modal-match").textContent = `${movie.match_pct || 96}% para vos`;
  document.getElementById("modal-bayes").textContent = `★ ${movie.bayesian_rating} Bayes`;
  document.getElementById("modal-year").textContent = movie.startYear || "2024";
  document.getElementById("modal-runtime").textContent = movie.runtimeMinutes ? `${movie.runtimeMinutes} min` : (isTvGuess ? "Serie por Episodios" : "Largometraje");
  document.getElementById("modal-country").textContent = movie.pais_origen || "Internacional";
  document.getElementById("modal-genres").textContent = movie.genres_es || movie.genres || "Drama";
  document.getElementById("modal-regiones").textContent = `${movie.num_regiones || 1} países`;

  const hours = movie.netflix_horas_vistas ? `${(movie.netflix_horas_vistas / 1e6).toFixed(1)} Millones de Horas` : "En catálogo internacional";
  document.getElementById("modal-hours").textContent = hours;
  document.getElementById("modal-overview").textContent = movie.overview_es || "Cargando descripción oficial en español...";

  // Botón Mi Lista + Feedback 👍 / 👎 en Modal
  const modalListBtn = document.getElementById("modal-btn-list");
  const inList = STATE.myList.includes(movie.tconst);
  modalListBtn.textContent = inList ? "✓ En Mi Lista" : "+ Agregar a Mi Lista";
  modalListBtn.onclick = () => {
    toggleMyList(movie, null);
    const isNow = STATE.myList.includes(movie.tconst);
    modalListBtn.textContent = isNow ? "✓ En Mi Lista" : "+ Agregar a Mi Lista";
  };

  const modalLikeBtn = document.getElementById("modal-btn-like");
  const modalDislikeBtn = document.getElementById("modal-btn-dislike");
  if (modalLikeBtn) {
    const isLiked = (STATE.userProfile.liked_tconsts || []).includes(movie.tconst);
    modalLikeBtn.classList.toggle("active-like", isLiked);
    modalLikeBtn.onclick = () => {
      modalLikeBtn.classList.add("active-like");
      modalDislikeBtn?.classList.remove("active-dislike");
      sendInteraction({
        event_type: "like",
        tconst: movie.tconst,
        title: movie.primaryTitle,
        genres: movie.genres || "",
        country_code: movie.domestic_region || "",
        actors: movie.actors_str || ""
      });
      showSubtleToast(`👍 Te encantó "${movie.primaryTitle}" (+8 pts en tu perfil)`);
    };
  }
  if (modalDislikeBtn) {
    modalDislikeBtn.classList.remove("active-dislike");
    modalDislikeBtn.onclick = () => {
      dismissDislikedTitleEverywhere(movie);
      closeModal();
    };
  }

  // Botón Reproducir / Tráiler
  const playBtn = document.getElementById("modal-btn-play");
  playBtn.innerHTML = "&#9658; Ver Tráiler Oficial / Reproducir";
  playBtn.onclick = () => playModalTrailer(movie.primaryTitle);

  const seriesSec = document.getElementById("modal-series-section");
  seriesSec.style.display = "none";
  const simSec = document.getElementById("modal-similar-section");
  if (simSec) simSec.style.display = "none";

  modalBackdrop.classList.add("active");
  document.body.style.overflow = "hidden";

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/title/${movie.tconst}/details`);
    const details = await res.json();

    document.getElementById("modal-overview").textContent = details.overview || movie.overview_es;
    if (details.pais_origen) {
      document.getElementById("modal-country").textContent = details.pais_origen;
    }
    if (details.genres_es) {
      document.getElementById("modal-genres").textContent = details.genres_es;
    }
    document.getElementById("modal-directors").textContent = (details.directors && details.directors.length > 0)
      ? details.directors.join(", ")
      : "Producción Original / Internacional";

    STATE.currentModalTrailerKey = details.trailer_key || null;
    if (autoplayTrailer && STATE.currentModalTrailerKey) {
      playModalTrailer(movie.primaryTitle);
    }

    // Píldoras de Actores Principales (1-Hop)
    const actorsContainer = document.getElementById("modal-actors-pills");
    actorsContainer.innerHTML = "";
    if (details.actors && details.actors.length > 0) {
      details.actors.forEach(actorName => {
        const btn = document.createElement("button");
        btn.className = "actor-pill";
        btn.textContent = actorName;
        btn.title = `Ver películas de ${actorName} y sumar a tus actores favoritos`;
        btn.onclick = () => clickActorPill(actorName, movie);
        actorsContainer.appendChild(btn);
      });
    } else {
      actorsContainer.innerHTML = `<span style="color:#777; font-size:12px;">Reparto coral internacional</span>`;
    }

    // Píldoras de Co-Estrellas del Grafo (2-Hop)
    const coActorsBox = document.getElementById("modal-graph-coactors");
    const coActorsContainer = document.getElementById("modal-coactors-pills");
    coActorsContainer.innerHTML = "";
    const coGraph = details.co_actors_graph || {};
    const coKeys = Object.keys(coGraph);
    if (coKeys.length > 0) {
      coActorsBox.style.display = "block";
      coKeys.forEach(coActor => {
        const info = coGraph[coActor];
        const btn = document.createElement("button");
        btn.className = "actor-pill coactor";
        btn.innerHTML = `${coActor} <span style="opacity:0.75; font-size:10px;">(vía ${info.via_actor})</span>`;
        btn.title = `Colaboró con ${info.via_actor} en '${info.shared_title}'. Clic para explorar`;
        btn.onclick = () => clickActorPill(coActor, movie);
        coActorsContainer.appendChild(btn);
      });
    } else {
      coActorsBox.style.display = "none";
    }

    // Si es una Serie, mostrar Hook Episode Banner, Temporadas y Episodios en español
    if (details.is_series && details.seasons && details.seasons.length > 0) {
      document.getElementById("modal-type-badge").textContent = `SERIE • ${details.seasons.length} TEMPORADA${details.seasons.length > 1 ? 'S' : ''}`;
      document.getElementById("modal-runtime").textContent = `${details.seasons.length} Temporada${details.seasons.length > 1 ? 's' : ''}`;
      seriesSec.style.display = "block";

      renderHookEpisodeBanner(details.hook_analysis);

      const seasonSelect = document.getElementById("modal-season-select");
      seasonSelect.innerHTML = "";
      details.seasons.forEach(sNum => {
        const opt = document.createElement("option");
        opt.value = sNum;
        opt.textContent = `Temporada ${sNum}`;
        seasonSelect.appendChild(opt);
      });

      seasonSelect.onchange = (e) => {
        loadSeriesSeasonEpisodes(movie.tconst, parseInt(e.target.value, 10));
      };

      renderEpisodesList(details.episodes || [], 1, details.hook_analysis?.hook_episode);
    }

    // Renderizar grilla "Más títulos similares a este" en la base del Modal
    renderModalSimilarGrid(details.similar_titles || []);
  } catch (err) {
    console.error("[Modal Details] Error:", err);
  }
}

function renderModalSimilarGrid(similarItems) {
  const sec = document.getElementById("modal-similar-section");
  const grid = document.getElementById("modal-similar-grid");
  if (!sec || !grid) return;

  if (!similarItems || similarItems.length === 0) {
    sec.style.display = "none";
    return;
  }
  sec.style.display = "block";
  grid.innerHTML = "";
  similarItems.slice(0, 6).forEach(sim => {
    const card = document.createElement("div");
    card.className = "modal-sim-card";
    const posterSrc = `${CONFIG.API_BASE}/api/poster/${sim.tconst}?title=${encodeURIComponent(sim.primaryTitle)}&year=${sim.startYear}&rating=${sim.bayesian_rating}`;
    card.innerHTML = `
      <img src="${posterSrc}" alt="${sim.primaryTitle}" loading="lazy" />
      <div class="modal-sim-info">
        <div class="modal-sim-title" title="${sim.primaryTitle}">${sim.primaryTitle}</div>
        <div class="modal-sim-meta">
          <span style="color:#46d369; font-weight:700;">★ ${sim.bayesian_rating}</span>
          <span>${sim.startYear || ""} • ${(sim.pais_origen || "").split(" - ")[0]}</span>
        </div>
      </div>
    `;
    card.onclick = () => {
      document.querySelector(".modal-box")?.scrollTo({ top: 0, behavior: "smooth" });
      openModal(sim, false);
    };
    grid.appendChild(card);
  });
}

function playModalTrailer(titleName) {
  if (STATE.currentModalMovie) {
    recordWatchProgress(STATE.currentModalMovie, 42, "Tráiler visto");
  }
  const trailerBox = document.getElementById("modal-trailer-container");
  const iframe = document.getElementById("modal-trailer-iframe");
  if (STATE.currentModalTrailerKey && trailerBox && iframe) {
    iframe.src = `https://www.youtube.com/embed/${STATE.currentModalTrailerKey}?autoplay=1&rel=0&modestbranding=1`;
    trailerBox.style.display = "block";
  } else {
    showSubtleToast(`▶ Iniciando reproducción en streaming HD de "${titleName}"`);
  }
}

function stopModalTrailer() {
  const trailerBox = document.getElementById("modal-trailer-container");
  const iframe = document.getElementById("modal-trailer-iframe");
  if (iframe) iframe.src = "";
  if (trailerBox) trailerBox.style.display = "none";
}

function renderHookEpisodeBanner(hookData) {
  const banner = document.getElementById("modal-hook-banner");
  if (!banner || !hookData) return;

  document.getElementById("hook-ep-val").textContent = `Ep. ${hookData.hook_episode}: "${hookData.hook_title}" (★ ${hookData.hook_rating || 8.4})`;
  document.getElementById("hook-retention-val").textContent = `${hookData.retention_pct}% Audiencia Fiel`;
  document.getElementById("hook-trend-val").textContent = hookData.trend || "Estable";
}

async function loadSeriesSeasonEpisodes(tconst, seasonNum) {
  const listEl = document.getElementById("modal-episodes-list");
  listEl.innerHTML = `<div style="padding:20px; color:#aaa; text-align:center;">Cargando episodios en español de la Temporada ${seasonNum}...</div>`;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/series/${tconst}/season/${seasonNum}`);
    const data = await res.json();
    renderHookEpisodeBanner(data.hook_analysis);
    renderEpisodesList(data.episodes || [], seasonNum, data.hook_analysis?.hook_episode);
  } catch (err) {
    console.error("[Series Season] Error:", err);
  }
}

function renderEpisodesList(episodes, seasonNum, hookEpNum = null) {
  const listEl = document.getElementById("modal-episodes-list");
  const subEl = document.getElementById("modal-series-subtitle");
  listEl.innerHTML = "";

  if (!episodes || episodes.length === 0) {
    listEl.innerHTML = `<div style="padding:16px; color:#888;">No se encontraron episodios detallados para esta temporada.</div>`;
    return;
  }

  const totalMin = episodes.reduce((acc, ep) => acc + (ep.runtime_minutes || 45), 0);
  const hours = (totalMin / 60).toFixed(1);
  subEl.textContent = `Temporada ${seasonNum}: ${episodes.length} episodios • Duración acumulada: ${totalMin} min (${hours} h)`;

  renderSeasonSparkline(episodes, seasonNum, hookEpNum);

  episodes.forEach((ep, epIdx) => {
    const isHook = hookEpNum === ep.episode_number;
    const row = document.createElement("div");
    row.className = "episode-row";
    if (isHook) {
      row.style.borderColor = "rgba(229, 9, 20, 0.65)";
      row.style.background = "rgba(229, 9, 20, 0.08)";
    }
    row.onclick = () => {
      const pct = Math.min(92, Math.max(15, Math.round(((epIdx + 1) / episodes.length) * 100)));
      if (STATE.currentModalMovie) {
        recordWatchProgress(STATE.currentModalMovie, pct, `T${seasonNum}:E${ep.episode_number}`);
      }
      showSubtleToast(`▶ Reproduciendo T${seasonNum}:E${ep.episode_number} - "${ep.title}" (${ep.runtime_minutes} min)`);
    };

    const hookBadge = isHook
      ? `<span style="background:#e50914; color:#fff; font-size:9.5px; font-weight:800; padding:1px 6px; border-radius:3px; margin-left:6px;">🔥 EPISODIO GANCHO</span>`
      : "";

    row.innerHTML = `
      <div class="episode-num">${ep.episode_number}</div>
      <div class="episode-thumb-box">
        <img class="episode-thumb" src="${ep.still_url}" alt="Episodio ${ep.episode_number}" loading="lazy" />
        <div class="episode-play-icon">&#9658;</div>
      </div>
      <div>
        <div class="episode-info-top">
          <div class="episode-title">${ep.title} ${hookBadge}</div>
          <div style="display:flex; gap:6px; align-items:center;">
            <span style="color:#46d369; font-size:11.5px; font-weight:bold;">★ ${ep.rating || 8.0}</span>
            <div class="episode-runtime-badge">&#9201; ${ep.runtime_minutes} min</div>
          </div>
        </div>
        <div class="episode-overview">${ep.overview}</div>
      </div>
    `;
    listEl.appendChild(row);
  });
}

function renderSeasonSparkline(episodes, seasonNum, hookEpNum) {
  const box = document.getElementById("modal-season-sparkline");
  if (!box) return;
  if (!episodes || episodes.length < 2) {
    box.style.display = "none";
    return;
  }
  box.style.display = "block";

  const ratings = episodes.map(e => Number(e.rating || 8.0));
  const minR = Math.min(...ratings) - 0.25;
  const maxR = Math.max(...ratings) + 0.25;
  const w = 680, h = 76, padX = 28, padY = 16;

  const pts = episodes.map((ep, i) => {
    const x = padX + (i / Math.max(1, episodes.length - 1)) * (w - padX * 2);
    const y = h - padY - ((Number(ep.rating || 8.0) - minR) / Math.max(0.2, maxR - minR)) * (h - padY * 2);
    return { x, y, ep };
  });

  const polyPoints = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const circles = pts.map(p => {
    const isHook = p.ep.episode_number === hookEpNum;
    const color = isHook ? "#e50914" : "#46d369";
    const r = isHook ? 5.5 : 3.6;
    return `
      <g>
        <title>E${p.ep.episode_number}: ${p.ep.title} (★ ${p.ep.rating || 8.0})</title>
        <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1" />
        <text x="${p.x.toFixed(1)}" y="${h - 2}" fill="#888" font-size="9" text-anchor="middle">E${p.ep.episode_number}</text>
      </g>
    `;
  }).join("");

  box.innerHTML = `
    <div style="display:flex; justify-content:space-between; font-size:11px; color:#bbb; margin-bottom:4px;">
      <strong>📉 Curva de Calificación Episodio a Episodio (Temporada ${seasonNum}):</strong>
      <span><span style="color:#e50914;">●</span> Episodio Gancho &nbsp;|&nbsp; <span style="color:#46d369;">●</span> Nota IMDb/TMDB</span>
    </div>
    <svg width="100%" height="${h}" viewBox="0 0 ${w} ${h}">
      <polyline fill="none" stroke="#46d369" stroke-width="2" points="${polyPoints}" />
      ${circles}
    </svg>
  `;
}

function clickActorPill(actorName, movie) {
  sendInteraction({
    event_type: "actor_click",
    tconst: movie.tconst || "",
    title: `Actor: ${actorName}`,
    genres: movie.genres || "",
    country_code: movie.domestic_region || "",
    actors: actorName
  });
  closeModal();
  const searchInput = document.getElementById("search-input");
  if (searchInput) {
    searchInput.value = actorName;
    const clearBtn = document.getElementById("btn-clear-search");
    if (clearBtn) clearBtn.style.display = "inline-block";
    executeSearch(actorName);
  }
}

function closeModal() {
  stopModalTrailer();
  const modalBackdrop = document.getElementById("modal-backdrop");
  if (modalBackdrop) {
    modalBackdrop.classList.remove("active");
    document.body.style.overflow = "auto";
  }
  if (STATE.pendingRecData) {
    tryApplyPendingRecommendationsSubtly();
  }
}

// ------------------------------------------------------------------------------
// 8. SECCIÓN "PAÍSES CON MAYOR POTENCIAL" (MAPAS + INSPECTOR + MATRIZ DE DOBLAJE)
// ------------------------------------------------------------------------------
async function loadBusinessSection() {
  try {
    if (!STATE.businessDataCache) {
      const res = await fetch(`${CONFIG.API_BASE}/api/business/potential-countries`);
      STATE.businessDataCache = await res.json();
    }
    const data = STATE.businessDataCache;

    // 1. Dictamen del Hub Recomendado
    const hub = data.recommended_hub;
    document.getElementById("biz-recommended-country").textContent = hub.pais;
    document.getElementById("biz-recommended-strategy").textContent = hub.estrategia;
    document.getElementById("biz-justification").textContent = hub.justificacion_datos;

    document.getElementById("biz-metric-bayes").textContent = `${hub.metricas_clave.rating_bayesiano} (${hub.metricas_clave.rating_lift})`;
    document.getElementById("biz-metric-reach").textContent = `${hub.metricas_clave.promedio_regiones} (${hub.metricas_clave.reach_lift})`;
    document.getElementById("biz-metric-hours").textContent = hub.metricas_clave.horas_netflix_top10;

    const limitsList = document.getElementById("biz-limits-list");
    limitsList.innerHTML = "";
    hub.limitaciones_y_riesgos.forEach(lim => {
      const li = document.createElement("li");
      li.textContent = lim;
      limitsList.appendChild(li);
    });

    // 2. Renderizar los 3 Gráficos Interactivos Plotly
    const metricSelect = document.getElementById("map-metric-select");
    renderWorldMapPlotly(data.ranking, metricSelect ? metricSelect.value : "potential_score");
    if (metricSelect) {
      metricSelect.onchange = (e) => renderWorldMapPlotly(data.ranking, e.target.value);
    }
    renderQuadrantScatterPlotly(data.ranking, data.global_benchmark);
    renderDubbingBarPlotly(data.ranking);
    renderHistoryErasPlotly(data.tech_eras_history || []);

    // 3. Inicializar el Inspector Ejecutivo con Corea del Sur (o el top 1) y el Comparador Head-to-Head
    const krRow = data.ranking.find(r => r.codigo_pais === "KR") || data.ranking[0];
    if (krRow) {
      inspectCountryExecutiveCard(krRow);
    }
    initHeadToHeadComparator(data.ranking);

    // 4. Renderizar Cascada Poblacional (Waterfall Funnel)
    const funnelContainer = document.getElementById("waterfall-funnel-container");
    funnelContainer.innerHTML = "";
    data.waterfall_funnel.forEach(step => {
      const row = document.createElement("div");
      row.className = "funnel-step";
      row.innerHTML = `
        <div>
          <strong style="color: #fff;">${step.etapa}</strong>
          <div style="color: #888; font-size: 11px;">${step.detalle}</div>
        </div>
        <div style="text-align: right;">
          <span style="color: #e50914; font-weight: bold; font-size: 16px;">${step.filas.toLocaleString()}</span>
          <div style="color: #bbb; font-size: 11px;">${step.pct_retenido}% del universo</div>
        </div>
      `;
      funnelContainer.appendChild(row);
    });

    // 5. Inicializar Optimizador Multi-País y Tabla Ordenable con Filtro en Vivo
    initPortfolioOptimizer();
    initSortableRankingTable(data.ranking);

  } catch (err) {
    console.error("[Business Section] Error:", err);
  }
}

async function updatePortfolioOptimizer() {
  const slider = document.getElementById("portfolio-budget-slider");
  const modeSel = document.getElementById("portfolio-mode-select");
  const label = document.getElementById("portfolio-budget-val");
  const strip = document.getElementById("portfolio-summary-strip");
  const bar = document.getElementById("portfolio-stacked-bar");
  const grid = document.getElementById("portfolio-cards-grid");
  if (!slider || !strip || !bar || !grid) return;

  const budget = parseInt(slider.value || "150", 10);
  const mode = modeSel ? modeSel.value : "balanced";
  if (label) label.textContent = `USD ${budget}M`;

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/business/optimize-portfolio?budget_m=${budget}&strategy_mode=${encodeURIComponent(mode)}`);
    const data = await res.json();
    const colors = ["#e50914", "#46d369", "#ffc107", "#00b4d8", "#9b5de5"];

    strip.innerHTML = `
      <div class="portfolio-kpi-pill">
        <div style="font-size:10.5px; color:#999;">Volumen Global Diversificado</div>
        <strong style="font-size:16px; color:#fff;">~${data.total_producciones} títulos originales / licencias</strong>
      </div>
      <div class="portfolio-kpi-pill">
        <div style="font-size:10.5px; color:#999;">Multiplicador vs. Filmar en Hollywood</div>
        <strong style="font-size:16px; color:#46d369;">${data.multiplicador_volumen_vs_hollywood}x más catálogo</strong>
        <span style="font-size:11px; color:#888;">(vs. ${data.hollywood_producciones_equivalentes} en EE.UU.)</span>
      </div>
      <div class="portfolio-kpi-pill">
        <div style="font-size:10.5px; color:#999;">Retorno de Consumo Proyectado</div>
        <strong style="font-size:16px; color:#ffc107;">~${Number(data.total_horas_proyectadas_m).toLocaleString()}M Horas Globales</strong>
      </div>
    `;

    bar.innerHTML = (data.allocations || []).map((a, i) => `
      <div style="width:${a.pct_presupuesto}%; background:${colors[i % colors.length]};"
           title="${a.pais}: ${a.pct_presupuesto}% (USD ${a.usd_millones}M)"></div>
    `).join("");

    grid.innerHTML = "";
    (data.allocations || []).forEach((a, i) => {
      const div = document.createElement("div");
      div.className = "portfolio-country-card";
      div.style.borderTop = `3px solid ${colors[i % colors.length]}`;
      div.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong style="font-size:12.5px; color:#fff;">${a.pais}</strong>
          <span style="font-size:12px; font-weight:800; color:${colors[i % colors.length]};">${a.pct_presupuesto}%</span>
        </div>
        <div style="font-size:10px; color:#999; margin:3px 0 6px 0;">${a.rol_cartera}</div>
        <div style="font-size:12px; color:#ddd;"><strong>USD ${a.usd_millones}M</strong> &rarr; ~${a.producciones_estimadas} títulos</div>
        <div style="font-size:10.5px; color:#46d369; margin-top:2px;">+${a.horas_proyectadas_m.toLocaleString()}M horas est.</div>
      `;
      div.onclick = () => {
        const found = (STATE.businessDataCache?.ranking || []).find(r => r.codigo_pais === a.codigo_pais);
        if (found) {
          inspectCountryExecutiveCard(found);
          document.getElementById("country-inspector-card")?.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      };
      grid.appendChild(div);
    });
  } catch (err) {
    console.error("[Portfolio Optimizer] Error:", err);
  }
}

function initPortfolioOptimizer() {
  const slider = document.getElementById("portfolio-budget-slider");
  const modeSel = document.getElementById("portfolio-mode-select");
  if (slider) slider.oninput = () => updatePortfolioOptimizer();
  if (modeSel) modeSel.onchange = () => updatePortfolioOptimizer();
  updatePortfolioOptimizer();
}

function initSortableRankingTable(ranking) {
  const filterInput = document.getElementById("country-table-filter");
  const headers = document.querySelectorAll("#exec-ranking-table th.sortable");

  const getFilteredAndSorted = () => {
    const q = (filterInput?.value || "").trim().toLowerCase();
    const filtered = ranking.filter(c =>
      c.pais.toLowerCase().includes(q) || c.estrategia_netflix.toLowerCase().includes(q)
    );
    const key = STATE.tableSortKey || "potential_score";
    const dir = STATE.tableSortAsc ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (key === "pais") return a.pais.localeCompare(b.pais) * dir;
      return ((Number(a[key]) || 0) - (Number(b[key]) || 0)) * dir;
    });
  };

  headers.forEach(th => {
    th.onclick = () => {
      const clickedKey = th.dataset.sort;
      if (STATE.tableSortKey === clickedKey) {
        STATE.tableSortAsc = !STATE.tableSortAsc;
      } else {
        STATE.tableSortKey = clickedKey;
        // Para costo TMDB conviene primer clic ascendente (más económico primero), resto descendente
        STATE.tableSortAsc = (clickedKey === "median_budget_usd_m" || clickedKey === "pais");
      }
      headers.forEach(h => h.classList.remove("active-sort"));
      th.classList.add("active-sort");
      renderRankingTableRows(getFilteredAndSorted());
    };
  });

  if (filterInput) {
    filterInput.oninput = () => renderRankingTableRows(getFilteredAndSorted());
  }
  renderRankingTableRows(getFilteredAndSorted());
}

function renderRankingTableRows(rows) {
  const tbody = document.getElementById("ranking-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  rows.forEach((c, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.countryCode = c.codigo_pais;
    if (c.codigo_pais === STATE.activeCountryCode) {
      tr.classList.add("active-country-row");
    }
    let strategyClass = "regional";
    if (c.estrategia_netflix.includes("Tier 1")) strategyClass = "tier1";
    if (c.estrategia_netflix.includes("Joya")) strategyClass = "gem";

    tr.innerHTML = `
      <td style="color:#888; font-weight:bold;">${idx + 1}</td>
      <td><strong>${c.pais}</strong></td>
      <td><strong style="color:#fff; background:#262626; padding:2px 8px; border-radius:4px;">${c.potential_score}/100</strong></td>
      <td><strong style="color:#9ad1ff;">${c.bias_adjusted_score}/100</strong> <span style="font-size:10.5px; color:#888;">(${c.selection_bias_multiplier}x)</span></td>
      <td><strong style="color:#ddd;">USD ${c.median_budget_usd_m}M</strong></td>
      <td><strong style="color: #46d369;">★ ${c.rating_bayesiano_medio}</strong> (${c.rating_lift > 0 ? '+' : ''}${c.rating_lift})</td>
      <td>${c.promedio_regiones} (${c.reach_lift > 0 ? '+' : ''}${c.reach_lift})</td>
      <td><span style="color:#ffc107; font-weight:bold;">${c.multiplicador_doblaje}x</span></td>
      <td><strong>${c.millones_horas_netflix} M</strong></td>
      <td><span class="badge-strategy ${strategyClass}">${c.estrategia_netflix}</span></td>
    `;

    tr.onclick = () => {
      inspectCountryExecutiveCard(c);
      document.getElementById("country-inspector-card")?.scrollIntoView({ behavior: "smooth", block: "center" });
    };
    tbody.appendChild(tr);
  });
}

async function inspectCountryExecutiveCard(countryRow) {
  if (!countryRow) return;
  STATE.activeCountryCode = countryRow.codigo_pais;
  document.querySelectorAll("#ranking-table-body tr").forEach(tr => {
    tr.classList.toggle("active-country-row", tr.dataset.countryCode === countryRow.codigo_pais);
  });
  document.getElementById("insp-strategy-badge").textContent = `${countryRow.estrategia_netflix} • POTENCIAL ${countryRow.potential_score}/100`;
  document.getElementById("insp-country-title").textContent = countryRow.pais;

  document.getElementById("insp-val-bayes").textContent = `★ ${countryRow.rating_bayesiano_medio} (${countryRow.rating_lift > 0 ? '+' : ''}${countryRow.rating_lift} vs Global)`;
  const bayesPct = Math.min(100, Math.max(20, ((countryRow.rating_bayesiano_medio - 5.5) / 2.0) * 100));
  document.getElementById("insp-fill-bayes").style.width = `${bayesPct}%`;

  document.getElementById("insp-val-reach").textContent = `${countryRow.promedio_regiones} países (${countryRow.reach_lift > 0 ? '+' : ''}${countryRow.reach_lift})`;
  const reachPct = Math.min(100, Math.max(15, (countryRow.promedio_regiones / 25.0) * 100));
  document.getElementById("insp-fill-reach").style.width = `${reachPct}%`;

  document.getElementById("insp-val-dub").textContent = `${countryRow.multiplicador_doblaje}x más alcance (${countryRow.reach_con_doblaje} vs ${countryRow.reach_sin_doblaje} países)`;
  const dubPct = Math.min(100, Math.max(20, (countryRow.multiplicador_doblaje / 4.2) * 100));
  document.getElementById("insp-fill-dub").style.width = `${dubPct}%`;

  const btnOpen = document.getElementById("insp-btn-open-carousel");
  btnOpen.onclick = () => loadCountryCarousel(countryRow.codigo_pais, countryRow.pais);

  // Actualizar Simulador de CAPEX / ROI para el país seleccionado
  const roiSlider = document.getElementById("roi-budget-slider");
  if (roiSlider) {
    updateCountryROISimulator(countryRow, parseInt(roiSlider.value || "50", 10));
    roiSlider.oninput = (e) => updateCountryROISimulator(countryRow, parseInt(e.target.value, 10));
  }

  // Cargar las 6 mejores películas del país en miniatura dentro del inspector
  const miniContainer = document.getElementById("insp-mini-movies");
  miniContainer.innerHTML = `<div style="color:#888; font-size:12px; grid-column: 1 / -1;">Cargando títulos emblemáticos de ${countryRow.pais}...</div>`;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/country/${countryRow.codigo_pais}/titles?limit=6`);
    const data = await res.json();
    miniContainer.innerHTML = "";
    (data.titles || []).slice(0, 6).forEach(m => {
      const div = document.createElement("div");
      div.className = "insp-mini-card";
      div.title = `${m.primaryTitle} (★ ${m.bayesian_rating})`;
      const posterSrc = `${CONFIG.API_BASE}/api/poster/${m.tconst}?title=${encodeURIComponent(m.primaryTitle)}&year=${m.startYear}&rating=${m.bayesian_rating}`;
      div.innerHTML = `
        <img src="${posterSrc}" alt="${m.primaryTitle}" loading="lazy" />
        <div class="insp-mini-title">${m.primaryTitle}</div>
      `;
      div.onclick = () => openModal(m, false);
      miniContainer.appendChild(div);
    });
  } catch (err) {
    console.error("[Country Inspector] Error:", err);
  }
}

function updateCountryROISimulator(countryRow, budgetMillions) {
  const labelEl = document.getElementById("roi-budget-label");
  const auditMetaEl = document.getElementById("roi-audit-meta");
  const titlesEl = document.getElementById("roi-titles-val");
  const hoursEl = document.getElementById("roi-hours-val");
  const savingEl = document.getElementById("roi-saving-val");
  if (!labelEl || !countryRow) return;

  labelEl.textContent = `USD ${budgetMillions}M`;
  // Costo mediano real por producción auditado desde TMDB frente al benchmark de USD 22.0M en Hollywood
  const hollywoodBenchmark = 22.0;
  const isTier1 = countryRow.estrategia_netflix.includes("Tier 1");
  const avgCostPerTitle = Number(countryRow.median_budget_usd_m || (isTier1 ? 6.2 : 3.8));
  const biasMult = Number(countryRow.selection_bias_multiplier || 1.12);
  const biasAdjScore = Number(countryRow.bias_adjusted_score || countryRow.potential_score);

  if (auditMetaEl) {
    auditMetaEl.innerHTML =
      `Costo mediano auditado TMDB: <strong style="color:#ddd;">USD ${avgCostPerTitle.toFixed(2)}M/título</strong> vs. USD 22M Hollywood • ` +
      `Ajuste sesgo IMDb: <strong style="color:#ffc107;">${biasMult.toFixed(2)}x</strong> (Potencial s/sesgo: <strong>${biasAdjScore}/100</strong>)`;
  }

  const estTitles = Math.max(1, Math.round(budgetMillions / Math.max(0.8, avgCostPerTitle)));

  // Horas proyectadas combinando eficiencia auditada, alcance transfronterizo y calidad bayesiana
  const reachFactor = (countryRow.promedio_regiones || 12) / 13.6;
  const qualityFactor = (countryRow.rating_bayesiano_medio || 6.6) / 6.51;
  const costEfficiencyBoost = Math.min(2.6, Math.max(0.75, 8.0 / Math.max(1.5, avgCostPerTitle)));
  const estHours = Math.round(budgetMillions * 4.8 * costEfficiencyBoost * reachFactor * qualityFactor);

  // Ahorro porcentual auditado frente a producir el mismo volumen en Hollywood (USD 22M)
  const savingPct = Math.min(90, Math.max(15, Math.round((1 - (avgCostPerTitle / hollywoodBenchmark)) * 100)));

  if (titlesEl) titlesEl.textContent = `~${estTitles} producciones`;
  if (hoursEl) hoursEl.textContent = `~${estHours.toLocaleString()}M Horas`;
  if (savingEl) savingEl.textContent = `-${savingPct}% vs Hollywood`;
}

function initHeadToHeadComparator(ranking) {
  const selA = document.getElementById("h2h-select-a");
  const selB = document.getElementById("h2h-select-b");
  const box = document.getElementById("h2h-comparison-box");
  if (!selA || !selB || !box || !ranking || ranking.length < 2) return;

  selA.innerHTML = "";
  selB.innerHTML = "";
  ranking.slice(0, 25).forEach(r => {
    const optA = document.createElement("option");
    optA.value = r.codigo_pais;
    optA.textContent = r.pais;
    selA.appendChild(optA);

    const optB = document.createElement("option");
    optB.value = r.codigo_pais;
    optB.textContent = r.pais;
    selB.appendChild(optB);
  });

  selA.value = ranking.find(r => r.codigo_pais === "KR") ? "KR" : ranking[0].codigo_pais;
  selB.value = ranking.find(r => r.codigo_pais === "AR") ? "AR" : (ranking[1]?.codigo_pais || ranking[0].codigo_pais);

  const renderH2H = () => {
    const rowA = ranking.find(r => r.codigo_pais === selA.value) || ranking[0];
    const rowB = ranking.find(r => r.codigo_pais === selB.value) || ranking[1];
    const winner = rowA.potential_score >= rowB.potential_score ? rowA : rowB;

    box.innerHTML = `
      <div style="display:grid; grid-template-columns: 1fr auto 1fr; gap:10px; text-align:center; align-items:center; margin-bottom:8px;">
        <div><strong style="color:#fff;">${rowA.pais}</strong><div style="color:#46d369; font-weight:bold;">★ ${rowA.rating_bayesiano_medio} Bayes</div></div>
        <div style="color:#777; font-size:10px; text-transform:uppercase;">Calidad Crítica</div>
        <div><strong style="color:#fff;">${rowB.pais}</strong><div style="color:#46d369; font-weight:bold;">★ ${rowB.rating_bayesiano_medio} Bayes</div></div>

        <div style="color:#e50914; font-weight:bold;">${rowA.promedio_regiones} países</div>
        <div style="color:#777; font-size:10px; text-transform:uppercase;">Alcance Exportación</div>
        <div style="color:#e50914; font-weight:bold;">${rowB.promedio_regiones} países</div>

        <div style="color:#ffc107; font-weight:bold;">${rowA.multiplicador_doblaje}x (${rowA.millones_horas_netflix}M h)</div>
        <div style="color:#777; font-size:10px; text-transform:uppercase;">Doblaje & Horas</div>
        <div style="color:#ffc107; font-weight:bold;">${rowB.multiplicador_doblaje}x (${rowB.millones_horas_netflix}M h)</div>

        <div style="color:#9ad1ff; font-weight:bold;">USD ${rowA.median_budget_usd_m}M • ${rowA.bias_adjusted_score}/100</div>
        <div style="color:#777; font-size:10px; text-transform:uppercase;">Costo TMDB & s/Sesgo</div>
        <div style="color:#9ad1ff; font-weight:bold;">USD ${rowB.median_budget_usd_m}M • ${rowB.bias_adjusted_score}/100</div>
      </div>
      <div style="border-top:1px solid #262626; padding-top:6px; font-size:11px; color:#bbb; text-align:center;">
        🏆 <strong>Dictamen:</strong> <span style="color:#fff;">${winner.pais}</span> lidera en Índice Global (${winner.potential_score}/100) con estrategia <em>${winner.estrategia_netflix}</em>.
      </div>
    `;
  };

  selA.onchange = renderH2H;
  selB.onchange = renderH2H;
  renderH2H();
}

function renderWorldMapPlotly(ranking, metricKey) {
  const mapEl = document.getElementById("world-map-plotly");
  if (!mapEl || typeof Plotly === "undefined") return;

  const validRows = ranking.filter(r => r.iso3 && r.iso3.length === 3);
  const locations = validRows.map(r => r.iso3);
  const zValues = validRows.map(r => Number(r[metricKey] || 0));
  const customData = validRows.map(r => r.codigo_pais);
  const hoverTexts = validRows.map(r =>
    `<b>${r.pais}</b><br>` +
    `Estrategia: ${r.estrategia_netflix}<br>` +
    `Índice Potencial: <b>${r.potential_score}/100</b><br>` +
    `Potencial Ajustado Sesgo IMDb: <b>${r.bias_adjusted_score}/100</b> (${r.selection_bias_multiplier}x)<br>` +
    `Costo Mediano Auditado TMDB: <b>USD ${r.median_budget_usd_m}M</b> / título<br>` +
    `Eficiencia Capital: ${r.eficiencia_horas_por_usd_m}M horas / USD 1M<br>` +
    `Rating Bayesiano: ★ ${r.rating_bayesiano_medio} (${r.rating_lift > 0 ? '+' : ''}${r.rating_lift})<br>` +
    `Alcance Promedio: ${r.promedio_regiones} países (${r.multiplicador_doblaje}x con doblaje)<br>` +
    `Horas Netflix Top 10: ${r.millones_horas_netflix}M h<br>` +
    `<i>(Clic para inspeccionar país)</i>`
  );

  const metricTitles = {
    potential_score: "Potencial (0-100)",
    bias_adjusted_score: "Potencial s/Sesgo",
    eficiencia_horas_por_usd_m: "Horas / USD 1M",
    rating_bayesiano_medio: "Rating Bayes",
    promedio_regiones: "Regiones",
    millones_horas_netflix: "Millones Horas",
    multiplicador_doblaje: "Mult. Doblaje"
  };

  const trace = {
    type: "choropleth",
    locationmode: "ISO-3",
    locations: locations,
    z: zValues,
    text: hoverTexts,
    hoverinfo: "text",
    customdata: customData,
    colorscale: [
      [0.0, "#1f1f1f"],
      [0.25, "#5c1014"],
      [0.55, "#b80710"],
      [0.8, "#e50914"],
      [1.0, "#ffbe0b"]
    ],
    marker: { line: { color: "#333", width: 0.7 } },
    colorbar: {
      title: { text: metricTitles[metricKey] || "Valor", font: { color: "#ccc", size: 11 } },
      tickfont: { color: "#aaa", size: 10 },
      bgcolor: "rgba(0,0,0,0)"
    }
  };

  const layout = {
    paper_bgcolor: "#181818",
    plot_bgcolor: "#181818",
    margin: { l: 0, r: 0, t: 10, b: 0 },
    geo: {
      bgcolor: "#181818",
      showframe: false,
      showcoastlines: true,
      coastlinecolor: "#333",
      showland: true,
      landcolor: "#222222",
      showocean: true,
      oceancolor: "#111111",
      showcountries: true,
      countrycolor: "#2c2c2c",
      projection: { type: "natural earth" }
    }
  };

  Plotly.newPlot(mapEl, [trace], layout, { responsive: true, displayModeBar: false });

  mapEl.on("plotly_click", (eventData) => {
    if (eventData.points && eventData.points.length > 0) {
      const code = eventData.points[0].customdata;
      const found = ranking.find(r => r.codigo_pais === code);
      if (found) inspectCountryExecutiveCard(found);
    }
  });
}

function renderQuadrantScatterPlotly(ranking, benchmark) {
  const chartEl = document.getElementById("quadrant-scatter-plotly");
  if (!chartEl || typeof Plotly === "undefined") return;

  const topRows = ranking.slice(0, 32);
  const xReach = topRows.map(r => r.promedio_regiones);
  const yBayes = topRows.map(r => r.rating_bayesiano_medio);
  const sizes = topRows.map(r => Math.max(11, Math.min(42, Math.sqrt(r.millones_horas_netflix || 10) * 1.15)));
  const labels = topRows.map(r => r.codigo_pais);
  const customData = topRows.map(r => r.codigo_pais);
  const colors = topRows.map(r => {
    if (r.estrategia_netflix.includes("Tier 1")) return "#e50914";
    if (r.estrategia_netflix.includes("Joya")) return "#ffc107";
    return "#46d369";
  });

  const hoverTexts = topRows.map(r =>
    `<b>${r.pais}</b><br>` +
    `Estrategia: ${r.estrategia_netflix}<br>` +
    `Rating Bayesiano: ★ ${r.rating_bayesiano_medio}<br>` +
    `Alcance Exportación: ${r.promedio_regiones} regiones<br>` +
    `Horas Top 10: ${r.millones_horas_netflix}M h`
  );

  const trace = {
    type: "scatter",
    mode: "markers+text",
    x: xReach,
    y: yBayes,
    text: labels,
    textposition: "top center",
    textfont: { color: "#ddd", size: 10 },
    hovertext: hoverTexts,
    hoverinfo: "text",
    customdata: customData,
    marker: {
      size: sizes,
      color: colors,
      opacity: 0.88,
      line: { color: "#fff", width: 1 }
    }
  };

  const bRating = (benchmark && benchmark.rating_bayesiano) ? benchmark.rating_bayesiano : 6.51;
  const bReach = (benchmark && benchmark.promedio_regiones) ? benchmark.promedio_regiones : 13.59;

  const layout = {
    paper_bgcolor: "#181818",
    plot_bgcolor: "#181818",
    margin: { l: 48, r: 20, t: 20, b: 42 },
    xaxis: {
      title: { text: "Alcance Promedio de Exportación (N° de Regiones)", font: { color: "#bbb", size: 11 } },
      tickfont: { color: "#999" },
      gridcolor: "#262626",
      zeroline: false
    },
    yaxis: {
      title: { text: "Calidad Crítica (Rating Bayesiano)", font: { color: "#bbb", size: 11 } },
      tickfont: { color: "#999" },
      gridcolor: "#262626",
      zeroline: false
    },
    shapes: [
      {
        type: "line",
        x0: bReach, x1: bReach,
        y0: Math.min(...yBayes) - 0.1, y1: Math.max(...yBayes) + 0.1,
        line: { color: "#666", width: 1, dash: "dot" }
      },
      {
        type: "line",
        x0: Math.min(...xReach) - 1, x1: Math.max(...xReach) + 1,
        y0: bRating, y1: bRating,
        line: { color: "#666", width: 1, dash: "dot" }
      }
    ]
  };

  Plotly.newPlot(chartEl, [trace], layout, { responsive: true, displayModeBar: false });

  chartEl.on("plotly_click", (eventData) => {
    if (eventData.points && eventData.points.length > 0) {
      const code = eventData.points[0].customdata;
      const found = ranking.find(r => r.codigo_pais === code);
      if (found) inspectCountryExecutiveCard(found);
    }
  });
}

function renderDubbingBarPlotly(ranking) {
  const chartEl = document.getElementById("dubbing-bar-plotly");
  if (!chartEl || typeof Plotly === "undefined") return;

  const top10 = ranking.slice(0, 10);
  const countries = top10.map(r => r.codigo_pais);
  const reachDubbed = top10.map(r => r.reach_con_doblaje);
  const reachSubOnly = top10.map(r => r.reach_sin_doblaje);

  const traceSub = {
    x: countries,
    y: reachSubOnly,
    name: "Solo Subtitulado (<4 idiomas)",
    type: "bar",
    marker: { color: "#444" }
  };

  const traceDub = {
    x: countries,
    y: reachDubbed,
    name: "Con Doblaje Multi-Idioma (≥4 idiomas)",
    type: "bar",
    marker: { color: "#e50914" }
  };

  const layout = {
    barmode: "group",
    paper_bgcolor: "#181818",
    plot_bgcolor: "#181818",
    margin: { l: 44, r: 16, t: 24, b: 38 },
    legend: { orientation: "h", y: 1.12, font: { color: "#ccc", size: 10.5 } },
    xaxis: { tickfont: { color: "#ccc" }, gridcolor: "#222" },
    yaxis: {
      title: { text: "N° de Mercados Alcanzados", font: { color: "#bbb", size: 11 } },
      tickfont: { color: "#999" },
      gridcolor: "#262626"
    }
  };

  Plotly.newPlot(chartEl, [traceSub, traceDub], layout, { responsive: true, displayModeBar: false });
}

function renderHistoryErasPlotly(erasHistory) {
  const chartEl = document.getElementById("history-eras-plotly");
  if (!chartEl || typeof Plotly === "undefined" || !erasHistory || erasHistory.length === 0) return;

  const eras = erasHistory.map(e => e.era);
  const nonAnglo = erasHistory.map(e => e.spillover_no_anglo);
  const anglo = erasHistory.map(e => e.spillover_anglo);

  const traceNonAnglo = {
    x: eras,
    y: nonAnglo,
    name: "Contenido Internacional (No-US/UK)",
    type: "scatter",
    mode: "lines+markers",
    line: { color: "#e50914", width: 3 },
    marker: { size: 9, color: "#e50914" }
  };

  const traceAnglo = {
    x: eras,
    y: anglo,
    name: "Contenido Anglosajón (US/UK)",
    type: "scatter",
    mode: "lines+markers",
    line: { color: "#888", width: 2, dash: "dot" },
    marker: { size: 7, color: "#888" }
  };

  const layout = {
    paper_bgcolor: "#181818",
    plot_bgcolor: "#181818",
    margin: { l: 44, r: 16, t: 24, b: 44 },
    legend: { orientation: "h", y: 1.15, font: { color: "#ccc", size: 10.5 } },
    xaxis: { tickfont: { color: "#ccc", size: 10 }, gridcolor: "#222" },
    yaxis: {
      title: { text: "% Títulos con Derrame Global (≥10 países)", font: { color: "#bbb", size: 10.5 } },
      tickfont: { color: "#999" },
      gridcolor: "#262626"
    }
  };

  Plotly.newPlot(chartEl, [traceNonAnglo, traceAnglo], layout, { responsive: true, displayModeBar: false });
}

async function loadCountryCarousel(countryCode, countryName) {
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/country/${countryCode}/titles`);
    const data = await res.json();
    
    clearSearchAndGoHome();
    const container = document.getElementById("carousels-container");
    
    let existingCountrySec = document.getElementById("carousel-country_selected");
    if (existingCountrySec) existingCountrySec.remove();

    const countryCarousel = createCarouselElement({
      id: "country_selected",
      title: `Top Producciones Exitosas de ${countryName}`,
      subtitle: `Catálogo emblemático desambiguado analizado para decisión de hub (${countryCode})`,
      items: data.titles
    });

    container.insertBefore(countryCarousel, container.firstChild);
    countryCarousel.scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    console.error("[Country Carousel] Error:", err);
  }
}

// ------------------------------------------------------------------------------
// 9. PANEL DE DEPURACIÓN (LEARNING PROFILE, GRAFO DE ACTORES & BANDIT DEBUGGER)
// ------------------------------------------------------------------------------
function initDebugPanel() {
  const btn = document.getElementById("btn-toggle-debug");
  const panel = document.getElementById("debug-panel");
  const closeBtn = document.getElementById("btn-close-debug");

  if (btn && panel) {
    btn.onclick = () => panel.classList.toggle("active");
  }
  if (closeBtn && panel) {
    closeBtn.onclick = () => panel.classList.remove("active");
  }

  window.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.key.toLowerCase() === "d") {
      e.preventDefault();
      panel.classList.toggle("active");
    }
  });
}

function updateDebugPanel() {
  const p = STATE.userProfile;
  const score = p.signal_score || 0;
  const threshold = 15.0;

  document.getElementById("debug-score-val").textContent = score.toFixed(1);
  const fillPct = Math.min(100, (score / threshold) * 100);
  document.getElementById("debug-meter-fill").style.width = `${fillPct}%`;
  
  const statusEl = document.getElementById("debug-gems-status");
  if (score >= threshold) {
    statusEl.innerHTML = "💎 <span style='color: #46d369;'>ACTIVADO</span>";
  } else {
    statusEl.textContent = `Faltan ${(threshold - score).toFixed(1)} pts`;
  }

  // Contextual Bandit Arm
  const banditEl = document.getElementById("debug-bandit-arm");
  if (banditEl) {
    const armLabels = {
      actor_focus: "Actor Star Artwork (Var #1)",
      genre_focus: "Genre Atmosphere Artwork",
      global_hit: "Global Top 10 Artwork"
    };
    banditEl.textContent = armLabels[p.active_bandit_arm] || "Global Top 10 Artwork";
  }

  // Top Géneros
  const genresList = document.getElementById("debug-genres-list");
  genresList.innerHTML = "";
  const sortedGenres = Object.entries(p.genres || {}).sort((a,b) => b[1] - a[1]).slice(0, 5);
  if (sortedGenres.length === 0) {
    genresList.innerHTML = `<li style="color:#666;">Sin interacciones</li>`;
  } else {
    sortedGenres.forEach(([g, w]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${g}</span><strong>${w} pts</strong>`;
      genresList.appendChild(li);
    });
  }

  // Top Países
  const countriesList = document.getElementById("debug-countries-list");
  countriesList.innerHTML = "";
  const sortedCountries = Object.entries(p.countries || {}).sort((a,b) => b[1] - a[1]).slice(0, 5);
  if (sortedCountries.length === 0) {
    countriesList.innerHTML = `<li style="color:#666;">Sin interacciones</li>`;
  } else {
    sortedCountries.forEach(([c, w]) => {
      const li = document.createElement("li");
      li.innerHTML = `<span>${c}</span><strong>${w} pts</strong>`;
      countriesList.appendChild(li);
    });
  }

  // Top Actores Favoritos (1-Hop Directos)
  const actorsList = document.getElementById("debug-actors-list");
  if (actorsList) {
    actorsList.innerHTML = "";
    const sortedActors = Object.entries(p.actors || {}).sort((a,b) => b[1] - a[1]).slice(0, 5);
    if (sortedActors.length === 0) {
      actorsList.innerHTML = `<li style="color:#666;">Sin interacciones</li>`;
    } else {
      sortedActors.forEach(([act, w]) => {
        const li = document.createElement("li");
        li.innerHTML = `<span>${act}</span><strong style="color:#46d369;">${w} pts</strong>`;
        actorsList.appendChild(li);
      });
    }
  }

  // Co-Estrellas Sugeridas por el Grafo (2-Hop)
  const coActorsList = document.getElementById("debug-coactors-list");
  if (coActorsList) {
    coActorsList.innerHTML = "";
    const sugg = p.suggested_actors || {};
    const suggEntries = Object.entries(sugg).slice(0, 5);
    if (suggEntries.length === 0) {
      coActorsList.innerHTML = `<li style="color:#666;">Esperando señal...</li>`;
    } else {
      suggEntries.forEach(([coAct, info]) => {
        const li = document.createElement("li");
        li.title = `Conectado vía ${info.via_actor} (${info.shared_title})`;
        li.innerHTML = `<span>${coAct}</span><strong style="color:#ffc107;">+${info.score}</strong>`;
        coActorsList.appendChild(li);
      });
    }
  }

  // Grafo Visual SVG (1-Hop -> 2-Hop)
  renderDebugGraphSVG(p.actors || {}, p.suggested_actors || {});

  // Log de acciones recientes
  const actionsList = document.getElementById("debug-actions-list");
  actionsList.innerHTML = "";
  (p.recent_actions || []).forEach(act => {
    const div = document.createElement("div");
    div.className = "debug-action-item";
    div.innerHTML = `[${act.event.toUpperCase()}] <strong>${act.title}</strong> (+${act.weight_added} pts)`;
    actionsList.appendChild(div);
  });
}

function renderDebugGraphSVG(directActors, suggestedActors) {
  const canvas = document.getElementById("debug-graph-canvas");
  if (!canvas) return;

  const topDirect = Object.entries(directActors).sort((a,b) => b[1] - a[1]).slice(0, 2);
  const topSugg = Object.entries(suggestedActors).slice(0, 4);

  if (topDirect.length === 0) {
    canvas.innerHTML = `<span style="color: #666; font-size: 10.5px;">Interactúa con películas o actores para visualizar el grafo...</span>`;
    return;
  }

  const w = 320, h = 110;
  let edgesSvg = "";
  let nodesSvg = "";

  const directPositions = topDirect.map(([name, score], i) => ({
    name,
    x: topDirect.length === 1 ? 105 : (75 + i * 95),
    y: 55
  }));

  const suggPositions = topSugg.map(([name, info], i) => {
    const angle = -0.9 + i * 0.6;
    return {
      name,
      via: info.via_actor,
      x: 245,
      y: 20 + i * 24
    };
  });

  suggPositions.forEach(s => {
    const src = directPositions.find(d => d.name === s.via) || directPositions[0];
    if (src) {
      edgesSvg += `<line x1="${src.x}" y1="${src.y}" x2="${s.x}" y2="${s.y}" stroke="#555" stroke-width="1.2" stroke-dasharray="3,2" />`;
    }
  });

  directPositions.forEach(d => {
    const shortName = d.name.length > 14 ? d.name.slice(0, 12) + ".." : d.name;
    nodesSvg += `
      <circle cx="${d.x}" cy="${d.y}" r="8" fill="#46d369" stroke="#fff" stroke-width="1.2" />
      <text x="${d.x}" y="${d.y + 19}" fill="#46d369" font-size="9.5" font-weight="bold" text-anchor="middle">${shortName}</text>
    `;
  });

  suggPositions.forEach(s => {
    const shortName = s.name.length > 14 ? s.name.slice(0, 12) + ".." : s.name;
    nodesSvg += `
      <circle cx="${s.x}" cy="${s.y}" r="5.5" fill="#ffc107" stroke="#222" stroke-width="1" />
      <text x="${s.x + 9}" y="${s.y + 3}" fill="#ffd54f" font-size="9" text-anchor="start">${shortName}</text>
    `;
  });

  canvas.innerHTML = `<svg width="100%" height="100%" viewBox="0 0 ${w} ${h}">${edgesSvg}${nodesSvg}</svg>`;
}

// ------------------------------------------------------------------------------
// 10. BUSCADOR EXCLUSIVO (POR PELÍCULA, ACTOR, GÉNERO O PAÍS + ACTORES DEL PAÍS)
// ------------------------------------------------------------------------------
function initSearch() {
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("btn-clear-search");
  const acBox = document.getElementById("search-autocomplete");
  const searchWrap = document.getElementById("search-box-wrap");
  const sortSelect = document.getElementById("search-sort-select");
  let debounceTimeout = null;
  let acTimeout = null;

  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    clearTimeout(debounceTimeout);
    clearTimeout(acTimeout);
    const query = e.target.value.trim();

    if (clearBtn) {
      clearBtn.style.display = query.length > 0 ? "inline-block" : "none";
    }

    if (!query) {
      if (acBox) acBox.style.display = "none";
      clearSearchAndGoHome();
      return;
    }

    if (query.length >= 2) {
      acTimeout = setTimeout(() => fetchSearchAutocomplete(query), 140);
    }

    debounceTimeout = setTimeout(() => {
      executeSearch(query);
    }, 300);
  });

  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && acBox) {
      acBox.style.display = "none";
    }
  });

  document.addEventListener("click", (e) => {
    if (acBox && searchWrap && !searchWrap.contains(e.target)) {
      acBox.style.display = "none";
    }
  });

  // Filtros rápidos en resultados de búsqueda (Todo / Películas / Series + Orden)
  document.querySelectorAll("#search-filter-bar .filter-chip").forEach(chip => {
    chip.onclick = () => {
      document.querySelectorAll("#search-filter-bar .filter-chip").forEach(c => c.classList.remove("active"));
      chip.classList.add("active");
      STATE.searchTypeFilter = chip.dataset.filter || "all";
      renderFilteredSearchGrids();
    };
  });

  if (sortSelect) {
    sortSelect.onchange = (e) => {
      STATE.searchSortMode = e.target.value || "relevance";
      renderFilteredSearchGrids();
    };
  }

  if (clearBtn) {
    clearBtn.onclick = () => {
      if (acBox) acBox.style.display = "none";
      clearSearchAndGoHome();
    };
  }
}

async function fetchSearchAutocomplete(query) {
  const acBox = document.getElementById("search-autocomplete");
  if (!acBox) return;
  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/autocomplete?q=${encodeURIComponent(query)}`);
    const data = await res.json();
    const list = data.suggestions || [];
    if (list.length === 0) {
      acBox.style.display = "none";
      return;
    }
    acBox.innerHTML = "";
    list.forEach(item => {
      const div = document.createElement("div");
      div.className = "ac-item";
      div.innerHTML = `
        <span class="ac-icon">${item.icon}</span>
        <div style="overflow:hidden;">
          <div class="ac-label">${item.label}</div>
          <div class="ac-sub">${item.sub}</div>
        </div>
      `;
      div.onclick = () => {
        acBox.style.display = "none";
        const searchInput = document.getElementById("search-input");
        if (searchInput) searchInput.value = item.query;
        executeSearch(item.query);
      };
      acBox.appendChild(div);
    });
    acBox.style.display = "block";
  } catch (err) {
    acBox.style.display = "none";
  }
}

function filterAndSortItemsList(items) {
  let out = [...(items || [])];
  if (STATE.searchTypeFilter === "movie") {
    out = out.filter(m => !m.is_series && m.titleType !== "tvSeries" && m.titleType !== "tvMiniSeries");
  } else if (STATE.searchTypeFilter === "series") {
    out = out.filter(m => m.is_series || m.titleType === "tvSeries" || m.titleType === "tvMiniSeries");
  }

  if (STATE.searchSortMode === "bayes") {
    out.sort((a, b) => (Number(b.bayesian_rating) || 0) - (Number(a.bayesian_rating) || 0));
  } else if (STATE.searchSortMode === "year") {
    out.sort((a, b) => (Number(b.startYear) || 0) - (Number(a.startYear) || 0));
  }
  return out;
}

function renderFilteredSearchGrids() {
  if (!STATE.lastSearchRawData) return;
  const directGrid = document.getElementById("search-direct-grid");
  const similarGrid = document.getElementById("search-similar-grid");
  const similarBlock = document.getElementById("search-similar-block");
  if (!directGrid || !similarGrid) return;

  const filteredDirect = filterAndSortItemsList(STATE.lastSearchRawData.direct_matches || []);
  const filteredSimilar = filterAndSortItemsList(STATE.lastSearchRawData.similar_titles || []);

  directGrid.innerHTML = "";
  if (filteredDirect.length === 0) {
    directGrid.innerHTML = `<div style="color:#888; padding:16px;">No hay títulos con el filtro seleccionado.</div>`;
  } else {
    filteredDirect.forEach(movie => directGrid.appendChild(createMovieCard(movie)));
  }

  similarGrid.innerHTML = "";
  if (filteredSimilar.length > 0 && similarBlock) {
    similarBlock.style.display = "block";
    filteredSimilar.forEach(movie => similarGrid.appendChild(createMovieCard(movie)));
  } else if (similarBlock) {
    similarBlock.style.display = "none";
  }
}

async function executeSearch(query) {
  STATE.isSearching = true;
  switchSection("home");

  const homeCatalogView = document.getElementById("home-catalog-view");
  const searchResultsView = document.getElementById("search-results-view");
  if (homeCatalogView) homeCatalogView.style.display = "none";
  if (searchResultsView) searchResultsView.style.display = "block";

  const titleEl = document.getElementById("search-view-title");
  const subEl = document.getElementById("search-view-subtitle");
  const actorsBlock = document.getElementById("search-actors-block");
  const actorsHeading = document.getElementById("search-actors-heading");
  const actorsPills = document.getElementById("search-actors-pills");
  const directHeading = document.getElementById("search-direct-heading");
  const directGrid = document.getElementById("search-direct-grid");
  const similarBlock = document.getElementById("search-similar-block");
  const similarHeading = document.getElementById("search-similar-heading");
  const similarSub = document.getElementById("search-similar-sub");
  const similarGrid = document.getElementById("search-similar-grid");

  titleEl.textContent = `Resultados para "${query}"`;
  subEl.textContent = `Buscando películas, series, países, actores y géneros relacionados...`;
  directGrid.innerHTML = `<div style="color:#aaa; padding:20px;">Consultando catálogo maestro desambiguado...</div>`;
  similarGrid.innerHTML = "";
  if (actorsBlock) actorsBlock.style.display = "none";

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/search?q=${encodeURIComponent(query)}&session_id=${CONFIG.SESSION_ID}`);
    const data = await res.json();
    STATE.lastSearchRawData = data;

    directGrid.innerHTML = "";
    similarGrid.innerHTML = "";

    const directItems = data.direct_matches || [];
    const similarItems = data.similar_titles || [];
    const relatedActors = data.country_actors || [];

    if (directItems.length === 0) {
      subEl.textContent = `No se hallaron coincidencias para "${query}". Prueba buscando por país (ej: Argentina, España, Corea), título, actor o género.`;
      directGrid.innerHTML = `<div style="color:#888; padding:16px;">Sin coincidencias directas.</div>`;
      similarBlock.style.display = "none";
      return;
    }

    // Renderizar bloque de Actores del País o de la Búsqueda
    if (actorsBlock && actorsPills && relatedActors.length > 0) {
      actorsBlock.style.display = "block";
      actorsHeading.innerHTML = data.is_country_search
        ? `🎭 Actores y Protagonistas Destacados de <strong>${data.country_name}</strong> <span style="font-size:11px; color:#888; font-weight:normal;">(Clic en un actor para ver sus películas)</span>:`
        : `🎭 Actores Relacionados con tu Búsqueda <span style="font-size:11px; color:#888; font-weight:normal;">(Clic para explorar su filmografía)</span>:`;
      actorsPills.innerHTML = "";
      relatedActors.forEach(actorName => {
        const btn = document.createElement("button");
        btn.className = "actor-pill";
        btn.textContent = actorName;
        btn.onclick = () => {
          const searchInput = document.getElementById("search-input");
          if (searchInput) searchInput.value = actorName;
          executeSearch(actorName);
        };
        actorsPills.appendChild(btn);
      });
    }

    if (data.is_country_search) {
      titleEl.textContent = `🌍 Películas, Series y Talento de ${data.country_name}`;
      subEl.textContent = `Mostrando las ${directItems.length} producciones más exitosas originarias de ${data.country_name} y su elenco representativo`;
      if (directHeading) directHeading.textContent = `Top Películas y Series de ${data.country_name}`;
    } else {
      titleEl.textContent = `Resultados para "${query}"`;
      subEl.textContent = `Mostrando ${directItems.length} coincidencias canónicas y recomendaciones de géneros similares (${data.seed_genres || 'Afines'})`;
      if (directHeading) directHeading.textContent = `Coincidencias Principales`;
    }

    if (similarItems.length > 0) {
      similarHeading.textContent = data.is_country_search
        ? `Recomendaciones Transfronterizas Afines a ${data.country_name}`
        : `Películas y Géneros Similares a "${data.seed_title || query}"`;
      similarSub.textContent = `Títulos seleccionados por similitud temática (${data.seed_genres || 'General'}), atmósfera y grafo de actores`;
    }
    renderFilteredSearchGrids();
  } catch (err) {
    console.error("[Search] Error:", err);
  }
}

function clearSearchAndGoHome() {
  STATE.isSearching = false;
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("btn-clear-search");
  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.style.display = "none";

  const homeCatalogView = document.getElementById("home-catalog-view");
  const searchResultsView = document.getElementById("search-results-view");
  if (searchResultsView) searchResultsView.style.display = "none";
  if (homeCatalogView) homeCatalogView.style.display = "block";

  switchSection("home");
}
