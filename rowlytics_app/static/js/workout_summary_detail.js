(() => {
  const container = document.getElementById("workoutDetail");
  const message = document.getElementById("workoutDetailMessage");
  const workoutId = document.body?.dataset?.workoutId;
  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");

  if (!container || !message || !workoutId) {
    return;
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

  const loadWorkout = async () => {
    message.textContent = "Loading workout...";
    try {
      const response = await fetch(getApiUrl(`/api/workouts/${workoutId}`));
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Unable to load workout");
      }

      const workout = payload.workout;
      const completedAt = new Date(workout.completedAt || workout.createdAt || Date.now()).toLocaleString();

      container.innerHTML = `
        <article class="recording-card workout-card">
          <div class="workout-card__row">
            <h1 class="workout-card__title">${completedAt}</h1>
            <span class="workout-card__pill">${formatDuration(workout.durationSec)}</span>
          </div>
          <p class="workout-card__score">
            ${workout.workoutScore != null ? `${Math.round(Number(workout.workoutScore))}% alignment` : "Score unavailable"}
          </p>
          <p class="workout-card__summary">${workout.summary || "No summary provided."}</p>
          <div class="workout-card__metrics">
            <p class="workout-card__metric"><span class="workout-card__metric-label">Stroke count:</span> <span class="workout-card__metric-value">${workout.strokeCount ?? "Not detected"}</span></p>
            <p class="workout-card__metric"><span class="workout-card__metric-label">Cadence:</span> <span class="workout-card__metric-value">${workout.cadenceSpm ?? "Not available"}</span></p>
            <p class="workout-card__metric"><span class="workout-card__metric-label">Range of motion:</span> <span class="workout-card__metric-value">${workout.rangeOfMotion ?? "Not available"}</span></p>
            <p class="workout-card__metric workout-card__metric--subtle"><span class="workout-card__metric-label">Dominant side:</span> <span class="workout-card__metric-value">${workout.dominantSide || "Not available"}</span></p>
          </div>
          <pre class="workout-card__details">${workout.alignmentDetails || ""}</pre>
        </article>
      `;

      message.textContent = "";
    } catch (err) {
      message.textContent = err.message || "Unable to load workout";
      message.classList.add("recordings-message--error");
    }
  };

  loadWorkout();
})();
