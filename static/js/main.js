const form = document.getElementById('wallet-form');
const addressesInput = document.getElementById('wallet-input');
const resultsContainer = document.getElementById('results');
const alertContainer = document.getElementById('alert-container');
const lastUpdatedElement = document.getElementById('last-updated');
const refreshSelect = document.getElementById('refresh-interval');
const stopButton = document.getElementById('stop-btn');

let activeAddresses = [];
let refreshTimerId = null;
let isLoading = false;

const ADDRESS_REGEX = /^0x[a-fA-F0-9]{40}$/;

function parseAddresses(raw) {
  if (!raw) {
    return [];
  }
  return Array.from(
    new Set(
      raw
        .split(/[\s,\n\r]+/)
        .map((entry) => entry.trim().toLowerCase())
        .filter((entry) => entry.length > 0)
    )
  );
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

function formatNumber(value, digits = 4) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return '—';
  }
  const number = Number(value);
  if (Math.abs(number) >= 1000) {
    return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: digits });
}

function formatTimestamp(timestamp) {
  if (!timestamp) {
    return '—';
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return timestamp;
  }
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`;
}

function buildMarketLink(slug) {
  if (!slug) {
    return null;
  }
  if (slug.startsWith('http://') || slug.startsWith('https://')) {
    return slug;
  }
  return `https://polymarket.com/event/${slug}`;
}

function renderPositions(positions) {
  if (!positions || positions.length === 0) {
    return '<p class="text-muted mb-0">No open positions on Polymarket.</p>';
  }

  const rows = positions
    .map((position) => {
      const link = buildMarketLink(position.market_slug);
      const question = position.market_question || 'Unknown market';
      const marketCell = link
        ? `<a href="${link}" target="_blank" rel="noopener noreferrer">${question}</a>`
        : question;

      return `
        <tr>
          <td>${marketCell}</td>
          <td>${position.outcome ?? '—'}</td>
          <td>${formatNumber(position.net_position)}</td>
          <td>${formatNumber(position.average_price)}</td>
          <td>${formatNumber(position.last_price)}</td>
          <td>${formatNumber(position.value, 2)}</td>
        </tr>`;
    })
    .join('');

  return `
    <div class="table-responsive">
      <table class="table table-sm align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th scope="col">Market</th>
            <th scope="col">Outcome</th>
            <th scope="col">Net position</th>
            <th scope="col">Average price</th>
            <th scope="col">Last price</th>
            <th scope="col">Mark to market</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>`;
}

function renderOrders(orders) {
  if (!orders || orders.length === 0) {
    return '<p class="text-muted mb-0">No open limit orders.</p>';
  }

  const rows = orders
    .map((order) => {
      const link = buildMarketLink(order.market_slug);
      const question = order.market_question || 'Unknown market';
      const marketCell = link
        ? `<a href="${link}" target="_blank" rel="noopener noreferrer">${question}</a>`
        : question;

      return `
        <tr>
          <td>${marketCell}</td>
          <td>${order.outcome ?? '—'}</td>
          <td>${order.side ?? '—'}</td>
          <td>${order.order_type ?? '—'}</td>
          <td>${formatNumber(order.price)}</td>
          <td>${formatNumber(order.size)}</td>
          <td>${formatNumber(order.remaining_size)}</td>
          <td>${order.status ?? '—'}</td>
          <td>${formatTimestamp(order.created_at)}</td>
        </tr>`;
    })
    .join('');

  return `
    <div class="table-responsive">
      <table class="table table-sm align-middle mb-0">
        <thead class="table-light">
          <tr>
            <th scope="col">Market</th>
            <th scope="col">Outcome</th>
            <th scope="col">Side</th>
            <th scope="col">Type</th>
            <th scope="col">Price</th>
            <th scope="col">Size</th>
            <th scope="col">Remaining</th>
            <th scope="col">Status</th>
            <th scope="col">Placed</th>
          </tr>
        </thead>
        <tbody>
          ${rows}
        </tbody>
      </table>
    </div>`;
}

