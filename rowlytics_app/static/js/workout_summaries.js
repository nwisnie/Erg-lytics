(() => {
  const PAGE_SIZE = 8;

  const grid = document.getElementById("workoutsGrid");
  const message = document.getElementById("workoutsMessage");
  const loadMoreBtn = document.getElementById("workoutsLoadMore");
  const userId = document.body?.dataset?.userId;

  if (!grid || !message) return;

  if (!userId) {
    message.textContent = "No user ID found.";
    message.classList.add("recordings-message--error");
    return;
  }

  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
  };

  let workouts = [];
  let nextCursor = null;
  let loading = false;

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("recordings-message--error", "recordings-message--success");
    if (tone === "error") message.classList.add("recordings-message--error");
    if (tone === "success") message.classList.add("recordings-message--success");
  };

  const setLoadMoreState = (cursor, isLoading = false) => {
    nextCursor = cursor || null;
    if (!loadMoreBtn) return;
    loadMoreBtn.classList.toggle("recordings-load-more--hidden", !nextCursor);
    loadMoreBtn.disabled = isLoading;
    loadMoreBtn.textContent = isLoading ? "Loading..." : "Load more summaries";
  };

  const formatDuration = (seconds) => {
    if (!seconds && seconds !== 0) return "Unknown duration";
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return mins ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const renderEmpty = () => {
    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No workouts yet. Start a session to see it here.";
    grid.appendChild(empty);
  };

  const renderWorkouts = () => {
    grid.innerHTML = "";
    if (!workouts.length) {
      renderEmpty();
      return;
    }

    workouts.forEach((workout) => {
      const card = document.createElement("article");
      card.className = "recording-card workout-card";

      const header = document.createElement("div");
      header.className = "workout-card__row";
      const title = document.createElement("h3");
      title.className = "workout-card__title";
      title.textContent = new Date(workout.completedAt || workout.createdAt || Date.now()).toLocaleString();
      const duration = document.createElement("span");
      duration.className = "workout-card__pill";
      duration.textContent = formatDuration(workout.durationSec);
      header.appendChild(title);
      header.appendChild(duration);

      const summary = document.createElement("p");
      summary.className = "workout-card__summary";
      summary.textContent = workout.summary || "No summary provided.";

      const score = document.createElement("p");
      score.className = "workout-card__meta";
      const scoreValue = workout.workoutScore;
      score.textContent = scoreValue === undefined || scoreValue === null
        ? "Score: not yet calculated"
        : `Score: ${scoreValue}`;

      card.appendChild(header);
      card.appendChild(summary);
      card.appendChild(score);
      grid.appendChild(card);
    });
  };

  const loadWorkouts = async ({ append = false } = {}) => {
    if (append && (!nextCursor || loading)) return;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && nextCursor) {
      params.set("cursor", nextCursor);
    }

    loading = true;
    setLoadMoreState(nextCursor, true);
    if (!append) {
      setMessage("Loading workouts...");
    }

    try {
      const response = await fetch(getApiUrl(`/api/workouts?${params.toString()}`));
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load workouts");
      }

      workouts = append
        ? workouts.concat(payload.workouts || [])
        : (payload.workouts || []);
      renderWorkouts();
      setLoadMoreState(payload.nextCursor, false);
      setMessage("");
    } catch (err) {
      if (!append) {
        workouts = [];
        renderEmpty();
      }
      setMessage(err.message || "Unable to load workouts", "error");
      setLoadMoreState(nextCursor, false);
    } finally {
      loading = false;
      if (loadMoreBtn) {
        loadMoreBtn.disabled = false;
      }
    }
  };

  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", async () => {
      await loadWorkouts({ append: true });
    });
  }

  loadWorkouts();
})();
