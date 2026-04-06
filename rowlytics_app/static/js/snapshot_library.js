(() => {
  const PAGE_SIZE = 8;

  const recGrid = document.getElementById("recordingsrecGrid");
  const recMessage = document.getElementById("recordingsrecMessage");
  const recLoadMoreBtn = document.getElementById("recordingsLoadMore");
  const userId = document.body?.dataset?.userId;

  if (!recGrid || !recMessage) return;

  const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
  const getApiUrl = (path) => {
    if (apiBase) return apiBase + path;
    const parts = window.location.pathname.split("/").filter(Boolean);
    const first = parts[0];
    const stage = first && ["Prod", "Stage", "Dev"].includes(first) ? `/${first}` : "";
    return stage + path;
  };

  if (!userId) {
    recMessage.textContent = "No user ID available to load recordings.";
    recMessage.classList.add("recordings-recMessage--error");
    return;
  }

  let recordings = [];
  let nextCursor = null;
  let loading = false;

  const setrecMessage = (text, tone) => {
    recMessage.textContent = text;
    recMessage.classList.remove("recordings-recMessage--error", "recordings-recMessage--success");
    if (tone === "error") recMessage.classList.add("recordings-recMessage--error");
    if (tone === "success") recMessage.classList.add("recordings-recMessage--success");
  };

  const setLoadMoreState = (cursor, isLoading = false) => {
    nextCursor = cursor || null;
    if (!recLoadMoreBtn) return;
    recLoadMoreBtn.classList.toggle("recordings-load-more--hidden", !nextCursor);
    recLoadMoreBtn.disabled = isLoading;
    recLoadMoreBtn.textContent = isLoading ? "Loading..." : "Load more clips";
  };

  const renderEmpty = () => {
    recGrid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = "No recordings yet.";
    recGrid.appendChild(empty);
  };

  const renderRecordings = () => {
    recGrid.innerHTML = "";
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
      recGrid.appendChild(card);
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
      setrecMessage("Loading recordings...");
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
      setrecMessage("");
    } catch (err) {
      if (!append) {
        recordings = [];
        renderEmpty();
      }
      setrecMessage(err.recMessage || "Unable to load recordings", "error");
      setLoadMoreState(nextCursor, false);
    } finally {
      loading = false;
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

  loadRecordings();
})();
