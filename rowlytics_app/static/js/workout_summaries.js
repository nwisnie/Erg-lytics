(() => {
  const PAGE_SIZE = 8;

  const grid = document.getElementById("workoutsGrid");
  const message = document.getElementById("workoutsMessage");
  const loadMoreBtn = document.getElementById("workoutsLoadMore");
  const dateFilterForm = document.getElementById("workoutsDateFilterForm");
  const dateFilterInput = document.getElementById("workoutsDateFilter");
  const clearFilterBtn = document.getElementById("workoutsClearFilter");
  const userId = document.body?.dataset?.userId;
  const workoutDetailBase = document.body?.dataset?.workoutDetailBase || "";

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
  let selectedDate = "";
  let loadRequestId = 0;

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

  const getLocalDayRange = (dateValue) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateValue || "")) return null;

    const [year, month, day] = dateValue.split("-").map(Number);
    const start = new Date(year, month - 1, day, 0, 0, 0, 0);
    const nextDay = new Date(year, month - 1, day + 1, 0, 0, 0, 0);
    if (Number.isNaN(start.getTime()) || Number.isNaN(nextDay.getTime())) return null;

    return {
      completedFrom: start.toISOString(),
      completedTo: new Date(nextDay.getTime() - 1).toISOString(),
    };
  };

  const formatSelectedDate = (dateValue) => {
    const [year, month, day] = dateValue.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    if (Number.isNaN(date.getTime())) return dateValue;
    return date.toLocaleDateString();
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
      score: asNumber(workout.workoutScore)
        ?? asNumber(parsedDetails["consistency score"])
        ?? asNumber(parsedDetails.score),
      armsStraightScore: asNumber(workout.armsStraightScore)
        ?? asNumber(parsedDetails["arms straight score"]),
      backStraightScore: asNumber(workout.backStraightScore)
        ?? asNumber(parsedDetails["back straight score"]),
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
    empty.textContent = selectedDate
      ? `No workouts found for ${formatSelectedDate(selectedDate)}.`
      : "No workouts yet. Start a session to see it here.";
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

      card.style.cursor = "pointer";

      card.addEventListener("click", () => {
        const detailUrl = workoutDetailBase.replace("__WORKOUT_ID__", workout.workoutId);
        window.location.href = detailUrl || `/workout-summaries/${workout.workoutId}`;
      });

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

      const armScore = buildMetricRow(
        "Arms straight",
        metrics.armsStraightScore == null ? "Not available" : `${Math.round(metrics.armsStraightScore)}%`,
        true,
      );

      const backScore = buildMetricRow(
        "Back straight",
        metrics.backStraightScore == null ? "Not available" : `${Math.round(metrics.backStraightScore)}%`,
        true,
      );

      const preview = document.createElement("p");
      preview.className = "workout-card__summary";
      preview.textContent = "Click to view full workout summary →";

      card.appendChild(header);
      card.appendChild(score);
      card.appendChild(armScore);
      card.appendChild(backScore);
      card.appendChild(preview);
      grid.appendChild(card);
    });
  };

  const loadWorkouts = async ({ append = false } = {}) => {
    if (append && (!nextCursor || loading)) return;
    const requestId = loadRequestId + 1;
    loadRequestId = requestId;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    const dateRange = getLocalDayRange(selectedDate);
    if (selectedDate && !dateRange) {
      workouts = [];
      renderEmpty();
      setLoadMoreState(null, false);
      setMessage("Choose a valid date.", "error");
      return;
    }
    if (dateRange) {
      params.set("completedFrom", dateRange.completedFrom);
      params.set("completedTo", dateRange.completedTo);
    }
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
      if (requestId !== loadRequestId) return;

      workouts = append
        ? workouts.concat(payload.workouts || [])
        : (payload.workouts || []);
      renderWorkouts();
      setLoadMoreState(payload.nextCursor, false);
      setMessage("");
    } catch (err) {
      if (requestId !== loadRequestId) return;
      if (!append) {
        workouts = [];
        renderEmpty();
      }
      setMessage(err.message || "Unable to load workouts", "error");
      setLoadMoreState(nextCursor, false);
    } finally {
      if (requestId === loadRequestId) {
        loading = false;
        if (loadMoreBtn) {
          loadMoreBtn.disabled = false;
        }
      }
    }
  };

  if (loadMoreBtn) {
    loadMoreBtn.addEventListener("click", async () => {
      await loadWorkouts({ append: true });
    });
  }

  if (dateFilterForm) {
    dateFilterForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      selectedDate = dateFilterInput?.value || "";
      await loadWorkouts();
    });
  }

  if (dateFilterInput) {
    dateFilterInput.addEventListener("change", async () => {
      selectedDate = dateFilterInput.value || "";
      await loadWorkouts();
    });
  }

  if (clearFilterBtn) {
    clearFilterBtn.addEventListener("click", async () => {
      if (dateFilterInput) {
        dateFilterInput.value = "";
      }
      selectedDate = "";
      await loadWorkouts();
    });
  }

  loadWorkouts();
})();
