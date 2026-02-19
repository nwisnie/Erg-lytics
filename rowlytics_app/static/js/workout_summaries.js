(() => {
  const grid = document.getElementById("workoutsGrid");
  const message = document.getElementById("workoutsMessage");
  const userId = document.body?.dataset?.userId;

  if (!grid || !message) {
    console.warn("[workouts] Required elements missing");
    return;
  }

  if (!userId) {
    message.textContent = "No user ID found.";
    message.classList.add("recordings-message--error");
    return;
  }

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("recordings-message--error", "recordings-message--success");
    if (tone === "error") message.classList.add("recordings-message--error");
    if (tone === "success") message.classList.add("recordings-message--success");
  };

  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");

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

  const renderEmpty = () => {
    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No workouts yet. Start a session to see it here.";
    grid.appendChild(empty);
  };

  const renderWorkouts = (workouts) => {
    grid.innerHTML = "";
    if (!workouts || workouts.length === 0) {
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

  const loadWorkouts = async () => {
    const apiUrl = getApiUrl("/api/workouts");
    setMessage("Loading workouts...");
    try {
      const response = await fetch(apiUrl);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load workouts");
      }
      renderWorkouts(payload.workouts || []);
      setMessage("");
    } catch (err) {
      console.error("[workouts] Failed to load workouts", err);
      renderEmpty();
      setMessage(err.message || "Unable to load workouts", "error");
    }
  };

  loadWorkouts();
})();
