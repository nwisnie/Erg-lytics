(() => {
  const grid = document.getElementById("recordingsGrid");
  if (!grid) {
    console.warn("[recordings] Grid element not found");
    return;
  }

  // Helper function to build correct API URLs with stage prefix
  const getApiUrl = (path) => {
    const currentPath = window.location.pathname;
    const match = currentPath.match(/^(\/[^/]+)?/); // Match /Prod or similar stage
    const stagePath = match ? match[0] : '';
    return stagePath + path;
  };

  const message = document.getElementById("recordingsMessage");
  const userId = document.body?.dataset?.userId;
  console.log("[recordings] Page loaded. Grid found:", !!grid, "User ID:", userId);

  if (!userId) {
    console.error("[recordings] No user ID found in data-user-id attribute");
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
    const apiUrl = getApiUrl(`/api/recordings/${encodeURIComponent(userId)}`);
    console.log("[recordings] Starting to load recordings from:", apiUrl);
    setMessage("Loading recordings...", "info");
    try {
      console.log("[recordings] Fetching from API...");
      const response = await fetch(apiUrl);
      console.log("[recordings] Fetch response status:", response.status);
      const payload = await response.json();
      console.log("[recordings] API response payload:", payload);
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load recordings");
      }
      console.log("[recordings] Successfully loaded", payload.recordings?.length || 0, "recordings");
      renderRecordings(payload.recordings || []);
      setMessage("", "success");
    } catch (err) {
      console.error("[recordings] Error loading recordings:", err);
      renderEmpty();
      setMessage(err.message || "Unable to load recordings", "error");
    }
  };

  console.log("[recordings] Calling loadRecordings()");
  loadRecordings();
})();
