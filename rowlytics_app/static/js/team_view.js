(() => {
  console.log("[team-view] Script initializing");

  // Helper function to build correct API URLs with stage prefix
  const getApiUrl = (path) => {
    const currentPath = window.location.pathname;
    const match = currentPath.match(/^(\/[^/]+)?/); // Match /Prod or similar stage
    const stagePath = match ? match[0] : '';
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
  const teamAddForm = document.getElementById("teamAddForm");
  const memberUserId = document.getElementById("memberUserId");
  const memberRole = document.getElementById("memberRole");
  const teamLeaveBtn = document.getElementById("teamLeaveBtn");
  const teamMessage = document.getElementById("teamMessage");

  if (!joinSection || !activeSection) {
    console.warn("[team-view] Required DOM elements not found. Join section:", !!joinSection, "Active section:", !!activeSection);
    return;
  }
  console.log("[team-view] All DOM elements found, setting up event listeners");

  let currentTeamId = null;

  const setMessage = (text, tone) => {
    teamMessage.textContent = text;
    teamMessage.classList.remove("team-message--error", "team-message--success");
    if (tone === "error") teamMessage.classList.add("team-message--error");
    if (tone === "success") teamMessage.classList.add("team-message--success");
  };

  const renderMembers = (members) => {
    teamMembersList.innerHTML = "";
    if (!members || members.length === 0) {
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
    renderMembers([]);
  };

  const showActive = (teamId, members) => {
    joinSection.classList.add("team-panel__section--hidden");
    activeSection.classList.remove("team-panel__section--hidden");
    teamStatus.textContent = "You're on a team.";
    currentTeamId = teamId;
    teamIdDisplay.textContent = `Team ID: ${teamId}`;
    renderMembers(members);
  };

  const loadCurrentTeam = async () => {
    console.log("[team-view] Loading current team data from /api/team/current");
    setMessage("", "info");
    try {
      const response = await fetch(getApiUrl("/api/team/current"));
      console.log("[team-view] API response status:", response.status);
      const data = await response.json();
      console.log("[team-view] API response data:", data);
      if (!response.ok) {
        throw new Error(data.error || "Unable to load team");
      }
      if (!data.teamId) {
        console.log("[team-view] No team ID in response, showing join section");
        showJoin();
        return;
      }
      console.log("[team-view] Team loaded:", data.teamId, "with", data.members?.length || 0, "members");
      showActive(data.teamId, data.members || []);
    } catch (err) {
      console.error("[team-view] Error loading team:", err);
      showJoin();
      setMessage(err.message || "Unable to load team", "error");
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
        body: JSON.stringify({ teamId })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to join team");
      }
      joinInput.value = "";
      setMessage("Joined team.", "success");
      showActive(data.teamId, data.members || []);
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
          body: JSON.stringify({ teamName })
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "Unable to create team");
        }
        createInput.value = "";
        setMessage("Team created. Share the Team ID to invite members.", "success");
        showActive(data.teamId, data.members || []);
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
          joinedAt: new Date().toISOString()
        })
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

  loadCurrentTeam();
  console.log("[team-view] Initial loadCurrentTeam() call made");
})();
