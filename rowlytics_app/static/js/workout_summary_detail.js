(() => {
  const PAGE_SIZE = 8;

  const container = document.getElementById("workoutDetail");
  const message = document.getElementById("workoutDetailMessage");
  const workoutId = document.body?.dataset?.workoutId;
  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
  const userId = document.body?.dataset?.userId;
  const loadMoreBtn = document.getElementById("recordingsLoadMoreBtn");
  const capturedFromWorkout = (() => {
    try {
      const params = new URLSearchParams(window.location.search || "");
      return params.get("captured") === "1";
    } catch (err) {
      return false;
    }
  })();

  if (!container || !message || !workoutId || !userId) {
    return;
  }

  let recordings = [];
  let nextCursor = null;
  let loading = false;

  const getGrid = () => document.getElementById("recordingsGrid");

  const setLoadMoreState = (cursor, isLoading = false) => {
    nextCursor = cursor || null;
    if (!loadMoreBtn) return;
    loadMoreBtn.classList.toggle("recordings-load-more--hidden", !nextCursor);
    loadMoreBtn.disabled = isLoading;
    loadMoreBtn.textContent = isLoading ? "Loading..." : "Load more clips";
  };

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("recordings-message--error", "recordings-message--success");
    if (tone === "error") message.classList.add("recordings-message--error");
    if (tone === "success") message.classList.add("recordings-message--success");
  };

  const renderEmpty = () => {
    const grid = getGrid();
    if (!grid) return;

    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "Snapshot clips will appear here.";
    grid.appendChild(empty);
  };

  const renderRecordings = () => {
    const grid = getGrid();
    if (!grid) return;
    grid.innerHTML = "";
    if (!recordings.length) {
      renderEmpty();
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
      grid.appendChild(card);
    });
  };

  const loadRecordings = async ({ append = false } = {}) => {
    if (append && (!nextCursor || loading)) return;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && nextCursor) {
      params.set("cursor", nextCursor);
    }
    if (workoutId) {
      params.set("workoutId", workoutId);
    }

    loading = true;
    setLoadMoreState(nextCursor, true);
    if (!append) {
      setMessage("Loading recordings...");
    }

    try {
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
      setLoadMoreState(payload.nextCursor, false);
      setMessage("");
    } catch (err) {
      if (!append) {
        recordings = [];
        renderEmpty();
      }
      setMessage(err.message || "Unable to load recordings", "error");
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
      await loadRecordings({ append: true });
    });
  }


  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
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

  const formatDecimal = (value, digits = 1) => {
    const num = asNumber(value);
    return num == null ? "Not available" : num.toFixed(digits);
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

  const buildMetricRow = (label, value, subtle = false) => {
    return `
      <p class="workout-card__metric${subtle ? " workout-card__metric--subtle" : ""}">
        <span class="workout-card__metric-label">${label}:</span>
        <span class="workout-card__metric-value">${value}</span>
      </p>
    `;
  };

  const loadWorkout = async () => {
    setMessage("Loading workout...");

    try {
      const response = await fetch(getApiUrl(`/api/workouts/${workoutId}`));
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Unable to load workout");
      }

      const workout = payload.workout;
      const details = parseAlignmentDetails(workout.alignmentDetails);

      const completedAt = new Date(
        workout.completedAt || workout.createdAt || Date.now(),
      ).toLocaleString();

      const score =
        asNumber(workout.workoutScore) ??
        asNumber(details["consistency score"]) ??
        null;

      const summary =
        workout.summary ||
        details.summary ||
        "No summary provided.";

      const strokeCount =
        workout.strokeCount ??
        details["stroke count"] ??
        "Not detected";

      const cadence =
        workout.cadenceSpm != null
          ? `${formatDecimal(workout.cadenceSpm, 1)} spm`
          : details["cadence (spm)"] != null
            ? `${formatDecimal(details["cadence (spm)"], 1)} spm`
            : "Not available";

      const rangeOfMotion =
        workout.rangeOfMotion != null
          ? formatDecimal(workout.rangeOfMotion, 3)
          : details["range of motion"] != null
            ? formatDecimal(details["range of motion"], 3)
            : "Not available";

      const dominantSide =
        workout.dominantSide ||
        details["dominant side"] ||
        "Not available";

      const signalUsed =
        details["signal strategy"]
          ? details["signal strategy"].replaceAll("_", " ")
          : "Not available";

      const movementGate =
        details["movement gate"] || "Not available";

      const movementReason =
        details["movement reason"] || "Not available";

      const clipsObserved =
        details["clips observed"] || "Not available";

      container.innerHTML = `
        <div class="stack">
          <article class="recording-card workout-card">
            <div class="workout-card__row">
              <h1 class="workout-card__title">${completedAt}</h1>
              <span class="workout-card__pill">${formatDuration(workout.durationSec)}</span>
            </div>

            <p class="workout-card__score ${
              score == null ? "workout-card__score--missing" : "workout-card__score--ok"
            }">
              ${score != null ? `${Math.round(score)}% consistency` : "Score unavailable"}
            </p>

            <p class="workout-card__summary">${summary}</p>

            <div class="workout-card__metrics">
              ${buildMetricRow("Stroke count", strokeCount)}
              ${buildMetricRow("Cadence", cadence)}
              ${buildMetricRow("Range of motion", rangeOfMotion)}
              ${buildMetricRow("Dominant side", dominantSide, true)}
            </div>

            <div class="workout-card__metrics" style="margin-top: 1rem;">
              ${buildMetricRow("Movement check", movementGate, true)}
              ${buildMetricRow("Reason", movementReason, true)}
              ${buildMetricRow("Signal used", signalUsed, true)}
              ${buildMetricRow("Clips observed", clipsObserved, true)}
            </div>
          </article>

          <section class="recording-card workout-card">
            <div class="recordings-panel__header">
              <h2>Snapshot Clips From This Workout</h2>
              <p>Review the short clips captured during this workout session.</p>
            </div>

            <div id="recordingsGrid" class="recordings-grid"></div>
            </div>
          </section>
        </div>
      `;

       message.classList.remove(
    "recordings-message--error",
    "recordings-message--success"
       );

      if (capturedFromWorkout) {
      setMessage("Workout successfully captured.", "success");
    } else {
      setMessage("");
    }

    try {
      await loadRecordings();
    } catch (err) {
        setMessage(err.message || "Unable to load workout", "error");
      }
  } catch (err) {
    setMessage(err.message || "An error occurred", "error");
  }
};

  loadWorkout();
})();
