(function () {
  function mediaKind(file) {
    if (file.type.startsWith("image/")) {
      return "image";
    }
    if (file.type.startsWith("video/")) {
      return "video";
    }

    const extension = file.name.split(".").pop().toLowerCase();
    if (["gif", "jpg", "jpeg", "png", "webp"].includes(extension)) {
      return "image";
    }
    if (["mov", "mp4", "ogg", "webm"].includes(extension)) {
      return "video";
    }
    return "";
  }

  function clearPreview(preview, frame, name, input, state) {
    if (state.objectUrl) {
      URL.revokeObjectURL(state.objectUrl);
      state.objectUrl = "";
    }
    frame.replaceChildren();
    name.textContent = "";
    preview.hidden = true;
    if (input) {
      input.value = "";
    }
  }

  function setupComposer(composer) {
    const input = composer.querySelector("[data-media-input]");
    const preview = composer.querySelector("[data-media-preview]");
    const frame = composer.querySelector("[data-media-preview-frame]");
    const name = composer.querySelector("[data-media-preview-name]");
    const clear = composer.querySelector("[data-media-preview-clear]");

    if (!input || !preview || !frame || !name || !clear) {
      return;
    }

    const state = { objectUrl: "" };

    input.addEventListener("change", function () {
      const file = input.files && input.files[0];
      clearPreview(preview, frame, name, null, state);

      if (!file) {
        return;
      }

      const kind = mediaKind(file);
      if (!kind) {
        return;
      }

      state.objectUrl = URL.createObjectURL(file);
      const element = document.createElement(kind === "image" ? "img" : "video");
      element.className = "composer-preview-media";
      element.src = state.objectUrl;

      if (kind === "image") {
        element.alt = "Selected image preview";
      } else {
        element.controls = true;
        element.muted = true;
        element.preload = "metadata";
      }

      frame.replaceChildren(element);
      name.textContent = file.name;
      preview.hidden = false;
    });

    clear.addEventListener("click", function () {
      clearPreview(preview, frame, name, input, state);
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  function setupPoll(composer) {
    const toggle = composer.querySelector("[data-poll-toggle]");
    const container = composer.querySelector("[data-poll-container]");
    const optionsList = composer.querySelector("[data-poll-options]");
    const addBtn = composer.querySelector("[data-add-poll-option]");

    if (!toggle || !container || !optionsList || !addBtn) {
      return;
    }

    let pollEnabled = false;

    function createOptionRow() {
      const index = optionsList.children.length;
      const row = document.createElement("div");
      row.className = "poll-option-row";
      row.style.display = "flex";
      row.style.gap = "8px";
      row.style.alignItems = "center";
      row.style.marginBottom = "8px";

      row.innerHTML = `
        <input name="poll_option" placeholder="Option ${index + 1}" maxlength="100" required>
        <button type="button" class="link-button remove-option" style="color: var(--muted)">Remove</button>
      `;

      row.querySelector(".remove-option").addEventListener("click", () => {
        if (optionsList.children.length > 2) {
          row.remove();
          updateUI();
        }
      });
      return row;
    }

    function updateUI() {
      const rows = optionsList.querySelectorAll(".poll-option-row");
      rows.forEach((row, i) => {
        row.querySelector("input").placeholder = `Option ${i + 1}`;
        row.querySelector(".remove-option").hidden = rows.length <= 2;
      });
      addBtn.hidden = rows.length >= 4;
    }

    toggle.addEventListener("click", () => {
      pollEnabled = !pollEnabled;
      container.hidden = !pollEnabled;
      toggle.textContent = pollEnabled ? "Remove Poll" : "Add Poll";

      if (pollEnabled && optionsList.children.length === 0) {
        optionsList.appendChild(createOptionRow());
        optionsList.appendChild(createOptionRow());
        updateUI();
      } else if (!pollEnabled) {
        optionsList.replaceChildren();
      }
    });

    addBtn.addEventListener("click", () => {
      if (optionsList.children.length < 4) {
        optionsList.appendChild(createOptionRow());
        updateUI();
      }
    });
  }

  function renderPollResults(container, results, votedOptionId) {
    container.innerHTML = results
      .map(
        (res) => `
      <div class="poll-result-row">
        <div class="poll-result-meta">
          <span>${res.text}</span>
          <span>${res.percentage}%</span>
        </div>
        <div class="poll-progress-bg ${res.option_id === votedOptionId ? "voted-for" : ""}">
          <div class="poll-progress-fill" style="width: ${res.percentage}%"></div>
          <div class="poll-progress-text">${res.votes} votes</div>
        </div>
      </div>
    `
      )
      .join("");
  }

  function setupPollVoting() {
    document.addEventListener("click", async (e) => {
      const voteBtn = e.target.closest("[data-poll-vote]");
      if (!voteBtn) {
        return;
      }

      const optionId = voteBtn.dataset.pollVote;
      const container = voteBtn.closest("[data-poll-id]");
      const pollId = container.dataset.pollId;

      try {
        const response = await fetch(`/api/polls/${pollId}/vote`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            option_id: optionId,
          }),
        });

        if (response.ok) {
          const data = await response.json();
          renderPollResults(container, data.results, optionId);
        } else {
          const error = await response.json();
          alert(error.error || "Failed to vote");
        }
      } catch (err) {
        console.error("Voting failed:", err);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("form.composer").forEach((composer) => {
      setupComposer(composer);
      setupPoll(composer);
    });
    setupPollVoting();
  });
})();
