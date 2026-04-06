(() => {
  const PAGE_SIZE = 8;

  const workGrid = document.getElementById("workoutsworkGrid");
  const workMessage = document.getElementById("workoutsworkMessage");
  const workLoadMoreBtn = document.getElementById("workoutsLoadMore");
  const recGrid = document.getElementById("recordingsworkGrid");
  const recMessage = document.getElementById("recordingsworkMessage");
  const recLoadMoreBtn = document.getElementById("recordingsLoadMore");
  const userId = document.body?.dataset?.userId;

  if (!workGrid || !workMessage || !recGrid || !recMessage) return;

  if (!userId) {
    workMessage.textContent = "No user ID found.";
    workMessage.classList.add("recordings-workMessage--error");
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
  let recordings = [];
  let workNextCursor = null;
  let recNextCursor = null;
  let workLoading = false;
  let recLoading = false;

  const setworkMessage = (text, tone) => {
    workMessage.textContent = text;
    workMessage.classList.remove("recordings-workMessage--error", "recordings-workMessage--success");
    if (tone === "error") workMessage.classList.add("recordings-workMessage--error");
    if (tone === "success") workMessage.classList.add("recordings-workMessage--success");
  };

  const setrecMessage = (text, tone) => {
    recMessage.textContent = text;
    recMessage.classList.remove("recordings-recMessage--error", "recordings-recMessage--success");
    if (tone === "error") recMessage.classList.add("recordings-recMessage--error");
    if (tone === "success") recMessage.classList.add("recordings-recMessage--success");
  };

  const setWorkLoadMoreState = (cursor, isLoading = false) => {
    workNextCursor = cursor || null;
    if (!workLoadMoreBtn) return;
    workLoadMoreBtn.classList.toggle("recordings-load-more--hidden", !workNextCursor);
    workLoadMoreBtn.disabled = isLoading;
    workLoadMoreBtn.textContent = isLoading ? "Loading..." : "Load more summaries";
  };

  const setRecLoadMoreState = (cursor, isLoading = false) => {
    recNextCursor = cursor || null;
    if (!recLoadMoreBtn) return;
    recLoadMoreBtn.classList.toggle("recordings-load-more--hidden", !recNextCursor);
    recLoadMoreBtn.disabled = isLoading;
    recLoadMoreBtn.textContent = isLoading ? "Loading..." : "Load more clips";
  };

  const formatDuration = (seconds) => {
    if (!seconds && seconds !== 0) return "Unknown duration";
    const total = Math.max(0, Math.round(seconds));
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return mins ? `${mins}m ${secs}s` : `${secs}s`;
  };

  const workRenderEmpty = () => {
    workGrid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No workouts yet. Start a session to see it here.";
    workGrid.appendChild(empty);
  };

  const recRenderEmpty = () => {
    recGrid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No recordings yet.";
    recGrid.appendChild(empty);
  };

  const renderWorkouts = () => {
    workGrid.innerHTML = "";
    if (!workouts.length) {
      workRenderEmpty();
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
      const metrics = getWorkoutMetrics(workout);

      const score = document.createElement("p");
      score.className = "workout-card__score";
      if (metrics.score == null) {
        score.classList.add("workout-card__score--missing");
        score.textContent = "Consistency score unavailable";
      } else {
        score.classList.add("workout-card__score--ok");
        score.textContent = `${Math.round(metrics.score)}% consistency`;
      }

      summary.textContent = metrics.score == null
        ? "Consistency score could not be calculated because not enough strokes were taken."
        : metrics.summary;

      const metricList = document.createElement("div");
      metricList.className = "workout-card__metrics";
      metricList.appendChild(buildMetricRow(
        "Stroke count",
        metrics.strokeCount == null ? "Not detected" : String(metrics.strokeCount),
      ));
      metricList.appendChild(buildMetricRow(
        "Cadence",
        metrics.cadenceSpm == null ? "Not available" : `${metrics.cadenceSpm.toFixed(1)} spm`,
      ));
      metricList.appendChild(buildMetricRow(
        "Range of motion",
        metrics.rangeOfMotion == null ? "Not available" : metrics.rangeOfMotion.toFixed(3),
      ));

      if (metrics.dominantSide) {
        metricList.appendChild(buildMetricRow("Dominant side", metrics.dominantSide, true));
      }
      if (metrics.signalStrategy) {
        metricList.appendChild(buildMetricRow(
          "Signal",
          metrics.signalStrategy.replaceAll("_", " "),
          true,
        ));
      }

      card.appendChild(header);
      card.appendChild(score);
      workGrid.appendChild(card);
    });
  };

  const loadWorkouts = async ({ append = false } = {}) => {
    if (append && (!workNextCursor || workLoading)) return;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && workNextCursor) {
      params.set("cursor", workNextCursor);
    }

    workLoading = true;
    setWorkLoadMoreState(workNextCursor, true);
    if (!append) {
      setworkMessage("Loading workouts...");
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
      setWorkLoadMoreState(payload.workNextCursor, false);
      setworkMessage("");
    } catch (err) {
      if (!append) {
        workouts = [];
        workRenderEmpty();
      }
      setworkMessage(err.workMessage || "Unable to load workouts", "error");
      setWorkLoadMoreState(payload.workNextCursor, false);
    } finally {
      workLoading = false;
      if (workLoadMoreBtn) {
        workLoadMoreBtn.disabled = false;
      }
    }
  };

  if (workLoadMoreBtn) {
    workLoadMoreBtn.addEventListener("click", async () => {
      await loadWorkouts({ append: true });
    });
  }

  const renderRecordings = () => {
    recGrid.innerHTML = "";
    console.log(recordings.length);
    if (!recordings.length) {
      recRenderEmpty();
      return;
    }

    recordings.forEach((recording) => {
      const card = document.createElement("article");
      card.className = "recording-card";

      const video = document.createElement("video");
      video.controls = true;
      video.preload = "metadata";
      if (recording.playbackUrl) {
        video.src = recording.playbackUrl;
      }

      const meta = document.createElement("div");
      meta.className = "recording-card__meta";
      const createdAt = recording.createdAt
        ? new Date(recording.createdAt).toLocaleString()
        : "Unknown date";
      meta.textContent = createdAt;

      card.appendChild(video);
      card.appendChild(meta);
      recGrid.appendChild(card);
    });
  };

  const loadRecordings = async ({ append = false } = {}) => {
    if (append && (!recNextCursor || recLoading)) return;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && recNextCursor) {
      params.set("cursor", recNextCursor);
    }

    recLoading = true;
    setRecLoadMoreState(recNextCursor, true);
    if (!append) {
      setrecMessage("Loading recordings...");
    }

    try {
      console.log("Fetching recordings with params:", params.toString());
      const response = await fetch(
        getApiUrl(`/api/recordings/${encodeURIComponent(userId)}?${params.toString()}`),
      );
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load recordings");
      }

      recordings = append
        ? recordings.concat(payload.recordings || [])
        : (payload.recordings || []);
      renderRecordings();
      setRecLoadMoreState(payload.recNextCursor, false);
      setrecMessage("");
    } catch (err) {
      if (!append) {
        recordings = [];
        recRenderEmpty();
      }
      setrecMessage(err.recMessage || "Unable to load recordings", "error");
      setRecLoadMoreState(payload.recNextCursor, false);
    } finally {
      recLoading = false;
      if (recLoadMoreBtn) {
        recLoadMoreBtn.disabled = false;
      }
    }
  };

  if (recLoadMoreBtn) {
    recLoadMoreBtn.addEventListener("click", async () => {
      await loadRecordings({ append: true });
    });
  }

  loadWorkouts();
  loadRecordings();
})();
