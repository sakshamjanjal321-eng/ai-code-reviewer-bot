// Tab switching logic
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  document.querySelectorAll('.tab-content').forEach(content => {
    content.classList.add('hidden');
  });

  // Activate button and tab content
  event.target.classList.add('active');
  document.getElementById(`tab-${tabId}`).classList.remove('hidden');

  if (tabId === 'history') {
    fetchHistory();
  }
}

// Simple markdown formatter
function renderMarkdown(text) {
  if (!text) return "";
  let html = text;
  
  // Code blocks
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>');
  
  // Headers
  html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
  
  // Bullet lists
  html = html.replace(/^\s*-\s*(.*$)/gim, '<li>$1</li>');
  
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  
  // Inline Code
  html = html.replace(/`(.*?)`/g, '<code>$1</code>');
  
  // Convert remaining newlines to linebreaks (ignoring inside pre/code blocks)
  // Simple check: split by pre, only replace newlines in non-pre blocks
  const parts = html.split(/(<pre>[\s\S]*?<\/pre>)/);
  for (let i = 0; i < parts.length; i++) {
    if (!parts[i].startsWith('<pre>')) {
      parts[i] = parts[i].replace(/\n/g, '<br>');
    }
  }
  return parts.join('');
}

// Global review history holder
let reviewHistory = [];

// Fetch audit logs and update UI stats
async function fetchHistory() {
  const loader = document.getElementById('history-loader');
  const container = document.getElementById('history-list-container');
  
  if (loader) loader.classList.remove('hidden');
  if (container) container.innerHTML = '';

  try {
    const response = await fetch('/api/history');
    if (!response.ok) throw new Error('Failed to fetch history logs');
    
    reviewHistory = await response.json();
    updateStats(reviewHistory);

    if (container) {
      if (reviewHistory.length === 0) {
        container.innerHTML = '<p style="color: var(--text-muted); text-align: center;">No reviews recorded yet.</p>';
      } else {
        reviewHistory.forEach(item => {
          const dateStr = new Date(item.timestamp).toLocaleString();
          const element = document.createElement('div');
          element.className = 'history-item glass-panel';
          element.innerHTML = `
            <div class="history-info">
              <div class="history-repo">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"></path></svg>
                ${item.repo} ${item.pr_number ? '#' + item.pr_number : ''}
              </div>
              <div class="history-meta">
                <span>Type: ${item.type === 'github_pr' ? 'GitHub Action Trigger' : 'Diff Simulation'}</span> • 
                <span>${dateStr}</span>
              </div>
            </div>
            <div class="history-stats">
              ${item.errors ? `<span class="badge badge-error">${item.errors} Error${item.errors > 1 ? 's' : ''}</span>` : ''}
              ${item.warnings ? `<span class="badge badge-warning">${item.warnings} Warning${item.warnings > 1 ? 's' : ''}</span>` : ''}
              ${item.infos ? `<span class="badge badge-info">${item.infos} Info</span>` : ''}
              ${!item.errors && !item.warnings && !item.infos ? `<span class="badge badge-info" style="border: 1px solid var(--color-success); color: var(--color-success);">Clean</span>` : ''}
            </div>
          `;
          element.onclick = () => showHistoryDetail(item);
          container.appendChild(element);
        });
      }
    }
  } catch (error) {
    console.error('Error fetching history:', error);
    if (container) {
      container.innerHTML = `<p style="color: var(--color-error); text-align: center;">Error loading history: ${error.message}</p>`;
    }
  } finally {
    if (loader) loader.classList.add('hidden');
  }
}

// Calculate and render stats in real-time
function updateStats(history) {
  const totalReviews = history.length;
  let totalSuggestions = 0;
  let highAlerts = 0;

  history.forEach(item => {
    totalSuggestions += (item.comment_count || 0);
    highAlerts += (item.errors || 0);
  });

  const totalReviewsElem = document.getElementById('stat-total-reviews');
  const totalSuggElem = document.getElementById('stat-total-suggestions');
  const highAlertsElem = document.getElementById('stat-high-alerts');

  if (totalReviewsElem) totalReviewsElem.textContent = totalReviews;
  if (totalSuggElem) totalSuggElem.textContent = totalSuggestions;
  if (highAlertsElem) highAlertsElem.textContent = highAlerts;
}

// Load a specific historical review into the simulator workspace
function showHistoryDetail(item) {
  // Select Simulator Tab
  const simulatorTabBtn = document.querySelector(".tab-btn[onclick*='simulator']");
  if (simulatorTabBtn) {
    simulatorTabBtn.click();
  }
  
  // Render Summary
  const outputDiv = document.getElementById('simulation-output');
  outputDiv.innerHTML = `<h3>Review Result (${item.repo})</h3>${renderMarkdown(item.summary)}`;
  outputDiv.classList.remove('hidden');

  // Render mock inline comments saved in history if any
  // If not saved in detail, we notify the user.
  // Note: Since history object holds summary and stats, we display the summary.
  const commentsContainer = document.getElementById('comments-output-container');
  commentsContainer.innerHTML = '';
  
  const placeholderComment = document.createElement('div');
  placeholderComment.className = 'comment-card info glass-panel';
  placeholderComment.innerHTML = `
    <div class="comment-meta">
      <span class="comment-path">History Log Details</span>
      <span class="comment-severity info">INFO</span>
    </div>
    <div class="comment-body">
      This is a historical summary log. Direct inline comments are posted directly onto GitHub. Detailed live code changes are reviewed on demand using the simulator.
    </div>
  `;
  commentsContainer.appendChild(placeholderComment);
}

