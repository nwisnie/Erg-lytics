(() => {
  const teamLookupForm = document.getElementById("teamLookupForm");
  if (!teamLookupForm) return;

  const teamIdInput = document.getElementById("teamIdInput");
  const teamMembersList = document.getElementById("teamMembersList");
  const teamAddForm = document.getElementById("teamAddForm");
  const memberUserId = document.getElementById("memberUserId");
  const memberRole = document.getElementById("memberRole");
  const memberStatus = document.getElementById("memberStatus");
  const teamMessage = document.getElementById("teamMessage");

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
      const metaParts = [
        member.email,
        member.memberRole,
        member.status,
      ].filter(Boolean);
      meta.textContent = metaParts.join(" · ");

      item.appendChild(title);
      item.appendChild(meta);
      teamMembersList.appendChild(item);
    });
  };

  const loadMembers = async (teamId) => {
    setMessage("Loading members...", "info");
    try {
      const response = await fetch(`/api/teams/${encodeURIComponent(teamId)}/members`);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to load members");
      }
      renderMembers(data.members);
      setMessage(`Loaded ${data.members.length} member(s).`, "success");
    } catch (error) {
      renderMembers([]);
      setMessage(error.message || "Unable to load members", "error");
    }
  };

  teamLookupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const teamId = teamIdInput.value.trim();
    if (!teamId) {
      setMessage("Enter a team ID first.", "error");
      return;
    }
    await loadMembers(teamId);
  });

  teamAddForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const teamId = teamIdInput.value.trim();
    const userId = memberUserId.value.trim();

    if (!teamId) {
      setMessage("Enter a team ID first.", "error");
      return;
    }
    if (!userId) {
      setMessage("Enter a user ID to add.", "error");
      return;
    }

    setMessage("Adding member...", "info");
    try {
      const response = await fetch(`/api/teams/${encodeURIComponent(teamId)}/members`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          userId,
          memberRole: memberRole.value,
          status: memberStatus.value,
          joinedAt: new Date().toISOString()
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unable to add member");
      }

      memberUserId.value = "";
      setMessage("Member added.", "success");
      await loadMembers(teamId);
    } catch (error) {
      setMessage(error.message || "Unable to add member", "error");
    }
  });
})();
