(() => {
  const rangeText = document.getElementById("teamStatsRange");
  const message = document.getElementById("teamStatsMessage");
  const userStatsTitle = document.getElementById("userStatsTitle");
  const userWorkoutCount = document.getElementById("userWorkoutCount");
  const userConsistencyScore = document.getElementById("userConsistencyScore");
  const userArmsScore = document.getElementById("userArmsScore");
  const userBackScore = document.getElementById("userBackScore");
  const teamStatsTitle = document.getElementById("teamStatsTitle");
  const teamWorkoutCount = document.getElementById("teamWorkoutCount");
  const teamConsistencyScore = document.getElementById("teamConsistencyScore");
  const teamArmsScore = document.getElementById("teamArmsScore");
  const teamBackScore = document.getElementById("teamBackScore");
  const teamMemberCount = document.getElementById("teamMemberCount");
  const userChartHint = document.getElementById("userChartHint");
  const teamChartHint = document.getElementById("teamChartHint");
  const userScatterChart = document.getElementById("userScatterChart");
  const teamScatterChart = document.getElementById("teamScatterChart");

  if (
    !rangeText ||
    !message ||
    !userStatsTitle ||
    !userConsistencyScore ||
    !userArmsScore ||
    !userBackScore ||
    !teamStatsTitle ||
    !teamConsistencyScore ||
    !teamArmsScore ||
    !teamBackScore ||
    !userScatterChart ||
    !teamScatterChart
  ) {
    return;
  }

  const getApiUrl = (path) => path;

  const setMessage = (text, tone) => {
    message.textContent = text;
    message.classList.remove("team-stats__message--error", "team-stats__message--success");
    if (tone === "error") {
      message.classList.add("team-stats__message--error");
    }
    if (tone === "success") {
      message.classList.add("team-stats__message--success");
    }
  };

  const formatDateRange = (windowStart, windowEnd) => {
    const formatter = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    });
    return `${formatter.format(windowStart)} to ${formatter.format(windowEnd)}`;
  };

  const formatScore = (value) => (typeof value === "number" ? `${value.toFixed(1)}%` : "--");

  const formatCount = (value) => {
    const count = Number(value);
    return Number.isFinite(count) ? String(count) : "0";
  };

  const renderSummary = (summary, elements, fallbackMeta) => {
    elements.title.textContent = summary.title || "Untitled";
    elements.workoutCount.textContent = formatCount(summary.workoutCount);
    elements.consistencyScore.textContent = formatScore(summary.averageConsistencyScore);
    elements.armsScore.textContent = formatScore(summary.averageArmsScore);
    elements.backScore.textContent = formatScore(summary.averageBackScore);

    if (!elements.meta) {
      return;
    }

    if (typeof summary.memberCount === "number" && summary.memberCount > 0) {
      elements.meta.textContent = `${summary.memberCount} team member${summary.memberCount === 1 ? "" : "s"}`;
      return;
    }

    elements.meta.textContent = fallbackMeta || "";
  };

  const escapeHtml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  const describeMetric = (label, value) => `${label}: ${typeof value === "number" ? `${value.toFixed(1)}%` : "n/a"}`;

  const renderScatter = (container, points, options) => {
    const {
      emptyText,
      windowStart,
      windowEnd,
      accentClass,
      chartTitle,
    } = options;

    if (!Array.isArray(points) || !points.length) {
      container.innerHTML = `<div class="team-chart-card__empty">${escapeHtml(emptyText)}</div>`;
      return;
    }

    const isMobile = window.matchMedia("(max-width: 720px)").matches;
    const width = isMobile ? 680 : 760;
    const height = isMobile ? 455 : 410;
    const margin = isMobile
      ? { top: 8, right: 18, bottom: 114, left: 76 }
      : { top: 8, right: 22, bottom: 102, left: 84 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const startMs = windowStart.getTime();
    const endMs = windowEnd.getTime();
    const spanMs = Math.max(endMs - startMs, 1);
    const yTicks = [0, 25, 50, 75, 100];
    const tickCount = isMobile ? 4 : 7;
    const axisFontSize = isMobile ? 24 : 20;
    const axisTitleFontSize = isMobile ? 26 : 22;

    const xFormatter = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    });
    const tooltipFormatter = new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });

    const xFor = (timestampMs) =>
      margin.left + ((timestampMs - startMs) / spanMs) * plotWidth;
    const yFor = (score) =>
      margin.top + plotHeight - (Math.max(0, Math.min(100, score)) / 100) * plotHeight;

    const xTicks = [];
    const tickStep = spanMs / Math.max(tickCount - 1, 1);
    for (let index = 0; index < tickCount; index += 1) {
      const tickMs = Math.min(startMs + index * tickStep, endMs);
      xTicks.push({
        label: xFormatter.format(new Date(tickMs)),
        x: xFor(tickMs),
      });
    }

    const gridLines = yTicks
      .map((tick) => {
        const y = yFor(tick);
        return `
          <line class="team-chart__grid" x1="${margin.left}" y1="${y}" x2="${width - margin.right}" y2="${y}"></line>
          <text class="team-chart__axis-label" style="font-size:${axisFontSize}px" x="${margin.left - 14}" y="${y + 7}" text-anchor="end">${tick}</text>
        `;
      })
      .join("");

    const tickLines = xTicks
      .map(
        (tick) => `
          <line class="team-chart__tick" x1="${tick.x}" y1="${height - margin.bottom}" x2="${tick.x}" y2="${height - margin.bottom + 6}"></line>
          <text class="team-chart__axis-label" style="font-size:${axisFontSize}px" x="${tick.x}" y="${height - 54}" text-anchor="middle">${escapeHtml(tick.label)}</text>
        `,
      )
      .join("");

    const circles = points
      .map((point) => {
        const timestamp = new Date(point.completedAt);
        const circleClass = point.isCurrentUser ? "team-chart__point team-chart__point--current" : accentClass;
        const x = xFor(timestamp.getTime());
        const y = yFor(Number(point.score));
        const title = [
          `${point.displayName || "Workout"}: ${Number(point.score).toFixed(1)}% composite`,
          `Completed: ${tooltipFormatter.format(timestamp)}`,
          describeMetric("Consistency", point.consistencyScore),
          describeMetric("Arms", point.armsScore),
          describeMetric("Back", point.backScore),
        ].join(" | ");
        return `
          <circle class="${circleClass}" cx="${x}" cy="${y}" r="5">
            <title>${escapeHtml(title)}</title>
          </circle>
        `;
      })
      .join("");

    container.innerHTML = `
      <svg class="team-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(chartTitle)}">
        <line class="team-chart__axis" x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${height - margin.bottom}" />
        <line class="team-chart__axis" x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" />
        ${gridLines}
        ${tickLines}
        ${circles}
        <text class="team-chart__axis-title" style="font-size:${axisTitleFontSize}px" x="${width / 2}" y="${height - 10}" text-anchor="middle">Workout completion date</text>
        <text class="team-chart__axis-title" style="font-size:${axisTitleFontSize}px" x="22" y="${height / 2}" text-anchor="middle" transform="rotate(-90 22 ${height / 2})">Composite score (%)</text>
      </svg>
    `;
  };

  const loadTeamStats = async () => {
    setMessage("Loading team statistics...");

    try {
      const response = await fetch(getApiUrl("/api/team/stats/weekly"));
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Unable to load team statistics");
      }

      const windowStart = new Date(payload.windowStart);
      const windowEnd = new Date(payload.windowEnd);
      const userSummary = payload.user || {};
      const teamSummary = payload.team || {};

      rangeText.textContent = `Weekly window: ${formatDateRange(windowStart, windowEnd)}`;
      userChartHint.textContent = `${formatCount(userSummary.workoutCount)} workouts in this window. A combined score is the average of a workout's consistency, arms, and back scores.`;
      teamChartHint.textContent = teamSummary.teamId
        ? `${formatCount(teamSummary.workoutCount)} team workouts in this window. A combined score is the average of a workout's consistency, arms, and back scores.`
        : (teamSummary.emptyState || "Join a team to see team-wide scores.");

      renderSummary(
        userSummary,
        {
          title: userStatsTitle,
          workoutCount: userWorkoutCount,
          consistencyScore: userConsistencyScore,
          armsScore: userArmsScore,
          backScore: userBackScore,
        },
      );

      renderSummary(
        teamSummary,
        {
          title: teamStatsTitle,
          workoutCount: teamWorkoutCount,
          consistencyScore: teamConsistencyScore,
          armsScore: teamArmsScore,
          backScore: teamBackScore,
          meta: teamMemberCount,
        },
        teamSummary.emptyState,
      );

      renderScatter(userScatterChart, userSummary.points || [], {
        windowStart,
        windowEnd,
        emptyText: "No workouts with score data for this user in the last 7 days.",
        accentClass: "team-chart__point",
        chartTitle: "Your weekly composite workout scores",
      });

      renderScatter(teamScatterChart, teamSummary.points || [], {
        windowStart,
        windowEnd,
        emptyText: teamSummary.emptyState || "No team workouts with score data in the last 7 days.",
        accentClass: "team-chart__point team-chart__point--team",
        chartTitle: "Team weekly composite workout scores",
      });

      setMessage("");
    } catch (err) {
      setMessage(err.message || "Unable to load team statistics", "error");
      userStatsTitle.textContent = "Unavailable";
      teamStatsTitle.textContent = "Unavailable";
      userScatterChart.innerHTML = '<div class="team-chart-card__empty">Unable to load chart data.</div>';
      teamScatterChart.innerHTML = '<div class="team-chart-card__empty">Unable to load chart data.</div>';
    }
  };

  loadTeamStats();
})();
