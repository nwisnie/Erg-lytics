(() => {
  const PAGE_SIZE = 20;

  const getApiUrl = (path) => path;

  const joinSection = document.getElementById("teamJoinSection");
  const activeSection = document.getElementById("teamActiveSection");
  const joinForm = document.getElementById("teamJoinForm");
  const joinInput = document.getElementById("teamJoinId");
  const createForm = document.getElementById("teamCreateForm");
  const createInput = document.getElementById("teamCreateName");
  const teamStatus = document.getElementById("teamStatus");
  const teamIdDisplay = document.getElementById("teamIdDisplay");
  const teamStatsGrid = document.getElementById("teamStatsGrid");
  const teamStatsMessage = document.getElementById("teamStatsMessage");
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
  let currentTeamName = null;
  let currentTeamStats = null;
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

  const formatPercent = (value) => {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? `${Math.round(numeric)}%` : "Not available";
  };

  const buildStatCard = (label, value, detail) => {
    const card = document.createElement("article");
    card.className = "team-stat-card";

    const valueEl = document.createElement("p");
    valueEl.className = "team-stat-card__value";
    valueEl.textContent = value;

    const labelEl = document.createElement("p");
    labelEl.className = "team-stat-card__label";
    labelEl.textContent = label;

    const detailEl = document.createElement("p");
    detailEl.className = "team-stat-card__detail";
    detailEl.textContent = detail;

    card.append(valueEl, labelEl, detailEl);
    return card;
  };

  const renderTeamStats = (stats) => {
    if (!teamStatsGrid) return;

    teamStatsGrid.innerHTML = "";
    if (teamStatsMessage) {
      teamStatsMessage.textContent = "";
    }

    if (!stats) {
      teamStatsGrid.appendChild(buildStatCard("Workouts", "0", "No team workout data yet"));
      return;
    }

    const metricCards = [
      ["Average consistency", stats.metrics?.consistencyScore],
      ["Average arms straight", stats.metrics?.armsStraightScore],
      ["Average back straight", stats.metrics?.backStraightScore],
    ];

    teamStatsGrid.appendChild(
      buildStatCard(
        "Members",
        String(stats.memberCount ?? members.length),
        `${stats.workoutCount ?? 0} team workouts`,
      ),
    );

    metricCards.forEach(([label, metric]) => {
      const count = metric?.count || 0;
      teamStatsGrid.appendChild(
        buildStatCard(
          label,
          formatPercent(metric?.average),
          count ? `${count} workouts included` : "No available scores",
        ),
      );
    });

    if (teamStatsMessage && stats.unavailableReason) {
      teamStatsMessage.textContent = stats.unavailableReason;
    }
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
    currentTeamName = null;
    currentTeamStats = null;
    members = [];
    renderMembers();
    renderTeamStats(null);
    setLoadMoreState(null);
  };

  const showActive = (teamId, teamName, incomingMembers, nextCursor, append, teamStats) => {
    joinSection.classList.add("team-panel__section--hidden");
    activeSection.classList.remove("team-panel__section--hidden");
    teamStatus.textContent = "You're on a team.";
    teamIdDisplay.textContent = teamName ? `Team name: ${teamName}` : `Team ID: ${teamId}`;
    currentTeamId = teamId;
    currentTeamName = teamName || null;
    if (teamStats !== undefined) {
      currentTeamStats = teamStats;
    }
    members = append ? members.concat(incomingMembers) : incomingMembers;
    renderMembers();
    renderTeamStats(currentTeamStats);
    setLoadMoreState(nextCursor);
  };

  const loadCurrentTeam = async ({ append = false } = {}) => {
    if (append && (!nextMembersCursor || loadingMembers)) {
      return;
    }

    const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
    if (append && nextMembersCursor) {
      params.set("cursor", nextMembersCursor);
      params.set("includeStats", "false");
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

      showActive(
        data.teamId,
        data.teamName,
        data.members || [],
        data.nextCursor,
        append,
        data.teamStats,
      );
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
    const teamName = joinInput.value.trim();
    if (!teamName) {
      setMessage("Enter a team name to join.", "error");
      return;
    }

    setMessage("Joining team...", "info");
    try {
      const response = await fetch(getApiUrl("/api/team/join"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ teamName }),
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
        setMessage("Team created. Share the team name to invite members.", "success");
        await loadCurrentTeam();
      } catch (err) {
        setMessage(err.message || "Unable to create team", "error");
      }
    });
  }

  teamLeaveBtn.addEventListener("click", async () => {
    if (!currentTeamId) return;
    const leavingDeletesTeam = members.length === 1 && !nextMembersCursor;
    if (leavingDeletesTeam) {
      const confirmed = window.confirm(
        `You are the last member of ${currentTeamName || "this team"}. Leaving will delete the team. Continue?`,
      );
      if (!confirmed) {
        return;
      }
    }
    setMessage("Leaving team...", "info");
    try {
      const response = await fetch(getApiUrl("/api/team/leave"), { method: "DELETE" });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to leave team");
      }
      setMessage(data.deletedTeam ? "Left team. The empty team was deleted." : "Left team.", "success");
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

    const userLookup = memberUserId.value.trim();
    if (!userLookup) {
      setMessage("Enter a display name or user ID to add.", "error");
      return;
    }

    setMessage("Adding member...", "info");
    try {
      const response = await fetch(getApiUrl(`/api/teams/${encodeURIComponent(currentTeamId)}/members`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userLookup,
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
