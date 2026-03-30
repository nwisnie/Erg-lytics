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

  const asNumber = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const parseAlignmentDetails = (details) => {
    const parsed = {};
    (details || "")
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .forEach((line) => {
        const separatorIndex = line.indexOf(":");
        if (separatorIndex < 0) return;
        const key = line.slice(0, separatorIndex).trim().toLowerCase();
        const value = line.slice(separatorIndex + 1).trim();
        parsed[key] = value;
      });
    return parsed;
  };

  const getWorkoutMetrics = (workout) => {
    const parsedDetails = parseAlignmentDetails(workout.alignmentDetails);
    return {
      score: asNumber(workout.workoutScore) ?? asNumber(parsedDetails.score),
      summary: workout.summary || parsedDetails.summary || "No summary provided.",
      strokeCount: asNumber(workout.strokeCount) ?? asNumber(parsedDetails["stroke count"]),
      cadenceSpm: asNumber(workout.cadenceSpm) ?? asNumber(parsedDetails["cadence (spm)"]),
      rangeOfMotion: asNumber(workout.rangeOfMotion) ?? asNumber(parsedDetails["range of motion"]),
      dominantSide: workout.dominantSide || parsedDetails["dominant side"] || "",
      signalStrategy: parsedDetails["signal strategy"] || "",
    };
  };

  const buildMetricRow = (labelText, valueText, subtle = false) => {
    const row = document.createElement("p");
    row.className = subtle ? "workout-card__metric workout-card__metric--subtle" : "workout-card__metric";

    const label = document.createElement("span");
    label.className = "workout-card__metric-label";
    label.textContent = `${labelText}:`;

    const value = document.createElement("span");
    value.className = "workout-card__metric-value";
    value.textContent = valueText;

    row.appendChild(label);
    row.appendChild(value);
    return row;
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
      const metrics = getWorkoutMetrics(workout);

      const score = document.createElement("p");
      score.className = "workout-card__score";
      if (metrics.score == null) {
        score.classList.add("workout-card__score--missing");
        score.textContent = "Score unavailable";
      } else {
        score.classList.add("workout-card__score--ok");
        score.textContent = `${Math.round(metrics.score)}% alignment`;
      }

      summary.textContent = metrics.score == null
        ? "Score could not be calculated because not enough strokes were taken."
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
      card.appendChild(summary);
      card.appendChild(metricList);
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
