/**
 * NETFLIX GLOBAL STREAMING, GRAPH AI & EXECUTIVE ANALYTICS (CLIENT ENGINE v4.0)
 * - Desambiguación canónica de títulos homónimos
 * - Descripciones, géneros y episodios traducidos al español (es-ES)
 * - Sección 'Mi Lista' con recomendador dedicado
 * - Actualización sutil y no intrusiva de carruseles (off-viewport / cross-fade)
 * - Tráilers de YouTube embebidos, Hook Episode Analysis, Contextual Bandit y Matriz de Doblaje
 */

const CONFIG = {
  MIN_HOVER_DWELL_MS: 800,
  API_BASE: "",
  SESSION_ID: "session_" + (localStorage.getItem("netflix_user_id") || (() => {
    const id = Math.random().toString(36).substring(2, 9);
    localStorage.setItem("netflix_user_id", id);
    return id;
  })())
};

let STATE = {
  activeSection: "home",
  isSearching: false,
  infinitePage: 1,
  isLoadingInfinite: false,
  businessDataCache: null,
  pendingRecData: null,
  currentModalTrailerKey: null,
  myList: JSON.parse(localStorage.getItem("netflix_my_list") || "[]"),
  userProfile: {
    genres: {},
    countries: {},
    actors: {},
    suggested_actors: {},
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
  initSearch();
  initDebugPanel();
  initInfiniteScroll();
  loadInitialCatalog();
});

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
  const gemsSec = document.getElementById("section-gems");
  const bizSec = document.getElementById("section-business");

  homeSec.style.display = "none";
  if (mylistSec) mylistSec.style.display = "none";
  if (gemsSec) gemsSec.style.display = "none";
  if (bizSec) bizSec.classList.remove("active");

  if (sectionId === "business") {
    bizSec.classList.add("active");
    loadBusinessSection();
  } else if (sectionId === "mylist") {
    mylistSec.style.display = "block";
    loadMyListSection();
  } else if (sectionId === "gems") {
    gemsSec.style.display = "block";
    loadHiddenGemsSection("all");
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

    if (data.hero) renderHero(data.hero);
    if (data.carousels) renderCarousels(data.carousels);
    
    refreshUserRecommendations(true);
  } catch (err) {
    console.error("[Catalog] Error al cargar:", err);
  }
}

function renderHero(hero) {
  const heroEl = document.querySelector(".hero-banner");
  if (!heroEl || !hero) return;

  const backdropUrl = `${CONFIG.API_BASE}/api/backdrop/${hero.tconst}`;
  heroEl.style.backgroundImage = `linear-gradient(to right, rgba(20, 20, 20, 0.95) 25%, rgba(20, 20, 20, 0.58) 60%, rgba(20, 20, 20, 0.15) 100%), linear-gradient(0deg, #141414 0%, transparent 60%), url('${backdropUrl}')`;

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
  (carouselData.items || []).forEach(movie => {
    const card = createMovieCard(movie);
    track.appendChild(card);
  });

  const leftBtn = sec.querySelector(".carousel-btn.left");
  const rightBtn = sec.querySelector(".carousel-btn.right");
  leftBtn.onclick = () => track.scrollBy({ left: -620, behavior: "smooth" });
  rightBtn.onclick = () => track.scrollBy({ left: 620, behavior: "smooth" });

  return sec;
}

