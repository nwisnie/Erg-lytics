(() => {
  const grid = document.getElementById("recordingsGrid");
  if (!grid) return;

  const message = document.getElementById("recordingsMessage");
  const userId = document.body?.dataset?.userId;
  if (!userId) {
    if (message) {
      message.textContent = "No user ID available to load recordings.";
      message.classList.add("recordings-message--error");
    }
    return;
  }

  const setMessage = (text, tone) => {
    if (!message) return;
    message.textContent = text;
    message.classList.remove("recordings-message--error", "recordings-message--success");
    if (tone === "error") message.classList.add("recordings-message--error");
    if (tone === "success") message.classList.add("recordings-message--success");
  };

  const renderEmpty = () => {
    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No recordings yet.";
    grid.appendChild(empty);
  };

  const renderRecordings = (recordings) => {
    grid.innerHTML = "";
    if (!recordings || recordings.length === 0) {
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

  const loadRecordings = async () => {
    setMessage("Loading recordings...", "info");
    try {
      const response = await fetch(`/api/recordings/${encodeURIComponent(userId)}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load recordings");
      }
      renderRecordings(payload.recordings || []);
      setMessage("", "success");
    } catch (err) {
      renderEmpty();
      setMessage(err.message || "Unable to load recordings", "error");
    }
  };

  loadRecordings();
})();