function renderRawData(rawPositions, rawOrders) {
  const content = {
    positions: rawPositions,
    orders: rawOrders,
  };
  return `
    <details class="mt-3 small text-muted">
      <summary>Raw API payload</summary>
      <pre class="mt-2 bg-body-secondary rounded p-2">${JSON.stringify(content, null, 2)}</pre>
    </details>`;
}

function renderWallet(result) {
  const statusBadge = result.error
    ? '<span class="badge bg-danger-subtle text-danger">API error</span>'
    : '<span class="badge bg-success-subtle text-success">Live</span>';

  const header = `
    <div class="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-2">
      <div>
        <h2 class="h5 mb-0">${result.address}</h2>
        <div class="small text-muted">Tracking open positions and limit orders</div>
      </div>
      ${statusBadge}
    </div>`;

  let body = '';
  if (result.error) {
    body = `<p class="text-danger mb-0">${result.error}</p>`;
  } else {
    body = `
      <div class="mb-4">
        <h3 class="h6 mb-2">Positions</h3>
        ${renderPositions(result.positions)}
      </div>
      <div>
        <h3 class="h6 mb-2">Open limit orders</h3>
        ${renderOrders(result.open_orders)}
      </div>
      ${renderRawData(result.positions?.map((p) => p.raw) ?? [], result.open_orders?.map((o) => o.raw) ?? [])}
    `;
  }

  return `
    <article class="card shadow-sm wallet-card">
      <div class="card-header bg-white border-bottom-0">
        ${header}
      </div>
      <div class="card-body">
        ${body}
      </div>
    </article>`;
}

function renderResults(snapshot) {
  if (!snapshot || !snapshot.results) {
    resultsContainer.innerHTML = '';
    lastUpdatedElement.textContent = 'Never';
    return;
  }

  resultsContainer.innerHTML = snapshot.results.map((result) => renderWallet(result)).join('');

  if (snapshot.requested_at) {
    lastUpdatedElement.textContent = formatTimestamp(snapshot.requested_at);
  } else {
    lastUpdatedElement.textContent = new Date().toLocaleString();
  }
}

async function fetchSnapshot(addresses) {
  const response = await fetch('/api/wallets', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ addresses }),
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.error || `Request failed with status ${response.status}`;
    throw new Error(message);
  }
  return payload;
}

async function refresh() {
  if (isLoading || activeAddresses.length === 0) {
    return;
  }
  isLoading = true;
  showAlert('Refreshing wallets…', 'info');
  try {
    const snapshot = await fetchSnapshot(activeAddresses);
    clearAlert();
    renderResults(snapshot);
  } catch (error) {
    showAlert(error.message, 'danger');
  } finally {
    isLoading = false;
  }
}

function setMonitoringState(running) {
  stopButton.disabled = !running;
  if (running) {
    form.classList.add('is-active');
  } else {
    form.classList.remove('is-active');
    lastUpdatedElement.textContent = 'Never';
    resultsContainer.innerHTML = '';
  }
}

function stopMonitoring() {
  if (refreshTimerId) {
    clearInterval(refreshTimerId);
    refreshTimerId = null;
  }
  activeAddresses = [];
  setMonitoringState(false);
  clearAlert();
}

async function startMonitoring(addresses) {
  activeAddresses = addresses;
  setMonitoringState(true);
  await refresh();

  const intervalSeconds = Number(refreshSelect.value || '20');
  if (refreshTimerId) {
    clearInterval(refreshTimerId);
  }
  refreshTimerId = setInterval(refresh, intervalSeconds * 1000);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const addresses = parseAddresses(addressesInput.value);

  if (addresses.length === 0) {
    showAlert('Please provide at least one Polygon wallet address.', 'warning');
    return;
  }

  const invalid = addresses.filter((address) => !ADDRESS_REGEX.test(address));
  if (invalid.length > 0) {
    showAlert(`Invalid wallet addresses detected: ${invalid.join(', ')}`, 'danger');
    return;
  }

  clearAlert();
  await startMonitoring(addresses);
});

stopButton.addEventListener('click', () => {
  stopMonitoring();
});

window.addEventListener('beforeunload', () => {
  if (refreshTimerId) {
    clearInterval(refreshTimerId);
  }
});