// Run simulation review
async function runSimulation() {
  const diffText = document.getElementById('diff-input').value;
  const loader = document.getElementById('simulator-loader');
  const runBtn = document.getElementById('btn-run-simulation');
  const outputDiv = document.getElementById('simulation-output');
  const commentsContainer = document.getElementById('comments-output-container');

  if (!diffText.trim()) {
    alert("Please paste a valid git diff before running the review.");
    return;
  }

  // UI state updates
  loader.style.display = 'flex';
  runBtn.disabled = true;
  outputDiv.classList.add('hidden');
  commentsContainer.innerHTML = '';

  try {
    const response = await fetch('/api/review-diff', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ diff_text: diffText })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Failed to analyze diff');
    }

    const data = await response.json(); // ReviewResult schema
    
    // Render high-level summary
    outputDiv.innerHTML = `<h3>AI Summary</h3>${renderMarkdown(data.summary)}`;
    outputDiv.classList.remove('hidden');

    // Render inline comments
    if (data.comments && data.comments.length > 0) {
      data.comments.forEach(comment => {
        const commentCard = document.createElement('div');
        commentCard.className = `comment-card ${comment.severity} glass-panel`;
        commentCard.innerHTML = `
          <div class="comment-meta">
            <span class="comment-path">${comment.file_path}:${comment.line_number}</span>
            <span class="comment-severity ${comment.severity}">${comment.severity}</span>
          </div>
          <div class="comment-body">
            ${renderMarkdown(comment.comment)}
          </div>
        `;
        commentsContainer.appendChild(commentCard);
      });
    } else {
      const cleanCard = document.createElement('div');
      cleanCard.className = 'comment-card info glass-panel';
      cleanCard.style.borderLeftColor = 'var(--color-success)';
      cleanCard.style.background = 'rgba(16, 185, 129, 0.05)';
      cleanCard.innerHTML = `
        <div class="comment-meta">
          <span class="comment-path">Code Audit Result</span>
          <span class="comment-severity info" style="color: var(--color-success); background: rgba(16, 185, 129, 0.15);">CLEAN</span>
        </div>
        <div class="comment-body">
          No critical suggestions found! The code changes align with standard practices and exhibit no high-risk issues.
        </div>
      `;
      commentsContainer.appendChild(cleanCard);
    }
    
    // Refresh stats from server history
    fetchHistory();
  } catch (error) {
    console.error('Error running diff review simulation:', error);
    alert(`Simulation failed: ${error.message}`);
  } finally {
    loader.style.display = 'none';
    runBtn.disabled = false;
  }
}

// Trigger standard PR review
async function runPRReview() {
  const repo = document.getElementById('gh-repo').value.trim();
  const pr = document.getElementById('gh-pr').value.trim();
  const token = document.getElementById('gh-token').value.trim();
  const loader = document.getElementById('pr-loader');
  const runBtn = document.getElementById('btn-run-pr');
  const resultMsg = document.getElementById('pr-result-msg');

  if (!repo || !pr) {
    alert("Please provide both repository name and pull request number.");
    return;
  }

  loader.style.display = 'flex';
  runBtn.disabled = true;
  resultMsg.classList.add('hidden');

  try {
    const response = await fetch('/api/review', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        repo: repo,
        pr_number: parseInt(pr),
        github_token: token || null
      })
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || 'Webhook trigger failed');
    }

    resultMsg.className = '';
    resultMsg.style.backgroundColor = 'rgba(16, 185, 129, 0.15)';
    resultMsg.style.border = '1px solid rgba(16, 185, 129, 0.3)';
    resultMsg.style.color = 'var(--color-success)';
    resultMsg.innerHTML = `PR Review initiated for <strong>${repo} #${pr}</strong> in the background. Audit results will be processed shortly.`;
    resultMsg.classList.remove('hidden');

    // Fetch updated history after 4 seconds when background review has had time to complete
    setTimeout(fetchHistory, 4000);
  } catch (error) {
    console.error('Error triggering PR review:', error);
    resultMsg.className = '';
    resultMsg.style.backgroundColor = 'rgba(239, 68, 68, 0.15)';
    resultMsg.style.border = '1px solid rgba(239, 68, 68, 0.3)';
    resultMsg.style.color = 'var(--color-error)';
    resultMsg.innerHTML = `Failed to trigger review: ${error.message}`;
    resultMsg.classList.remove('hidden');
  } finally {
    loader.style.display = 'none';
    runBtn.disabled = false;
  }
}

// Initial loader on startup
window.onload = () => {
  fetchHistory();
};
