/* NewCo Charts - Search */

window.NewCoSearch = {
  index: null,
  naicsNames: null,
  dataCache: {},
  chartDataBase: '',
  resultCounter: 0,

  async init(options) {
    options = options || {};
    var dataBase = options.dataBase || '../data/search/';
    this.chartDataBase = options.chartDataBase || '../data/';

    // Resolve site root from nav.js script for page links
    var scripts = document.querySelectorAll('script[src*="nav.js"]');
    var siteRoot = '';
    if (scripts.length > 0) {
      var src = scripts[0].getAttribute('src');
      siteRoot = src.replace(/js\/nav\.js$/, '');
    }
    this.siteRoot = siteRoot;

    try {
      var resp = await Promise.all([
        fetch(dataBase + 'search_index.json'),
        fetch(dataBase + 'naics_names.json')
      ]);
      this.index = await resp[0].json();
      this.naicsNames = await resp[1].json();
    } catch (e) {
      document.getElementById('search-results').innerHTML =
        '<div class="search-empty">Failed to load search index.</div>';
      return;
    }

    // Check URL for query parameter
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q');
    var input = document.getElementById('search-input');
    if (q) {
      input.value = q;
      this.search(q);
    }

    // Sync nav search input if present
    var navInput = document.getElementById('nav-search-input');
    if (navInput && q) {
      navInput.value = q;
    }

    // Listen for input
    var self = this;
    var debounce;
    input.addEventListener('input', function() {
      clearTimeout(debounce);
      debounce = setTimeout(function() { self.search(input.value); }, 200);
    });

    // Also handle Enter key
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        clearTimeout(debounce);
        self.search(input.value);
      }
    });
  },

  search: function(query) {
    var q = query.trim().toLowerCase();
    if (!q) {
      document.getElementById('search-results').innerHTML = '';
      document.getElementById('search-hint').textContent = '';
      var url = new URL(window.location);
      url.searchParams.delete('q');
      history.replaceState(null, '', url);
      return;
    }

    var url = new URL(window.location);
    url.searchParams.set('q', query.trim());
    history.replaceState(null, '', url);

    var isNaicsQuery = /^\d{2,6}$/.test(q);
    var results;
    var hint = document.getElementById('search-hint');

    if (isNaicsQuery) {
      results = this.index.filter(function(entry) {
        return entry.naics && entry.naics.indexOf(q) === 0;
      });
      var resultIds = {};
      results.forEach(function(r) { resultIds[r.id + '|' + r.page] = true; });
      var keywordResults = this.index.filter(function(entry) {
        if (resultIds[entry.id + '|' + entry.page]) return false;
        return entry.name.toLowerCase().indexOf(q) !== -1;
      });
      results = results.concat(keywordResults);

      var naicsLabel = this.naicsNames[q];
      hint.textContent = naicsLabel ? 'NAICS ' + q + ': ' + naicsLabel : '';
    } else {
      var terms = q.split(/\s+/).filter(function(t) { return t.length > 0; });
      results = this.index.filter(function(entry) {
        var haystack = (entry.name + ' ' + (entry.naicsName || '') + ' ' +
                        entry.sectionLabel + ' ' + (entry.naics || '')).toLowerCase();
        return terms.every(function(term) {
          return haystack.indexOf(term) !== -1;
        });
      });
      hint.textContent = '';
    }

    this.renderResults(results, q);
  },

  renderResults: function(results, query) {
    var container = document.getElementById('search-results');
    this.resultCounter = 0;

    if (results.length === 0) {
      container.innerHTML = '<div class="search-empty">No results found.</div>';
      return;
    }

    // Deduplicate: group entries by series id + section, merge pages
    var seriesMap = {};
    var seriesOrder = [];
    results.forEach(function(r) {
      var key = r.id + '|' + r.sectionLabel;
      if (!seriesMap[key]) {
        seriesMap[key] = {
          id: r.id,
          name: r.name,
          naics: r.naics,
          naicsName: r.naicsName,
          section: r.section,
          sectionLabel: r.sectionLabel,
          pages: []
        };
        seriesOrder.push(key);
      }
      var existing = seriesMap[key];
      var alreadyHasPage = existing.pages.some(function(p) { return p.page === r.page; });
      if (!alreadyHasPage) {
        existing.pages.push({ page: r.page, pageLabel: r.pageLabel, dataFile: r.dataFile });
      }
    });

    // Group by section
    var groups = {};
    var groupOrder = [];
    var self = this;
    seriesOrder.forEach(function(key) {
      var item = seriesMap[key];
      if (!groups[item.sectionLabel]) {
        groups[item.sectionLabel] = [];
        groupOrder.push(item.sectionLabel);
      }
      groups[item.sectionLabel].push(item);
    });

    var uniqueCount = seriesOrder.length;
    var html = '<div class="search-count">' + uniqueCount + ' series found';
    html += ' <button class="view-all-btn" id="view-all-btn">View All Charts</button>';
    html += '</div>';

    groupOrder.forEach(function(section) {
      var items = groups[section];
      html += '<div class="search-group">';
      html += '<h2 class="search-group-title">' + section + ' (' + items.length + ')</h2>';

      items.forEach(function(item) {
        var rid = 'sr-' + (self.resultCounter++);
        var naicsBadge = item.naics
          ? '<span class="naics-badge">NAICS ' + item.naics + '</span>'
          : '';

        // Build page links with + expand buttons
        var links = item.pages.map(function(p, i) {
          var expandId = rid + '-' + i;
          return '<a href="' + self.siteRoot + p.page + '" class="result-link">' + p.pageLabel + '</a>' +
                 '<button class="expand-btn" data-expand-id="' + expandId + '" ' +
                 'data-series-id="' + item.id + '" data-data-file="' + p.dataFile + '" ' +
                 'title="Show chart">+</button>';
        }).join('');

        html += '<div class="search-result" id="' + rid + '">';
        html += '<div class="result-name">' + self.highlight(item.name, query) + '</div>';
        html += naicsBadge;
        html += '<div class="result-links">' + links + '</div>';
        // Chart containers (one per page link, hidden by default)
        item.pages.forEach(function(p, i) {
          html += '<div class="inline-chart-wrap" id="' + rid + '-' + i + '" style="display:none;">';
          html += '<div class="inline-chart-container"></div>';
          html += '</div>';
        });
        html += '</div>';
      });

      html += '</div>';
    });

    container.innerHTML = html;

    // Attach expand button handlers
    container.querySelectorAll('.expand-btn').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.preventDefault();
        var expandId = btn.getAttribute('data-expand-id');
        var seriesId = btn.getAttribute('data-series-id');
        var dataFile = btn.getAttribute('data-data-file');
        self.toggleChart(expandId, seriesId, dataFile, btn);
      });
    });

    // View All button handler
    var viewAllBtn = document.getElementById('view-all-btn');
    if (viewAllBtn) {
      viewAllBtn.addEventListener('click', function() {
        self.viewAll();
      });
    }
  },

  toggleChart: function(expandId, seriesId, dataFile, btn) {
    var wrap = document.getElementById(expandId);
    if (!wrap) return;

    if (wrap.style.display !== 'none') {
      // Collapse
      wrap.style.display = 'none';
      btn.textContent = '+';
      btn.classList.remove('active');
      var plotDiv = wrap.querySelector('.inline-chart-container');
      if (plotDiv && window.Plotly) Plotly.purge(plotDiv);
      return;
    }

    // Expand
    wrap.style.display = 'block';
    btn.textContent = '\u2212'; // minus sign
    btn.classList.add('active');
    var plotDiv = wrap.querySelector('.inline-chart-container');
    plotDiv.innerHTML = '<div class="chart-loading">Loading chart...</div>';

    this.loadAndRender(plotDiv, seriesId, dataFile);
  },

  viewAll: function() {
    var self = this;
    var btns = document.querySelectorAll('.expand-btn');
    // Check if most are already open — if so, collapse all
    var openCount = 0;
    btns.forEach(function(btn) {
      if (btn.classList.contains('active')) openCount++;
    });

    if (openCount > btns.length / 2) {
      // Collapse all
      btns.forEach(function(btn) {
        var expandId = btn.getAttribute('data-expand-id');
        var wrap = document.getElementById(expandId);
        if (wrap && wrap.style.display !== 'none') {
          wrap.style.display = 'none';
          btn.textContent = '+';
          btn.classList.remove('active');
          var plotDiv = wrap.querySelector('.inline-chart-container');
          if (plotDiv && window.Plotly) Plotly.purge(plotDiv);
        }
      });
      document.getElementById('view-all-btn').textContent = 'View All Charts';
    } else {
      // Expand all — batch to avoid UI jank
      var pending = [];
      btns.forEach(function(btn) {
        if (!btn.classList.contains('active')) {
          pending.push(btn);
        }
      });
      var batch = 0;
      function processBatch() {
        var slice = pending.slice(batch, batch + 6);
        slice.forEach(function(btn) {
          var expandId = btn.getAttribute('data-expand-id');
          var seriesId = btn.getAttribute('data-series-id');
          var dataFile = btn.getAttribute('data-data-file');
          self.toggleChart(expandId, seriesId, dataFile, btn);
        });
        batch += 6;
        if (batch < pending.length) {
          requestAnimationFrame(processBatch);
        }
      }
      if (pending.length > 0) processBatch();
      document.getElementById('view-all-btn').textContent = 'Collapse All';
    }
  },

  loadAndRender: function(plotDiv, seriesId, dataFile) {
    var self = this;
    var url = this.chartDataBase + dataFile;

    // Use cache if available
    if (this.dataCache[dataFile]) {
      self.renderChart(plotDiv, seriesId, this.dataCache[dataFile]);
      return;
    }

    fetch(url).then(function(resp) {
      return resp.json();
    }).then(function(data) {
      self.dataCache[dataFile] = data;
      self.renderChart(plotDiv, seriesId, data);
    }).catch(function() {
      plotDiv.innerHTML = '<div class="chart-loading">Failed to load data.</div>';
    });
  },

  renderChart: function(plotDiv, seriesId, data) {
    var series = null;
    for (var i = 0; i < data.series.length; i++) {
      if (data.series[i].id === seriesId) {
        series = data.series[i];
        break;
      }
    }
    if (!series) {
      plotDiv.innerHTML = '<div class="chart-loading">Series not found.</div>';
      return;
    }

    // Compute YoY % change
    var rawDates = series.data.map(function(d) { return d.date; });
    var rawValues = series.data.map(function(d) { return d.value; });
    var freq = data.metadata && data.metadata.frequency;
    var lookback = (freq === 'quarterly') ? 4 : 12;

    var dates = [];
    var values = [];
    for (var i = lookback; i < rawDates.length; i++) {
      var cur = rawValues[i];
      var prev = rawValues[i - lookback];
      dates.push(rawDates[i]);
      if (cur != null && prev != null && prev !== 0) {
        values.push(((cur - prev) / Math.abs(prev)) * 100);
      } else {
        values.push(null);
      }
    }

    // Trim to last 24 periods
    if (dates.length > 24) {
      dates = dates.slice(-24);
      values = values.slice(-24);
    }

    // Color bars
    var colors = values.map(function(v) {
      return v != null && v >= 0 ? '#4a90d9' : '#e74c3c';
    });

    plotDiv.innerHTML = '';
    Plotly.newPlot(plotDiv, [{
      x: dates,
      y: values,
      type: 'bar',
      marker: { color: colors },
      hovertemplate: '%{x|%b %Y}: %{y:.1f}%<extra></extra>'
    }], {
      margin: { l: 45, r: 10, t: 10, b: 30 },
      height: 180,
      yaxis: { title: 'YoY %', ticksuffix: '%' },
      xaxis: {
        tickformat: '%b\n%Y',
        tickangle: 0
      },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent'
    }, {
      responsive: true,
      displayModeBar: false
    });
  },

  highlight: function(text, query) {
    var terms = query.toLowerCase().split(/\s+/).filter(function(t) { return t.length > 0; });
    var result = text;
    terms.forEach(function(term) {
      var escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      var regex = new RegExp('(' + escaped + ')', 'gi');
      result = result.replace(regex, '<mark>$1</mark>');
    });
    return result;
  }
};

// Initialized by page script calling NewCoSearch.init({ ... })
