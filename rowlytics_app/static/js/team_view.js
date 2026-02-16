(() => {
  const PAGE_SIZE = 20;

  const getApiUrl = (path) => {
    const currentPath = window.location.pathname;
    const match = currentPath.match(/^(\/[^/]+)?/);
    const stagePath = match ? match[0] : "";
    return stagePath + path;
  };

  const joinSection = document.getElementById("teamJoinSection");
  const activeSection = document.getElementById("teamActiveSection");
  const joinForm = document.getElementById("teamJoinForm");
  const joinInput = document.getElementById("teamJoinId");
  const createForm = document.getElementById("teamCreateForm");
  const createInput = document.getElementById("teamCreateName");
  const teamStatus = document.getElementById("teamStatus");
  const teamIdDisplay = document.getElementById("teamIdDisplay");
  const teamMembersList = document.getElementById("teamMembersList");
  const teamMembersLoadMore = document.getElementById("teamMembersLoadMore");
  const teamAddForm = document.getElementById("teamAddForm");
  const memberUserId = document.getElementById("memberUserId");
  const memberRole = document.getElementById("memberRole");
  const teamLeaveBtn = document.getElementById("teamLeaveBtn");
  const teamMessage = document.getElementById("teamMessage");

  if (!joinSection || !activeSection || !teamMembersList) {
    return;
  }

  let currentTeamId = null;
  let nextMembersCursor = null;
  let members = [];
  let loadingMembers = false;

  const setMessage = (text, tone) => {
    teamMessage.textContent = text;
    teamMessage.classList.remove("team-message--error", "team-message--success");
    if (tone === "error") teamMessage.classList.add("team-message--error");
    if (tone === "success") teamMessage.classList.add("team-message--success");
  };

  const setLoadMoreState = (cursor, loading = false) => {
    nextMembersCursor = cursor || null;
    if (!teamMembersLoadMore) return;
    teamMembersLoadMore.classList.toggle("team-load-more--hidden", !nextMembersCursor);
    teamMembersLoadMore.disabled = loading;
    teamMembersLoadMore.textContent = loading ? "Loading..." : "Load more members";
  };

  const renderMembers = () => {
    teamMembersList.innerHTML = "";
    if (!members.length) {
      const empty = document.createElement("li");
      empty.className = "team-members__empty";
      empty.textContent = "No members found.";
      teamMembersList.appendChild(empty);
      return;
    }

    members.forEach((member) => {
      const item = document.createElement("li");
      item.className = "team-members__item";

      const title = document.createElement("div");
      title.className = "team-members__title";
      title.textContent = member.name || member.userId || "Unknown user";

      const meta = document.createElement("div");
      meta.className = "team-members__meta";
      const metaParts = [member.email, member.memberRole].filter(Boolean);
      meta.textContent = metaParts.join(" · ");

      item.appendChild(title);
      item.appendChild(meta);
      teamMembersList.appendChild(item);
    });
  };

  const showJoin = () => {
    joinSection.classList.remove("team-panel__section--hidden");
    activeSection.classList.add("team-panel__section--hidden");
    teamStatus.textContent = "You're not on a team yet.";
    currentTeamId = null;
    members = [];
    renderMembers();
    setLoadMoreState(null);
  };

  const showActive = (teamId, incomingMembers, nextCursor, append) => {
    joinSection.classList.add("team-panel__section--hidden");
    activeSection.classList.remove("team-panel__section--hidden");
    teamStatus.textContent = "You're on a team.";
    teamIdDisplay.textContent = `Team ID: ${teamId}`;
    currentTeamId = teamId;
    members = append ? members.concat(incomingMembers) : incomingMembers;
    renderMembers();
    setLoadMoreState(nextCursor);
  };

  const loadCurrentTeam = async ({ append = false } = {}) => {
    if (append && (!nextMembersCursor || loadingMembers)) {
      return;
    }

    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && nextMembersCursor) {
      params.set("cursor", nextMembersCursor);
    }

    loadingMembers = true;
    setLoadMoreState(nextMembersCursor, true);
    if (!append) {
      setMessage("", "info");
    }

    try {
      const response = await fetch(getApiUrl(`/api/team/current?${params.toString()}`));
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to load team");
      }

      if (!data.teamId) {
        showJoin();
        return;
      }

      showActive(data.teamId, data.members || [], data.nextCursor, append);
    } catch (err) {
      if (!append) {
        showJoin();
      }
      setMessage(err.message || "Unable to load team", "error");
    } finally {
      loadingMembers = false;
      setLoadMoreState(nextMembersCursor, false);
    }
  };

  joinForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const teamId = joinInput.value.trim();
    if (!teamId) {
      setMessage("Enter a team ID to join.", "error");
      return;
    }

    setMessage("Joining team...", "info");
    try {
      const response = await fetch(getApiUrl("/api/team/join"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ teamId }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to join team");
      }
      joinInput.value = "";
      setMessage("Joined team.", "success");
      await loadCurrentTeam();
    } catch (err) {
      setMessage(err.message || "Unable to join team", "error");
    }
  });

  if (createForm && createInput) {
    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const teamName = createInput.value.trim();
      if (!teamName) {
        setMessage("Enter a team name to create.", "error");
        return;
      }

      setMessage("Creating team...", "info");
      try {
        const response = await fetch(getApiUrl("/api/team/create"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ teamName }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Unable to create team");
        }
        createInput.value = "";
        setMessage("Team created. Share the Team ID to invite members.", "success");
        await loadCurrentTeam();
      } catch (err) {
        setMessage(err.message || "Unable to create team", "error");
      }
    });
  }

  teamLeaveBtn.addEventListener("click", async () => {
    if (!currentTeamId) return;
    setMessage("Leaving team...", "info");
    try {
      const response = await fetch(getApiUrl("/api/team/leave"), { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to leave team");
      }
      setMessage("Left team.", "success");
      showJoin();
    } catch (err) {
      setMessage(err.message || "Unable to leave team", "error");
    }
  });

  teamAddForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentTeamId) {
      setMessage("Join a team first.", "error");
      return;
    }

    const userId = memberUserId.value.trim();
    if (!userId) {
      setMessage("Enter a user ID to add.", "error");
      return;
    }

    setMessage("Adding member...", "info");
    try {
      const response = await fetch(getApiUrl(`/api/teams/${encodeURIComponent(currentTeamId)}/members`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId,
          memberRole: memberRole.value,
          joinedAt: new Date().toISOString(),
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to add member");
      }

      memberUserId.value = "";
      setMessage("Member added.", "success");
      await loadCurrentTeam();
    } catch (err) {
      setMessage(err.message || "Unable to add member", "error");
    }
  });

  if (teamMembersLoadMore) {
    teamMembersLoadMore.addEventListener("click", async () => {
      await loadCurrentTeam({ append: true });
    });
  }

  loadCurrentTeam();
})();
