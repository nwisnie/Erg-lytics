(() => {
  const PAGE_SIZE = 8;

  const grid = document.getElementById("recordingsGrid");
  const message = document.getElementById("recordingsMessage");
  const loadMoreBtn = document.getElementById("recordingsLoadMore");
  const dateFilterForm = document.getElementById("recordingsDateFilterForm");
  const dateFilterInput = document.getElementById("recordingsDateFilter");
  const clearFilterBtn = document.getElementById("recordingsClearFilter");
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
  let selectedDate = "";
  let loadRequestId = 0;

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

  const getLocalDayRange = (dateValue) => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dateValue || "")) return null;

    const [year, month, day] = dateValue.split("-").map(Number);
    const start = new Date(year, month - 1, day, 0, 0, 0, 0);
    const nextDay = new Date(year, month - 1, day + 1, 0, 0, 0, 0);
    if (Number.isNaN(start.getTime()) || Number.isNaN(nextDay.getTime())) return null;

    return {
      createdFrom: start.toISOString(),
      createdTo: new Date(nextDay.getTime() - 1).toISOString(),
    };
  };

  const formatSelectedDate = (dateValue) => {
    const [year, month, day] = dateValue.split("-").map(Number);
    const date = new Date(year, month - 1, day);
    if (Number.isNaN(date.getTime())) return dateValue;
    return date.toLocaleDateString();
  };

  const renderEmpty = () => {
    recGrid.innerHTML = "";
    const empty = document.createElement("div");
    empty.className = "recordings-empty";
    empty.textContent = selectedDate
      ? `No recordings found for ${formatSelectedDate(selectedDate)}.`
      : "No recordings yet.";
    grid.appendChild(empty);
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
    const requestId = loadRequestId + 1;
    loadRequestId = requestId;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    const dateRange = getLocalDayRange(selectedDate);
    if (selectedDate && !dateRange) {
      recordings = [];
      renderEmpty();
      setLoadMoreState(null, false);
      setMessage("Choose a valid date.", "error");
      return;
    }
    if (dateRange) {
      params.set("createdFrom", dateRange.createdFrom);
      params.set("createdTo", dateRange.createdTo);
    }
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
      if (requestId !== loadRequestId) return;

      recordings = append
        ? recordings.concat(payload.recordings || [])
        : (payload.recordings || []);
      renderRecordings();
      setLoadMoreState(payload.nextCursor, false);
      setrecMessage("");
    } catch (err) {
      if (requestId !== loadRequestId) return;
      if (!append) {
        recordings = [];
        renderEmpty();
      }
      setrecMessage(err.recMessage || "Unable to load recordings", "error");
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

  if (recLoadMoreBtn) {
    recLoadMoreBtn.addEventListener("click", async () => {
      await loadRecordings({ append: true });
    });
  }

  if (dateFilterForm) {
    dateFilterForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      selectedDate = dateFilterInput?.value || "";
      await loadRecordings();
    });
  }

  if (dateFilterInput) {
    dateFilterInput.addEventListener("change", async () => {
      selectedDate = dateFilterInput.value || "";
      await loadRecordings();
    });
  }

  if (clearFilterBtn) {
    clearFilterBtn.addEventListener("click", async () => {
      if (dateFilterInput) {
        dateFilterInput.value = "";
      }
      selectedDate = "";
      await loadRecordings();
    });
  }

  loadRecordings();
})();