function createMovieCard(movie, subtleEnter = false) {
  const card = document.createElement("div");
  card.className = subtleEnter ? "movie-card subtle-enter" : "movie-card";
  card.dataset.tconst = movie.tconst;

  const inList = STATE.myList.includes(movie.tconst);
  const genresDisplay = movie.genres_es || movie.genres || "";
  // Contextual Artwork Bandit variant (0 o 1 según el brazo activo del usuario)
  const banditVariant = (STATE.userProfile.active_bandit_arm === "actor_focus") ? 1 : 0;
  const posterSrc = `${CONFIG.API_BASE}/api/poster/${movie.tconst}?title=${encodeURIComponent(movie.primaryTitle)}&year=${movie.startYear}&rating=${movie.bayesian_rating}&genres=${encodeURIComponent(genresDisplay)}&variant=${banditVariant}`;
  const isSeriesBadge = (movie.is_series || movie.titleType === "tvSeries" || movie.titleType === "tvMiniSeries")
    ? `<span style="background:#e50914; color:#fff; font-size:9px; font-weight:800; padding:1px 5px; border-radius:2px;">SERIE</span>`
    : "";

  card.innerHTML = `
    <img class="poster-img" src="${posterSrc}" alt="${movie.primaryTitle}" loading="lazy" />
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

  return card;
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
    if (["click", "modal_open", "my_list", "actor_click"].includes(eventData.event_type)) {
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
      container.insertBefore(newAffinity, container.children[1] || null);
    }
  }

  if (data.gems_carousel && data.gems_carousel.items && data.gems_carousel.items.length > 0) {
    let existingGems = document.getElementById("carousel-hidden_gems");
    const newGems = createCarouselElement(data.gems_carousel);
    if (existingGems) {
      container.replaceChild(newGems, existingGems);
    } else {
      container.insertBefore(newGems, container.children[2] || null);
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
async function openModal(movie, autoplayTrailer = false) {
  const modalBackdrop = document.getElementById("modal-backdrop");
  if (!modalBackdrop) return;

  stopModalTrailer();
  STATE.currentModalTrailerKey = null;

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

  // Botón Mi Lista
  const modalListBtn = document.getElementById("modal-btn-list");
  const inList = STATE.myList.includes(movie.tconst);
  modalListBtn.textContent = inList ? "✓ En Mi Lista" : "+ Agregar a Mi Lista";
  modalListBtn.onclick = () => {
    toggleMyList(movie, null);
    const isNow = STATE.myList.includes(movie.tconst);
    modalListBtn.textContent = isNow ? "✓ En Mi Lista" : "+ Agregar a Mi Lista";
  };

  // Botón Reproducir / Tráiler
  const playBtn = document.getElementById("modal-btn-play");
  playBtn.innerHTML = "&#9658; Ver Tráiler Oficial / Reproducir";
  playBtn.onclick = () => playModalTrailer(movie.primaryTitle);

  const seriesSec = document.getElementById("modal-series-section");
  seriesSec.style.display = "none";

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
  } catch (err) {
    console.error("[Modal Details] Error:", err);
  }
}

function playModalTrailer(titleName) {
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

  episodes.forEach(ep => {
    const isHook = hookEpNum === ep.episode_number;
    const row = document.createElement("div");
    row.className = "episode-row";
    if (isHook) {
      row.style.borderColor = "rgba(229, 9, 20, 0.65)";
      row.style.background = "rgba(229, 9, 20, 0.08)";
    }
    row.onclick = () => showSubtleToast(`▶ Reproduciendo T${seasonNum}:E${ep.episode_number} - "${ep.title}" (${ep.runtime_minutes} min)`);

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

    // 3. Inicializar el Inspector Ejecutivo con Corea del Sur (o el top 1)
    const krRow = data.ranking.find(r => r.codigo_pais === "KR") || data.ranking[0];
    if (krRow) {
      inspectCountryExecutiveCard(krRow);
    }

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

    // 5. Renderizar Tabla de Ranking con Filtro en Vivo
    renderRankingTableRows(data.ranking);
    const filterInput = document.getElementById("country-table-filter");
    if (filterInput) {
      filterInput.oninput = (e) => {
        const q = e.target.value.trim().toLowerCase();
        const filtered = data.ranking.filter(c =>
          c.pais.toLowerCase().includes(q) || c.estrategia_netflix.toLowerCase().includes(q)
        );
        renderRankingTableRows(filtered);
      };
    }

  } catch (err) {
    console.error("[Business Section] Error:", err);
  }
}

function renderRankingTableRows(rows) {
  const tbody = document.getElementById("ranking-table-body");
  if (!tbody) return;
  tbody.innerHTML = "";

  rows.forEach((c, idx) => {
    const tr = document.createElement("tr");
    let strategyClass = "regional";
    if (c.estrategia_netflix.includes("Tier 1")) strategyClass = "tier1";
    if (c.estrategia_netflix.includes("Joya")) strategyClass = "gem";

    tr.innerHTML = `
      <td style="color:#888; font-weight:bold;">${idx + 1}</td>
      <td><strong>${c.pais}</strong></td>
      <td><strong style="color:#fff; background:#262626; padding:2px 8px; border-radius:4px;">${c.potential_score}/100</strong></td>
      <td>${c.total_titulos.toLocaleString()}</td>
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
    `Rating Bayesiano: ★ ${r.rating_bayesiano_medio} (${r.rating_lift > 0 ? '+' : ''}${r.rating_lift})<br>` +
    `Alcance Promedio: ${r.promedio_regiones} países<br>` +
    `Efecto Doblaje: ${r.multiplicador_doblaje}x<br>` +
    `Horas Netflix Top 10: ${r.millones_horas_netflix}M h<br>` +
    `<i>(Clic para inspeccionar país)</i>`
  );

  const metricTitles = {
    potential_score: "Potencial (0-100)",
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

// ------------------------------------------------------------------------------
// 10. BUSCADOR EXCLUSIVO (OCULTA CATEGORÍAS DE INICIO Y MUESTRA SIMILARES)
// ------------------------------------------------------------------------------
function initSearch() {
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("btn-clear-search");
  const countrySelect = document.getElementById("nav-country-select");
  let debounceTimeout = null;

  if (countrySelect) {
    countrySelect.onchange = (e) => {
      const code = e.target.value;
      if (!code) {
        clearSearchAndGoHome();
      } else {
        const selectedLabel = countrySelect.options[countrySelect.selectedIndex].text.replace(/^[^\s]+\s/, "");
        if (searchInput) searchInput.value = selectedLabel;
        if (clearBtn) clearBtn.style.display = "inline-block";
        executeSearch(code);
      }
    };
  }

  if (!searchInput) return;

  searchInput.addEventListener("input", (e) => {
    clearTimeout(debounceTimeout);
    const query = e.target.value.trim();

    if (clearBtn) {
      clearBtn.style.display = query.length > 0 ? "inline-block" : "none";
    }

    if (!query) {
      clearSearchAndGoHome();
      return;
    }

    debounceTimeout = setTimeout(() => {
      executeSearch(query);
    }, 280);
  });

  if (clearBtn) {
    clearBtn.onclick = () => {
      clearSearchAndGoHome();
    };
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

  try {
    const res = await fetch(`${CONFIG.API_BASE}/api/catalog/search?q=${encodeURIComponent(query)}&session_id=${CONFIG.SESSION_ID}`);
    const data = await res.json();

    directGrid.innerHTML = "";
    similarGrid.innerHTML = "";

    const directItems = data.direct_matches || [];
    const similarItems = data.similar_titles || [];

    if (directItems.length === 0) {
      subEl.textContent = `No se hallaron coincidencias para "${query}". Prueba buscando por país (ej: Argentina, España, Corea), título, actor o género.`;
      directGrid.innerHTML = `<div style="color:#888; padding:16px;">Sin coincidencias directas.</div>`;
      similarBlock.style.display = "none";
      return;
    }

    if (data.is_country_search) {
      titleEl.textContent = `🌍 Catálogo de ${data.country_name}`;
      subEl.textContent = `Mostrando las ${directItems.length} películas y series más exitosas originarias de ${data.country_name} (ordenadas por Rating Bayesiano y Horas en Netflix)`;
      if (directHeading) directHeading.textContent = `Top Producciones de ${data.country_name}`;
    } else {
      titleEl.textContent = `Resultados para "${query}"`;
      subEl.textContent = `Mostrando ${directItems.length} coincidencias canónicas y recomendaciones de géneros similares (${data.seed_genres || 'Afines'})`;
      if (directHeading) directHeading.textContent = `Coincidencias Principales`;
    }

    directItems.forEach(movie => {
      directGrid.appendChild(createMovieCard(movie));
    });

    if (similarItems.length > 0) {
      similarBlock.style.display = "block";
      similarHeading.textContent = data.is_country_search
        ? `Recomendaciones Transfronterizas Afines a ${data.country_name}`
        : `Películas y Géneros Similares a "${data.seed_title || query}"`;
      similarSub.textContent = `Títulos seleccionados por similitud temática (${data.seed_genres || 'General'}), atmósfera y grafo de actores`;
      similarItems.forEach(movie => {
        similarGrid.appendChild(createMovieCard(movie));
      });
    } else {
      similarBlock.style.display = "none";
    }
  } catch (err) {
    console.error("[Search] Error:", err);
  }
}

function clearSearchAndGoHome() {
  STATE.isSearching = false;
  const searchInput = document.getElementById("search-input");
  const clearBtn = document.getElementById("btn-clear-search");
  const countrySelect = document.getElementById("nav-country-select");
  if (searchInput) searchInput.value = "";
  if (clearBtn) clearBtn.style.display = "none";
  if (countrySelect) countrySelect.value = "";

  const homeCatalogView = document.getElementById("home-catalog-view");
  const searchResultsView = document.getElementById("search-results-view");
  if (searchResultsView) searchResultsView.style.display = "none";
  if (homeCatalogView) homeCatalogView.style.display = "block";

  switchSection("home");
}
