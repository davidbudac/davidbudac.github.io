const summaryCardsContainer = document.getElementById('summary-cards');
const topicsList = document.getElementById('topics-list');
const topTweetsTable = document.querySelector('#top-tweets-table tbody');
const lastUpdated = document.getElementById('last-updated');
const alertContainer = document.getElementById('alert-container');
const refreshButton = document.getElementById('refresh-btn');

async function fetchData(endpoint = '/data', options = {}) {
  try {
    const response = await fetch(endpoint, options);
    const payload = await response.json();
    if (!response.ok) {
      const message = payload?.error || `Request failed with status ${response.status}`;
      throw new Error(message);
    }
    return payload;
  } catch (error) {
    showAlert(`Unable to load data: ${error.message}`, 'danger');
    throw error;
  }
}

function showAlert(message, type = 'info') {
  alertContainer.innerHTML = `
    <div class="alert alert-${type} alert-dismissible fade show" role="alert">
      ${message}
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>`;
}

function clearAlert() {
  alertContainer.innerHTML = '';
}

function renderSummary(summary) {
  const items = [
    { label: 'Tweets analysed', value: summary.tweet_count.toLocaleString() },
    { label: 'Average length', value: `${summary.avg_length.toFixed(1)} chars` },
    { label: 'Median length', value: `${summary.median_length.toFixed(0)} chars` },
    { label: 'Average likes', value: summary.avg_likes.toFixed(0) },
    { label: 'Average retweets', value: summary.avg_retweets.toFixed(0) },
    { label: 'Length range', value: `${summary.min_length} – ${summary.max_length} chars` },
  ];

  summaryCardsContainer.innerHTML = items
    .map(
      (item) => `
        <div class="col-12 col-md-4 col-xl-2 mb-3">
          <div class="card h-100">
            <div class="card-body">
              <p class="text-muted small mb-1">${item.label}</p>
              <p class="fw-semibold h5 mb-0">${item.value}</p>
            </div>
          </div>
        </div>`
    )
    .join('');
}

function renderScatter(scatter) {
  const trace = {
    x: scatter.timestamps,
    y: scatter.lengths,
    type: 'scatter',
    mode: 'markers',
    marker: {
      color: '#0d6efd',
      size: 8,
      opacity: 0.7,
    },
    text: scatter.hover_text,
    hovertemplate: '%{text}<extra></extra>',
  };

  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 50 },
    xaxis: { title: 'Date' },
    yaxis: { title: 'Tweet length (characters)' },
  };

  Plotly.newPlot('length-time-chart', [trace], layout, { responsive: true });
}

function renderDaily(daily) {
  const trace = {
    x: daily.date_only,
    y: daily.tweet_count,
    type: 'bar',
    marker: { color: '#6610f2' },
    hovertemplate: '%{x}<br>Tweets: %{y}<extra></extra>',
  };

  const secondary = {
    x: daily.date_only,
    y: daily.avg_length,
    yaxis: 'y2',
    type: 'scatter',
    mode: 'lines',
    name: 'Avg length',
    marker: { color: '#20c997' },
    hovertemplate: 'Avg length: %{y:.0f}<extra></extra>',
  };

  const layout = {
    margin: { t: 10, r: 50, b: 60, l: 50 },
    xaxis: { title: 'Date' },
    yaxis: { title: 'Tweet count' },
    yaxis2: {
      overlaying: 'y',
      side: 'right',
      title: 'Average length',
    },
    legend: { orientation: 'h', y: -0.2 },
  };

  Plotly.newPlot('daily-chart', [trace, secondary], layout, { responsive: true });
}

function renderHourly(hourly) {
  const trace = {
    x: hourly.hour,
    y: hourly.tweet_count,
    type: 'bar',
    marker: { color: '#198754' },
    hovertemplate: 'Hour %{x}:00<br>Tweets: %{y}<extra></extra>',
  };

  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 50 },
    xaxis: { title: 'Hour of day (UTC)' },
    yaxis: { title: 'Tweet count' },
  };

  Plotly.newPlot('hourly-chart', [trace], layout, { responsive: true });
}

function renderHistogram(hist) {
  const trace = {
    x: hist.bins,
    y: hist.counts,
    type: 'bar',
    marker: { color: '#fd7e14' },
    hovertemplate: 'Length: %{x}<br>Count: %{y}<extra></extra>',
  };

  const layout = {
    bargap: 0,
    margin: { t: 10, r: 10, b: 40, l: 50 },
    xaxis: { title: 'Tweet length (characters)' },
    yaxis: { title: 'Tweet count' },
  };

  Plotly.newPlot('length-hist-chart', [trace], layout, { responsive: true });
}

function renderTimeOfDay(timeOfDay) {
  const trace = {
    x: timeOfDay.time_of_day,
    y: timeOfDay.tweet_count,
    type: 'bar',
    marker: { color: '#6f42c1' },
    hovertemplate: '%{x}<br>Tweets: %{y}<extra></extra>',
  };

  const layout = {
    margin: { t: 10, r: 10, b: 40, l: 50 },
    xaxis: { title: 'Time of day' },
    yaxis: { title: 'Tweet count' },
  };

  Plotly.newPlot('time-of-day-chart', [trace], layout, { responsive: true });
}

function renderTopics(topics) {
  if (!topics || topics.length === 0) {
    topicsList.innerHTML = '<li class="list-group-item">Not enough data to detect topics.</li>';
    return;
  }

  topicsList.innerHTML = topics
    .map(
      (topic) => `
        <li class="list-group-item">
          <strong>Topic ${topic.topic}:</strong>
          <span class="text-muted">${topic.keywords.join(', ')}</span>
        </li>`
    )
    .join('');
}

function renderTopTweets(tweets) {
  topTweetsTable.innerHTML = tweets
    .map(
      (tweet) => `
        <tr>
          <td>${tweet.created_at}</td>
          <td><a href="${tweet.url}" target="_blank" rel="noopener noreferrer">${tweet.content}</a></td>
          <td>${tweet.like_count.toLocaleString()}</td>
          <td>${tweet.retweet_count.toLocaleString()}</td>
          <td>${tweet.reply_count.toLocaleString()}</td>
        </tr>`
    )
    .join('');
}

function updateLastUpdated(timestamp) {
  if (!timestamp) {
    lastUpdated.textContent = '';
    return;
  }
  const date = new Date(timestamp);
  lastUpdated.textContent = `Last updated ${date.toLocaleString()}`;
}

function renderAll(data, timestamp) {
  renderSummary(data.summary);
  renderScatter(data.scatter);
  renderDaily(data.daily);
  renderHourly(data.hourly);
  renderHistogram(data.length_hist);
  renderTimeOfDay(data.time_of_day);
  renderTopics(data.topics);
  renderTopTweets(data.top_examples);
  updateLastUpdated(timestamp);
}

async function initialise() {
  clearAlert();
  try {
    const response = await fetchData();
    renderAll(response.data, response.last_updated);
  } catch (error) {
    console.error(error);
    showAlert('Unable to load Elon Musk tweet analytics right now. Please try again later.', 'danger');
  }
}

refreshButton.addEventListener('click', async () => {
  refreshButton.disabled = true;
  refreshButton.textContent = 'Refreshing…';
  clearAlert();
  try {
    const response = await fetchData('/refresh', { method: 'POST' });
    renderAll(response.data, response.last_updated);
    showAlert('Data refreshed successfully.', 'success');
  } catch (error) {
    console.error(error);
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = 'Refresh data';
  }
});

window.addEventListener('DOMContentLoaded', initialise);
