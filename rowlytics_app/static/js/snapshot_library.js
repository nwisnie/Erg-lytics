(() => {
  const PAGE_SIZE = 8;

  const grid = document.getElementById("recordingsGrid");
  const message = document.getElementById("recordingsMessage");
  const loadMoreBtn = document.getElementById("recordingsLoadMore");
  const userId = document.body?.dataset?.userId;

  if (!grid || !message) return;

  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
  };

  if (!userId) {
    message.textContent = "No user ID available to load recordings.";
    message.classList.add("recordings-message--error");
    return;
  }

  let recordings = [];
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
    loadMoreBtn.textContent = isLoading ? "Loading..." : "Load more clips";
  };

  const renderEmpty = () => {
    grid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No recordings yet.";
    grid.appendChild(empty);
  };

  const renderRecordings = () => {
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

  loadRecordings();
})();
